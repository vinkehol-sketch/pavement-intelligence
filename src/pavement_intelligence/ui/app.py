"""Panel Streamlit - Punto de Entrada Principal."""
import sys
from pathlib import Path
import streamlit as st

# Asegurar que 'src' esté en el path de Python
src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Configuración de página de Streamlit
st.set_page_config(page_title="Pavement Intelligence", layout="wide")

# Configurar navegación ordenada del MVP
pages = [
    st.Page("pages/home.py", title="Inicio", icon="🏠", default=True),
    st.Page("pages/traffic_monitoring.py", title="Monitoreo de tráfico", icon=":material/traffic:"),
    st.Page("pages/ocr_plate_review.py", title="Lecturas de placas", icon=":material/license:"),
    st.Page("pages/video_analysis.py", title="Análisis de video", icon="🎥"),
    st.Page("pages/traffic_review.py", title="Revisión del aforo automático", icon="🔍"),
    st.Page("pages/survey_tpda.py", title="Aforo y TPDA", icon="📊"),
    st.Page("pages/weighing.py", title="Pesaje", icon="⚖️"),
    st.Page("pages/esal_calculator.py", title="ESAL", icon="🔢"),
    st.Page("pages/soil_study.py", title="Estudio de suelo", icon="🌍"),
    st.Page("pages/aashto_sn.py", title="AASHTO 93 — SN requerido", icon=":material/calculate:"),
    st.Page("pages/layer_design.py", title="AASHTO 93 — Capas demostrativas", icon=":material/layers:"),
    st.Page("pages/pavement_design.py", title="Diseño de pavimento", icon="🛣️"),
    st.Page("pages/reports.py", title="Reportes", icon="📄"),
]

pg = st.navigation(pages)
pg.run()
