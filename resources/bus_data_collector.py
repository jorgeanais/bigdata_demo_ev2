"""
Bus data collector — saves to partitioned Parquet files.

Strategy:
  - Captures every CAPTURE_INTERVAL_SEC seconds for TOTAL_HOURS hours.
  - Buffers FLUSH_EVERY captures in RAM before writing to disk.
  - One Parquet file per UTC date: data/buses_YYYY-MM-DD.parquet
  - Uses category dtype for low-cardinality columns to save ~60% space.
  - Appends to existing files so restarts are safe.
  - Flushes buffer on SIGINT/SIGTERM (Ctrl+C or system shutdown).

Estimated resource usage (6 334 buses, 1-min interval, 24 h):
  - Captures: 1 440
  - Total rows: ~9.1 million
  - RAM (buffer of 10): ~50 MB peak
  - Disk (Parquet, compressed): ~150–250 MB/day
"""

import os
import signal
import sys
import time

import pandas as pd
import requests

# ── Configuration ────────────────────────────────────────────────────────────
API_URL             = "https://velocidades.seguimos.cl/?all-buses-data=1"
CAPTURE_INTERVAL_SEC = 60        # seconds between captures
TOTAL_HOURS          = 240       # total run time
FLUSH_EVERY          = 10        # write to disk every N successful captures
OUTPUT_DIR           = "data"    # folder for Parquet files
REQUEST_TIMEOUT_SEC  = 20        # HTTP timeout
# ─────────────────────────────────────────────────────────────────────────────

TOTAL_CAPTURES = int(TOTAL_HOURS * 3600 / CAPTURE_INTERVAL_SEC)

# Low-cardinality columns stored as category (saves ~60 % RAM and disk)
CATEGORY_COLS = ["servicio", "direccion", "operador"]

DTYPES = {
    "patente":        "string",
    "latitud":        "float32",
    "longitud":       "float32",
    "velocidad":      "float32",
    "servicio":       "category",
    "direccion":      "category",
    "operador":       "category",
    "timestamp_gps":  "string",
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Parquet helpers ───────────────────────────────────────────────────────────

def _parquet_path(dt: pd.Timestamp) -> str:
    return os.path.join(OUTPUT_DIR, f"buses_{dt.date()}.parquet")


def flush_buffer(buffer: list) -> None:
    """Convert buffer to DataFrame and append to the appropriate Parquet file(s)."""
    if not buffer:
        return

    df = pd.DataFrame(buffer)

    # Apply efficient dtypes
    for col, dtype in DTYPES.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)

    # Partition by capture date (UTC) in case a flush spans midnight
    for date, group in df.groupby(df["timestamp_captura"].dt.date):
        path = os.path.join(OUTPUT_DIR, f"buses_{date}.parquet")
        group = group.reset_index(drop=True)

        if os.path.exists(path):
            existing = pd.read_parquet(path)
            # Re-apply category dtypes after read (they may have been stored differently)
            for col in CATEGORY_COLS:
                if col in existing.columns:
                    existing[col] = existing[col].astype("category")
            combined = pd.concat([existing, group], ignore_index=True)
        else:
            combined = group

        combined.to_parquet(path, index=False, compression="snappy")

    print(f"  → Flushed {len(df):,} rows to Parquet.")
    buffer.clear()


# ── Graceful shutdown ─────────────────────────────────────────────────────────

_buffer_ref: list = []  # module-level ref so the signal handler can access it

def _handle_exit(signum, frame):
    print("\nSignal received — flushing buffer before exit…")
    flush_buffer(_buffer_ref)
    print("Done. Exiting.")
    sys.exit(0)

signal.signal(signal.SIGINT,  _handle_exit)
signal.signal(signal.SIGTERM, _handle_exit)

# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    buffer = _buffer_ref
    successful = 0
    failed = 0

    print(f"Starting capture: {TOTAL_CAPTURES} iterations × {CAPTURE_INTERVAL_SEC}s = {TOTAL_HOURS}h")
    print(f"Flushing to Parquet every {FLUSH_EVERY} successful captures.")
    print(f"Output directory: {os.path.abspath(OUTPUT_DIR)}\n")

    for i in range(TOTAL_CAPTURES):
        iter_start = time.monotonic()

        try:
            response = requests.get(API_URL, timeout=REQUEST_TIMEOUT_SEC)
            response.raise_for_status()

            features = response.json().get("geojson", {}).get("features", [])
            capture_ts = pd.Timestamp.now('UTC')

            for feature in features:
                props = feature.get("properties", {})
                coords = feature.get("geometry", {}).get("coordinates", [None, None])
                buffer.append({
                    "patente":           props.get("license_plate"),
                    "latitud":           coords[1] if len(coords) == 2 else None,
                    "longitud":          coords[0] if len(coords) == 2 else None,
                    "velocidad":         props.get("speed"),
                    "servicio":          props.get("route_code"),
                    "direccion":         props.get("route_direction"),
                    "operador":          props.get("operator"),
                    "timestamp_gps":     props.get("timestamp"),
                    "timestamp_captura": capture_ts,
                })

            successful += 1
            print(f"[{i+1:>4}/{TOTAL_CAPTURES}] ✓ {len(features):,} buses — buffer: {len(buffer):,} rows")

            if successful % FLUSH_EVERY == 0:
                flush_buffer(buffer)

        except requests.RequestException as e:
            failed += 1
            print(f"[{i+1:>4}/{TOTAL_CAPTURES}] ✗ Request error (attempt {failed}): {e}")
        except Exception as e:
            failed += 1
            print(f"[{i+1:>4}/{TOTAL_CAPTURES}] ✗ Unexpected error: {e}")

        # Sleep only the remaining time in this interval (accounts for request duration)
        elapsed = time.monotonic() - iter_start
        sleep_for = max(0.0, CAPTURE_INTERVAL_SEC - elapsed)
        if i < TOTAL_CAPTURES - 1:
            time.sleep(sleep_for)

    # Final flush
    print("\nAll captures complete — flushing remaining buffer…")
    flush_buffer(buffer)
    print(f"\nFinished. Successful: {successful}, Failed: {failed}")
    print(f"Files saved in: {os.path.abspath(OUTPUT_DIR)}/")


if __name__ == "__main__":
    main()