import pandas as pd
import matplotlib.pyplot as plt
import contextily as cx
import os
import subprocess
import shutil
import numpy as np

def create_animation(parquet_file, output_video, temp_dir="resources/frames"):
    print("Loading data...")
    df = pd.read_parquet(parquet_file)
    
    # Filter out invalid coordinates (0, 0)
    df = df[(df['latitud'] != 0) & (df['longitud'] != 0)]
    
    # Sort and set index by timestamp for easier time-based grouping
    df = df.sort_values("timestamp_captura")
    df.set_index("timestamp_captura", inplace=True)
    
    # Create temporary directory for frames
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    # Get bounding box for the static map
    min_lon, max_lon = df['longitud'].min(), df['longitud'].max()
    min_lat, max_lat = df['latitud'].min(), df['latitud'].max()
    
    # Resample data into 1-minute intervals to reduce frames and smooth animation
    freq = '1min'
    time_bins = df.resample(freq)
    
    # Pre-calculate colors for each unique operator
    import matplotlib.cm as cm
    unique_operators = sorted(df['operador'].unique())
    cmap = cm.get_cmap('tab20', len(unique_operators))
    operator_colors = {op: cmap(i) for i, op in enumerate(unique_operators)}
    
    print(f"Generating frames for {len(time_bins)} time intervals...")
    
    frame_count = 0
    for time, group in time_bins:
        if len(group) == 0:
            continue
            
        fig, ax = plt.subplots(figsize=(10, 10))
        
        # Plot buses for this time interval, grouped by operator to show a legend
        for op, op_group in group.groupby('operador'):
            ax.scatter(op_group['longitud'], op_group['latitud'], 
                       color=operator_colors[op], s=10, alpha=0.7, zorder=2, label=f"Op {op}")
        
        # Add legend outside the map area
        ax.legend(title="Operator", loc='center left', bbox_to_anchor=(1, 0.5), fontsize='small')
        
        # Set fixed limits so the map doesn't jump around
        ax.set_xlim(min_lon, max_lon)
        ax.set_ylim(min_lat, max_lat)
        
        # Add basemap
        # We specify crs="EPSG:4326" because the GPS coordinates are in WGS84
        try:
            cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.CartoDB.Positron)
        except Exception as e:
            print(f"Warning: Could not load basemap: {e}")
            pass
        
        # Formatting
        ax.set_title(f"Bus Positions - {time.strftime('%Y-%m-%d %H:%M:%S')} UTC", fontsize=14)
        ax.set_axis_off()
        
        # Save frame
        frame_filename = os.path.join(temp_dir, f"frame_{frame_count:04d}.png")
        plt.savefig(frame_filename, bbox_inches='tight', dpi=100)
        plt.close(fig)
        
        if frame_count % 10 == 0:
            print(f"Generated {frame_count} frames...")
            
        frame_count += 1
        
    print(f"Finished generating {frame_count} frames.")
    
    # Compile video using ffmpeg
    print("Compiling video with ffmpeg...")
    try:
        ffmpeg_cmd = [
            "ffmpeg",
            "-y", # Overwrite output file if it exists
            "-framerate", "10", # 10 frames per second
            "-i", os.path.join(temp_dir, "frame_%04d.png"),
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_video
        ]
        subprocess.run(ffmpeg_cmd, check=True)
        print(f"Animation successfully saved to {output_video}")
    except subprocess.CalledProcessError as e:
        print(f"Error running ffmpeg: {e}")
    finally:
        # Clean up
        print("Cleaning up temporary frames...")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    create_animation(
        parquet_file="data/buses_2026-05-08.parquet",
        output_video="resources/bus_animation.mp4"
    )
