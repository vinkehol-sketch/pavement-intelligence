"""Página de Streamlit para el flujo de visión con calibración manual."""
import os
import time
import json
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st

from pavement_intelligence.vision.detection.yolo_detector import YOLODetectorTracker
from pavement_intelligence.vision.pipeline import VisionPipeline, export_corrected_records

st.set_page_config(page_title="Análisis de Video", layout="wide")
st.title("🎥 Análisis de Tráfico por Video")
st.info("Procesamiento secuencial con línea virtual configurable, diagnóstico y corrección manual del aforo.")

if "processing_done" not in st.session_state:
    st.session_state.processing_done = False
if "events" not in st.session_state:
    st.session_state.events = []
if "corrected_records" not in st.session_state:
    st.session_state.corrected_records = []

st.sidebar.header("Configuración del Modelo")
model_path = st.sidebar.text_input("Ruta del Modelo YOLO", "data/models/yolov8n.pt")
device = st.sidebar.selectbox("Dispositivo", ["cpu", "cuda", "mps"], index=0)
conf_thresh = st.sidebar.slider("Confianza Mínima", 0.1, 1.0, 0.45, 0.05)
image_size = st.sidebar.selectbox("Tamaño de Inferencia", [640, 960], index=0)
allowed_classes = st.sidebar.multiselect(
    "Clases Admitidas",
    ["car", "motorcycle", "bus", "truck"],
    default=["car", "motorcycle", "bus", "truck"],
)

st.sidebar.header("ByteTrack")
tracker_config = st.sidebar.selectbox("Configuración", ["predeterminada", "mayor_persistencia"], index=0)

tolerance = st.sidebar.slider("Tolerancia / Banda Muerta", 0.0, 20.0, 3.0, 0.5)
cooldown_frames = st.sidebar.slider("Cooldown para Oscilaciones", 1, 15, 3)

st.sidebar.header("Línea Virtual")
preset = st.sidebar.selectbox("Preset", ["horizontal", "vertical", "inclinado", "manual"], index=0)
if preset == "horizontal":
    line_points = ((100, 360), (1180, 360))
elif preset == "vertical":
    line_points = ((640, 80), (640, 720))
elif preset == "inclinado":
    line_points = ((200, 180), (980, 520))
else:
    line_points = ((100, 360), (1180, 360))

x1 = st.sidebar.number_input("Punto 1 - X", value=line_points[0][0])
y1 = st.sidebar.number_input("Punto 1 - Y", value=line_points[0][1])
x2 = st.sidebar.number_input("Punto 2 - X", value=line_points[1][0])
y2 = st.sidebar.number_input("Punto 2 - Y", value=line_points[1][1])

uploaded_file = st.file_uploader("Sube un video de tráfico (MP4, AVI)", type=["mp4", "avi", "mov"])

if uploaded_file is not None:
    st.subheader("Fotograma de Referencia")
    temp_dir = Path("data/videos/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / uploaded_file.name
    with open(temp_path, "wb") as handle:
        handle.write(uploaded_file.getbuffer())
    cap_ref = cv2.VideoCapture(str(temp_path))
    if cap_ref.isOpened():
        ok, frame_ref = cap_ref.read()
        if ok:
            frame_ref = cv2.resize(frame_ref, (960, 540))
            cv2.line(frame_ref, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 255), 2)
            rgb_ref = cv2.cvtColor(frame_ref, cv2.COLOR_BGR2RGB)
            st.image(rgb_ref, channels="RGB")
        cap_ref.release()

    if st.button("▶️ Procesar Video", type="primary"):
        st.session_state.processing_done = False
        st.session_state.events = []
        st.session_state.corrected_records = []

        cap = cv2.VideoCapture(str(temp_path))
        if not cap.isOpened():
            st.error("No se pudo abrir el archivo de video. Verifica el formato.")
            st.stop()

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        st.write(f"**Resolución:** {width}x{height} | **FPS:** {fps} | **Fotogramas:** {total_frames}")

        try:
            detector = YOLODetectorTracker(
                model_path=model_path,
                device=device,
                conf_threshold=conf_thresh,
                image_size=image_size,
                allowed_classes=allowed_classes,
                tracker_config=tracker_config,
            )
            pipeline = VisionPipeline(
                detector,
                (x1, y1),
                (x2, y2),
                tolerance=tolerance,
                cooldown_frames=cooldown_frames,
            )
        except Exception as exc:
            st.error(f"Error al inicializar YOLO: {exc}")
            cap.release()
            st.stop()

        out_path = temp_dir / f"processed_{uploaded_file.name}"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_video = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))

        progress_bar = st.progress(0)
        status_text = st.empty()
        frame_window = st.image([])
        metrics_col1, metrics_col2 = st.columns(2)
        metric_total = metrics_col1.empty()
        metric_time = metrics_col2.empty()

        frame_count = 0
        start_time = time.time()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            processed_frame, new_events = pipeline.process_frame(frame, frame_count, fps, uploaded_file.name)
            out_video.write(processed_frame)
            if frame_count % 5 == 0 or frame_count == total_frames:
                rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                frame_window.image(rgb_frame, channels="RGB")
                progress = min(1.0, frame_count / total_frames) if total_frames > 0 else 0
                progress_bar.progress(progress)
                elapsed = time.time() - start_time
                status_text.text(f"Procesando: {frame_count}/{total_frames} ({(progress*100):.1f}%)")
                metric_total.metric("Total Vehículos Contados", len(pipeline.events))
                metric_time.metric("Tiempo Transcurrido", f"{elapsed:.1f} s")

        cap.release()
        out_video.release()
        cv2.destroyAllWindows()

        st.session_state.events = pipeline.events
        st.session_state.corrected_records = [
            {
                "event_id": event.event_id,
                "track_id": event.track_id,
                "category": event.category,
                "direction": event.direction,
                "source": event.source,
                "status": "AUTOMATICO",
                "notes": "",
            }
            for event in pipeline.events
        ]
        st.session_state.processing_done = True
        st.session_state.out_video_path = out_path
        st.success("¡Procesamiento completado!")

if st.session_state.get("processing_done", False):
    st.header("Resultados")
    events = st.session_state.events
    if not events:
        st.warning("No se detectó ningún cruce de línea.")
    else:
        df = pd.DataFrame([e.to_dict() for e in events])
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Por Categoría")
            st.dataframe(df['category'].value_counts().reset_index())
        with col2:
            st.subheader("Por Sentido")
            st.dataframe(df['direction'].value_counts().reset_index())

        st.subheader("Registros Detallados")
        st.dataframe(df)

        st.subheader("Corrección Manual del Aforo")
        corrected_df = pd.DataFrame(st.session_state.corrected_records)
        edited_df = st.data_editor(
            corrected_df,
            column_config={
                "category": st.column_config.SelectboxColumn("Categoría", options=["AUTO", "MOTO", "BUS", "CAMION", "DESCONOCIDO"]),
                "direction": st.column_config.SelectboxColumn("Dirección", options=[-1, 1]),
                "status": st.column_config.SelectboxColumn("Estado", options=["AUTOMATICO", "CORREGIDO_MANUALMENTE", "AGREGADO_MANUALMENTE"]),
                "notes": st.column_config.TextColumn("Observaciones"),
            },
            disabled=["event_id", "track_id", "source"],
            hide_index=True,
            use_container_width=True,
        )
        st.session_state.corrected_records = edited_df.to_dict(orient="records")

        if st.button("Exportar Registros Corregidos"):
            export_dir = Path("data/processed/reports")
            export_result = export_corrected_records(st.session_state.corrected_records, export_dir)
            st.success(f"Archivos exportados en {export_dir}")
            st.code(json.dumps(export_result, indent=2))

        csv = df.to_csv(index=False).encode('utf-8')
        json_data = json.dumps([e.to_dict() for e in events], indent=4)
        dl_col1, dl_col2, dl_col3 = st.columns(3)
        dl_col1.download_button("Descargar CSV Automático", data=csv, file_name="conteo.csv", mime="text/csv")
        dl_col2.download_button("Descargar JSON Automático", data=json_data, file_name="conteo.json", mime="application/json")
        out_path = st.session_state.get("out_video_path")
        if out_path and os.path.exists(out_path):
            with open(out_path, "rb") as handle:
                dl_col3.download_button("Descargar Video Procesado", data=handle, file_name=out_path.name, mime="video/mp4")
