import os
import requests

def download_file_from_dropbox(url, destination):
    # Ensure the URL is set up for direct download
    direct_download_url = url.replace("dl=0", "dl=1")
    
    print(f"Descargando datos desde Dropbox...")
    print("Esto puede tardar un momento dependiendo de tu conexión (aprox. 15 MB).")
    
    try:
        response = requests.get(direct_download_url, stream=True)
        response.raise_for_status() # Check for request errors
        
        # Ensure the destination directory exists
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        print(f"¡Descarga completada con éxito! Archivo guardado en: {destination}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar el archivo: {e}")

if __name__ == "__main__":
    FILES_TO_DOWNLOAD = [
        {
            "url": "https://www.dropbox.com/scl/fi/qn1g0s829dol4zu6p5gfh/buses_2026-05-08.parquet?rlkey=1q64fcvqrx6bkbzypqh0ywnro&st=rtfbkfzt&dl=0",
            "destination": "data/buses_2026-05-08.parquet"
        },
        {
            "url": "https://www.dropbox.com/scl/fi/wpebtr0gxkzulfv2xlqd0/buses_2026-05-09.parquet?rlkey=p4vnwwrhs5pwt0eovk4f0ebpe&st=19sjym4s&dl=0",
            "destination": "data/buses_2026-05-09.parquet"
        }
    ]
    
    for file_info in FILES_TO_DOWNLOAD:
        download_file_from_dropbox(file_info["url"], file_info["destination"])
        print("-" * 40)
