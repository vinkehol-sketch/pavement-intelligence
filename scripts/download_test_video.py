import urllib.request
import os
from pathlib import Path
import sys

def download_video(url: str, filename: str):
    DEST_DIR = Path("data/videos/samples")
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = DEST_DIR / filename
    
    if dest_path.exists():
        print(f"El video {filename} ya existe en {dest_path}")
        return str(dest_path)
        
    print(f"Descargando video desde {url}...")
    try:
        urllib.request.urlretrieve(url, dest_path)
        print(f"Video descargado exitosamente en {dest_path}")
        return str(dest_path)
    except Exception as e:
        print(f"Error al descargar: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 2:
        download_video(sys.argv[1], sys.argv[2])
    else:
        print("Uso: python download.py <url> <filename>")
