import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import os
import contextily as cx
from pyproj import Transformer

def main():
    print("Loading data...")
    # Load the parquet file
    data_path = 'data/buses_2026-05-08.parquet'
    if not os.path.exists(data_path):
        print(f"Error: Data file {data_path} not found.")
        return
        
    df = pd.read_parquet(data_path)
    
    # 1. Filter out coordinates at (0, 0) and NaNs
    print("Filtering coordinates...")
    df_clean = df[(df['latitud'] != 0) & (df['longitud'] != 0)].dropna(subset=['latitud', 'longitud'])
    
    # Sort by timestamp to ensure chronological trajectories
    df_clean['timestamp_gps'] = pd.to_datetime(df_clean['timestamp_gps'], format='ISO8601', errors='coerce')
    df_clean = df_clean.sort_values(by=['patente', 'timestamp_gps'])

    print("Transforming coordinates to Web Mercator for map overlay...")
    # Transform coordinates from GPS (EPSG:4326) to Web Mercator (EPSG:3857)
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    df_clean['x'], df_clean['y'] = transformer.transform(df_clean['longitud'].values, df_clean['latitud'].values)

    fig, ax = plt.subplots(figsize=(12, 12))

    # Generate a dynamic colormap for operators
    operators = df_clean['operador'].dropna().unique()
    colors = plt.cm.tab20(np.linspace(0, 1, len(operators)))
    colormap = dict(zip(operators, colors))

    print("Plotting trajectories...")
    # 2. Plot trajectories grouped by bus (patente)
    for patente, traj in df_clean.groupby('patente'):
        if traj.empty or "operador" not in traj.columns:
            continue
            
        # Get operator for color mapping
        operator = traj["operador"].iloc[0]
        color = colormap.get(operator, "lightslategrey")
        
        # Plot trajectory line
        ax.plot(traj['x'].values, traj['y'].values, marker="None", linestyle="-", color=color, alpha=0.3, linewidth=0.5)
        # Plot end point
        ax.plot(traj['x'].values[-1], traj['y'].values[-1], marker=".", color="darkred", alpha=1, markersize=3, linestyle="None")

    # 3. Build legend based on operators
    legend_handles = [
        Line2D([0], [0], color=color, lw=2, label=str(op)) 
        for op, color in colormap.items()
    ]

    ax.legend(handles=legend_handles, title="Bus Operator", loc="lower left", 
              fontsize=8, title_fontsize=10, frameon=True)

    ax.set_title("Bus Trajectories by Operator")
    ax.axis('off')  # Hide coordinate axes for a clean map look

    print("Adding background map...")
    # Add the map background tiles
    cx.add_basemap(ax, source=cx.providers.CartoDB.Positron)
    
    output_img = "bus_trajectories.png"
    plt.savefig(output_img, dpi=300, bbox_inches='tight')
    print(f"Plot saved successfully as '{output_img}'")

if __name__ == "__main__":
    main()
