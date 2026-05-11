"""
Pipeline ETL — Flota de Buses
Lee archivos Parquet desde GCS, transforma y carga en BigQuery.
Implementa idempotencia mediante tabla de control pipeline_log.
"""

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition
from google.cloud import bigquery
from datetime import datetime, timezone
import pyarrow.parquet as pq
import pyarrow.fs as pafs
import argparse
import logging
import sys
import os

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de validación
# ---------------------------------------------------------------------------
VEL_MIN, VEL_MAX = 0.0, 120.0  # km/h válidos
LAT_MIN, LAT_MAX = -56.0, -17.0  # Bounding box Chile
LON_MIN, LON_MAX = -76.0, -65.0
DIAS_ES = {
    "Monday": "Lunes",
    "Tuesday": "Martes",
    "Wednesday": "Miercoles",
    "Thursday": "Jueves",
    "Friday": "Viernes",
    "Saturday": "Sabado",
    "Sunday": "Domingo",
}

# ---------------------------------------------------------------------------
# Funciones de transformación (DoFn)
# ---------------------------------------------------------------------------


class TransformarRegistro(beam.DoFn):
    """Aplica transformaciones y calcula columnas derivadas."""

    OUTPUT_INVALIDO = "invalido"

    def __init__(self, archivo_origen):
        self.archivo_origen = archivo_origen

    def process(self, row):
        """
        Recibe un dict con las columnas originales del Parquet.
        Emite al output principal si es válido,
        o al output 'invalido' si no pasa las validaciones.
        """
        from datetime import timezone
        import pytz

        ahora_utc = datetime.now(timezone.utc)
        motivos = []

        # --- Parsear timestamp_gps ---
        # Soporta formatos: '2026-05-08T20:41:49+0000', '2026-05-08 20:41:49', ISO 8601
        ts_gps = None
        try:
            raw = row.get("timestamp_gps", "")
            if raw is None or raw == "":
                motivos.append("timestamp_gps_nulo")
            elif isinstance(raw, str):
                raw_clean = raw.replace("+0000", "+00:00").replace("Z", "+00:00")
                try:
                    ts_gps = datetime.fromisoformat(raw_clean)
                    if ts_gps.tzinfo is None:
                        ts_gps = ts_gps.replace(tzinfo=timezone.utc)
                except ValueError:
                    ts_gps = datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")
                    ts_gps = ts_gps.replace(tzinfo=timezone.utc)
            elif hasattr(raw, "tzinfo"):
                ts_gps = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        except Exception as e:
            motivos.append(f"timestamp_gps_invalido({e})")

        # --- timestamp_captura ---
        ts_cap = row.get("timestamp_captura")
        if ts_cap is None:
            motivos.append("timestamp_captura_nulo")

        # --- Validar velocidad ---
        vel = float(row.get("velocidad") or -1)
        vel_valida = VEL_MIN <= vel <= VEL_MAX
        if not vel_valida:
            motivos.append(f"velocidad_fuera_rango({vel})")

        # --- Validar coordenadas GPS ---
        lat = float(row.get("latitud") or 0)
        lon = float(row.get("longitud") or 0)
        gps_valido = (LAT_MIN <= lat <= LAT_MAX) and (LON_MIN <= lon <= LON_MAX)
        if not gps_valido:
            motivos.append(f"gps_fuera_chile(lat={lat},lon={lon})")

        # --- Si hay errores críticos, enviar a inválidos ---
        if motivos:
            yield beam.pvalue.TaggedOutput(
                self.OUTPUT_INVALIDO,
                {
                    "patente": str(row.get("patente", "")),
                    "latitud": lat,
                    "longitud": lon,
                    "velocidad": vel,
                    "servicio": str(row.get("servicio", "")),
                    "timestamp_gps": str(row.get("timestamp_gps", "")),
                    "archivo_origen": self.archivo_origen,
                    "motivo_rechazo": " | ".join(motivos),
                    "procesado_en": ahora_utc.isoformat(),
                },
            )
            return

        # --- Columnas derivadas ---
        santiago = __import__("pytz").timezone("America/Santiago")
        ts_cap_local = (
            ts_cap.astimezone(santiago) if hasattr(ts_cap, "astimezone") else ts_cap
        )
        hora = ts_cap_local.hour if ts_cap_local else 0
        dia_en = ts_cap_local.strftime("%A") if ts_cap_local else "Monday"
        es_hora_punta = (7 <= hora < 9) or (17 <= hora < 19)

        latencia = None
        if ts_gps and ts_cap:
            latencia = (ts_cap - ts_gps).total_seconds()

        yield {
            "patente": str(row.get("patente", "")),
            "servicio": str(row.get("servicio", "")),
            "operador": int(row.get("operador") or 0),
            "direccion": str(row.get("direccion", "")),
            "latitud": lat,
            "longitud": lon,
            "velocidad": vel,
            "timestamp_gps": ts_gps.isoformat() if ts_gps else None,
            "timestamp_captura": ts_cap.isoformat() if ts_cap else None,
            "fecha_particion": (
                ts_cap_local.strftime("%Y-%m-%d") if ts_cap_local else None
            ),
            "hora_captura": hora,
            "dia_semana": DIAS_ES.get(dia_en, dia_en),
            "es_hora_punta": es_hora_punta,
            "latencia_segundos": latencia,
            "velocidad_valida": vel_valida,
            "gps_valido": gps_valido,
            "archivo_origen": self.archivo_origen,
            "procesado_en": ahora_utc.isoformat(),
        }


# ---------------------------------------------------------------------------
# Control de idempotencia
# ---------------------------------------------------------------------------


def ya_fue_procesado(project_id, archivo_nombre):
    """
    Consulta pipeline_log. Retorna True si el archivo ya fue
    procesado exitosamente (estado = 'SUCCESS').
    """
    client = bigquery.Client(project=project_id)
    query = f"""
        SELECT COUNT(*) AS n
        FROM `{project_id}.buses_control.pipeline_log`
        WHERE archivo_nombre = @archivo
          AND estado = 'SUCCESS'
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("archivo", "STRING", archivo_nombre)
        ]
    )
    resultado = client.query(query, job_config=job_config).result()
    return next(iter(resultado)).n > 0


def registrar_log(
    project_id, archivo, fecha, estado, filas_ok, filas_ko, inicio, fin, error=None
):
    """Inserta una fila en pipeline_log con el resultado de la ejecución."""
    client = bigquery.Client(project=project_id)
    tabla = f"{project_id}.buses_control.pipeline_log"
    fila = [
        {
            "archivo_nombre": archivo,
            "fecha_datos": fecha,
            "estado": estado,
            "filas_procesadas": filas_ok,
            "filas_rechazadas": filas_ko,
            "inicio_proceso": inicio.isoformat(),
            "fin_proceso": fin.isoformat(),
            "mensaje_error": error,
        }
    ]
    errors = client.insert_rows_json(tabla, fila)
    if errors:
        log.warning(f"Error al escribir pipeline_log: {errors}")


# ---------------------------------------------------------------------------
# Función principal — lee en batches y ejecuta el pipeline Beam
# ---------------------------------------------------------------------------


def ejecutar_pipeline(project_id, bucket, archivo_gcs, region, temp_dir):
    """
    Lee el Parquet en batches de 50.000 filas para no saturar la RAM
    de Cloud Shell. Cada batch se procesa con un pipeline Beam independiente.
    """
    archivo_nombre = os.path.basename(archivo_gcs)
    fecha_str = archivo_nombre.replace("buses_", "").replace(".parquet", "")

    # --- Control de idempotencia ---
    if ya_fue_procesado(project_id, archivo_nombre):
        log.info(f"[SKIP] {archivo_nombre} ya fue procesado. Omitiendo.")
        return

    inicio = datetime.now(timezone.utc)
    log.info(f"[START] Procesando {archivo_nombre}")

    # --- Abrir Parquet como stream de batches (no carga todo en RAM) ---
    gcs_fs = pafs.GcsFileSystem()
    ruta_gcs = archivo_gcs.replace("gs://", "")
    pf = pq.ParquetFile(ruta_gcs, filesystem=gcs_fs)

    BATCH_SIZE = 50_000  # filas por batch — ajustar si hay OOM

    schema_validos = {
        "fields": [
            {"name": "patente", "type": "STRING"},
            {"name": "servicio", "type": "STRING"},
            {"name": "operador", "type": "INTEGER"},
            {"name": "direccion", "type": "STRING"},
            {"name": "latitud", "type": "FLOAT"},
            {"name": "longitud", "type": "FLOAT"},
            {"name": "velocidad", "type": "FLOAT"},
            {"name": "timestamp_gps", "type": "TIMESTAMP"},
            {"name": "timestamp_captura", "type": "TIMESTAMP"},
            {"name": "fecha_particion", "type": "DATE"},
            {"name": "hora_captura", "type": "INTEGER"},
            {"name": "dia_semana", "type": "STRING"},
            {"name": "es_hora_punta", "type": "BOOLEAN"},
            {"name": "latencia_segundos", "type": "FLOAT"},
            {"name": "velocidad_valida", "type": "BOOLEAN"},
            {"name": "gps_valido", "type": "BOOLEAN"},
            {"name": "archivo_origen", "type": "STRING"},
            {"name": "procesado_en", "type": "TIMESTAMP"},
        ]
    }
    schema_invalidos = {
        "fields": [
            {"name": "patente", "type": "STRING"},
            {"name": "latitud", "type": "FLOAT"},
            {"name": "longitud", "type": "FLOAT"},
            {"name": "velocidad", "type": "FLOAT"},
            {"name": "servicio", "type": "STRING"},
            {"name": "timestamp_gps", "type": "STRING"},
            {"name": "archivo_origen", "type": "STRING"},
            {"name": "motivo_rechazo", "type": "STRING"},
            {"name": "procesado_en", "type": "TIMESTAMP"},
        ]
    }

    opts = PipelineOptions(
        [
            f"--project={project_id}",
            f"--temp_location={temp_dir}",
            "--runner=DirectRunner",
            "--save_main_session",
        ]
    )

    filas_ok = 0
    filas_ko = 0
    error_msg = None
    estado = "SUCCESS"
    batch_num = 0

    try:
        for batch in pf.iter_batches(batch_size=BATCH_SIZE):
            batch_num += 1
            registros = batch.to_pylist()
            log.info(f"  Batch {batch_num}: {len(registros)} registros")

            with beam.Pipeline(options=opts) as p:
                resultados = (
                    p
                    | "Crear" >> beam.Create(registros)
                    | "Transformar"
                    >> beam.ParDo(TransformarRegistro(archivo_nombre)).with_outputs(
                        TransformarRegistro.OUTPUT_INVALIDO, main="validos"
                    )
                )
                resultados.validos | "Escribir validos" >> WriteToBigQuery(
                    table=f"{project_id}:buses_dw.bus_positions",
                    schema=schema_validos,
                    write_disposition=BigQueryDisposition.WRITE_APPEND,
                    create_disposition=BigQueryDisposition.CREATE_NEVER,
                )
                resultados.invalido | "Escribir invalidos" >> WriteToBigQuery(
                    table=f"{project_id}:buses_control.registros_invalidos",
                    schema=schema_invalidos,
                    write_disposition=BigQueryDisposition.WRITE_APPEND,
                    create_disposition=BigQueryDisposition.CREATE_NEVER,
                )

    except Exception as e:
        estado = "FAILED"
        error_msg = str(e)
        log.error(f"[ERROR] {archivo_nombre}: {e}")

    fin = datetime.now(timezone.utc)
    registrar_log(
        project_id,
        archivo_nombre,
        fecha_str,
        estado,
        filas_ok,
        filas_ko,
        inicio,
        fin,
        error_msg,
    )
    log.info(f"[DONE] {archivo_nombre} — {batch_num} batches procesados")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL Buses → BigQuery")
    parser.add_argument("--project", required=True, help="GCP Project ID")
    parser.add_argument("--bucket", required=True, help="Nombre del bucket GCS")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument(
        "--fechas",
        nargs="+",
        default=["2026-05-08", "2026-05-09", "2026-05-10"],
        help="Fechas a procesar (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    temp_dir = f"gs://{args.bucket}/temp/dataflow"

    for fecha in args.fechas:
        archivo_gcs = f"gs://{args.bucket}/raw/buses/date={fecha}/buses_{fecha}.parquet"
        log.info(f"=== Procesando fecha: {fecha} | Archivo: {archivo_gcs} ===")
        ejecutar_pipeline(args.project, args.bucket, archivo_gcs, args.region, temp_dir)

    log.info("=== Proceso finalizado para todas las fechas ===")
