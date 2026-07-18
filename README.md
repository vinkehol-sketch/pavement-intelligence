# Pavement Intelligence — Plataforma de Análisis de Tránsito y Diseño de Pavimentos

## Descripción

Plataforma modular para el análisis de tránsito vehicular y el diseño estructural
de pavimentos.

## Tecnologías

- Python 3.10+
- YOLOv8 y ByteTrack
- SQLite y Streamlit
- Pandas, NumPy y Plotly
- PaddleOCR (integración opcional; requiere instalación adicional)

## Instalación en PowerShell

```powershell
python -m venv .venv
& '.\.venv\Scripts\Activate.ps1'
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
Copy-Item '.env.example' '.env'
```

Los pesos YOLO deben existir en `data/models/`. Los videos de prueba están en
`data/videos/samples/`.

## Uso rápido

```powershell
python -m pytest -v
python -m streamlit run src\pavement_intelligence\ui\app.py
python scripts\run_headless_vision.py --video data\videos\samples\car-detection.mp4 --prefix demo
```

El repositorio actual no contiene un servidor FastAPI ni un descargador
automático de modelos.
