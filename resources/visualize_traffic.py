import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import contextily as cx
from pyproj import Transformer

def main():
    print("Loading data...")
    data_path = 'data/buses_2026-05-08.parquet'
    if not os.path.exists(data_path):
        print(f"Error: Data file {data_path} not found.")
        return
        
    df = pd.read_parquet(data_path)
    
    print("Filtering data...")
    # 1. Clean invalid coordinates and NaNs
    df = df[(df['latitud'] != 0) & (df['longitud'] != 0)].dropna(subset=['latitud', 'longitud', 'velocidad'])
    
    # Remove extreme geographical outliers (top/bottom 1%) to keep the map focused on the main city area
    lat_min, lat_max = df['latitud'].quantile(0.01), df['latitud'].quantile(0.99)
    lon_min, lon_max = df['longitud'].quantile(0.01), df['longitud'].quantile(0.99)
    
    df = df[(df['latitud'] >= lat_min) & (df['latitud'] <= lat_max) &
            (df['longitud'] >= lon_min) & (df['longitud'] <= lon_max)]

    print("Transforming coordinates to Web Mercator for map overlay...")
    # Transform coordinates from GPS (EPSG:4326) to Web Mercator (EPSG:3857)
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    df['x'], df['y'] = transformer.transform(df['longitud'].values, df['latitud'].values)

    print(f"Data ready: {len(df):,} rows.")

    # =====================================================================
    # Visualization A: Hexbin Map of Average Speed over a Basemap
    # =====================================================================
    print("Generating Visualization A: Average Speed Hexbin Map...")
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Filter out buses that are completely stopped (likely parked/at terminals) to get a true moving average
    df_moving = df[df['velocidad'] >= 2]
    
    # Create hexbin plot using x, y
    hb = ax.hexbin(df_moving['x'], df_moving['y'], C=df_moving['velocidad'], 
                   gridsize=120, cmap='RdYlGn', reduce_C_function=np.mean, 
                   mincnt=5, alpha=0.75, edgecolors='none')
    
    plt.colorbar(hb, ax=ax, label='Average Speed (km/h)')
    ax.set_title('Average Bus Speed by Zone (Red = Slow/Traffic, Green = Fast)')
    ax.axis('off') # Hide axes ticks since Web Mercator coordinates are just large numbers
    
    # Add the map background
    cx.add_basemap(ax, source=cx.providers.CartoDB.Positron)
    
    out_a = 'traffic_hexbin_map.png'
    plt.savefig(out_a, dpi=300, bbox_inches='tight')
    print(f"Saved {out_a}")
    plt.close()

    # =====================================================================
    # Visualization B: Density of "Slow" moving buses (2 to 15 km/h) over Basemap
    # =====================================================================
    print("Generating Visualization B: Traffic Density Heatmap...")
    # Filter for speeds indicating slow traffic (excluding 0-2 km/h stops)
    df_slow = df[(df['velocidad'] >= 2) & (df['velocidad'] <= 15)]
    
    fig, ax = plt.subplots(figsize=(12, 10))
    # Using hist2d for high performance on large datasets. 
    h = ax.hist2d(df_slow['x'], df_slow['y'], bins=150, cmap='inferno', cmin=10, alpha=0.6)
    
    plt.colorbar(h[3], ax=ax, label='Number of Slow Reports (Congestion Intensity)')
    ax.set_title('Traffic Density Heatmap (Concentration of Speeds 2-15 km/h)')
    ax.axis('off')
    
    # Add the map background
    cx.add_basemap(ax, source=cx.providers.CartoDB.Positron)
    
    out_b = 'traffic_density_heatmap.png'
    plt.savefig(out_b, dpi=300, bbox_inches='tight')
    print(f"Saved {out_b}")
    plt.close()

    print("Done!")

if __name__ == "__main__":
    main()
