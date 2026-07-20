"""Panel Streamlit - Punto de Entrada Principal."""
import sys
from pathlib import Path
import streamlit as st

# Asegurar que 'src' esté en el path de Python
src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from pavement_intelligence.ui.utils.congestion_session import (  # noqa: E402
    clear_congestion_session,
)
from pavement_intelligence.ui.utils.uploaded_video import (  # noqa: E402
    UploadedVideoHandle,
    cleanup_uploaded_video,
)

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
if pg.url_path != "traffic_monitoring":
    controller = st.session_state.get("traffic_analysis_controller")
    if controller is not None:
        controller.close()
    handle = st.session_state.get("traffic_uploaded_video_handle")
    if isinstance(handle, UploadedVideoHandle):
        cleanup_uploaded_video(handle)
    st.session_state["traffic_analysis_controller"] = None
    st.session_state["traffic_analysis_running"] = False
    st.session_state["traffic_analysis_paused"] = False
    st.session_state["traffic_analysis_current_result"] = None
    st.session_state["traffic_analysis_batch_events"] = []
    st.session_state["traffic_analysis_source_metadata"] = None
    st.session_state["traffic_analysis_active_source_id"] = None
    st.session_state["traffic_uploaded_video_handle"] = None
    st.session_state["traffic_uploaded_video_hash"] = None
    st.session_state["traffic_uploaded_video_file_id"] = None
    st.session_state["traffic_uploaded_video_error"] = ""
    st.session_state["traffic_uploaded_video_cleanup_token"] = None
    clear_congestion_session(st.session_state)
pg.run()
