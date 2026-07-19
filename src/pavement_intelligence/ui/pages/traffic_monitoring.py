"""Centro de monitoreo de tráfico con datos exclusivamente simulados."""
from __future__ import annotations

import csv
import datetime
import io
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from pavement_intelligence.domain.traffic.presentation import DashboardOperationalState
from pavement_intelligence.integration.traffic_event_adapter import build_traffic_event_batch
from pavement_intelligence.ui.utils.demo_data import PROJECT_ROOT, load_demo_dashboard, validate_dashboard_state
from pavement_intelligence.ui.utils.demo_video import (
    advance_frame,
    compute_demo_metrics,
    frame_to_rgb,
    initialize_demo_playback,
    inspect_video,
    playback_progress,
    read_frame,
    reset_demo_playback,
)
from pavement_intelligence.ui.utils.formatting import format_unit
from pavement_intelligence.ui.utils.styles import load_dashboard_css, render_status_chip
from pavement_intelligence.ui.utils.traffic_analysis_state import prepare_session_for_real_analysis
from pavement_intelligence.vision.analysis import AnalysisState, TrafficAnalysisController
from pavement_intelligence.vision.capture import CameraSource, VideoFileSource
from pavement_intelligence.vision.detection.yolo_detector import YOLODetectorTracker
from pavement_intelligence.vision.pipeline import VisionPipeline

st.set_page_config(page_title="Centro de monitoreo de tráfico", page_icon=":material/traffic:", layout="wide")
load_dashboard_css()

MONITORING_FRAME = PROJECT_ROOT / "data" / "samples" / "ui" / "assets" / "traffic_monitoring_urban_avenue.png"
DEMO_VIDEO = PROJECT_ROOT / "data" / "samples" / "ui" / "assets" / "traffic_monitoring_demo.mp4"
STATIC_MODE = "Imagen demostrativa"
VIDEO_MODE = "Video pregrabado"
CAMERA_MODE = "Cámara en vivo"
MODEL_PATH = PROJECT_ROOT / "data" / "models" / "yolov8n.pt"


@st.cache_data(max_entries=1)
def _load_state():
    return load_demo_dashboard()


@st.cache_data(max_entries=2)
def _inspect_video(path: str):
    return inspect_video(path)


def _export_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["origen", "categoría", "conteo"])
    for item in state.categories:
        writer.writerow(["SYNTHETIC_UI_DEMO", item.label, item.count])
    return buffer.getvalue().encode("utf-8-sig")


def _play() -> None:
    st.session_state["traffic_demo_playing"] = True
    st.session_state["traffic_demo_last_update"] = time.monotonic()
    st.session_state["traffic_monitor_state"] = DashboardOperationalState.PROCESSING_ACTIVE.value


def _pause() -> None:
    st.session_state["traffic_demo_playing"] = False
    st.session_state["traffic_monitor_state"] = DashboardOperationalState.PROCESSING_PAUSED.value


def _restart() -> None:
    reset_demo_playback(st.session_state, last_update=time.monotonic())
    st.session_state["traffic_monitor_state"] = DashboardOperationalState.PROCESSING_ACTIVE.value


def _format_clock(seconds: float) -> str:
    seconds = max(0, round(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _close_real_controller() -> None:
    controller = st.session_state.get("traffic_analysis_controller")
    if controller is not None:
        controller.close()
    st.session_state["traffic_analysis_controller"] = None
    st.session_state["traffic_analysis_running"] = False
    st.session_state["traffic_analysis_paused"] = False


def _pipeline_factory(source):
    def create_pipeline() -> VisionPipeline:
        info = source.source_info()
        width, height = info.width, info.height
        line_y = max(1, height // 2)
        detector = YOLODetectorTracker(
            model_path=str(MODEL_PATH), device="cpu", conf_threshold=0.45,
            image_size=640, allowed_classes=["car", "motorcycle", "bus", "truck"],
            tracker_config="default",
        )
        return VisionPipeline(detector, (0, line_y), (max(1, width - 1), line_y), tolerance=3.0)

    return create_pipeline


def _start_real_analysis(source_mode: str, camera_index: int) -> None:
    _close_real_controller()
    prepare_session_for_real_analysis(st.session_state)
    try:
        if source_mode == VIDEO_MODE:
            source = VideoFileSource(DEMO_VIDEO)
        else:
            source = CameraSource(camera_index)
        controller = TrafficAnalysisController(source, _pipeline_factory(source))
        metadata = controller.start()
        st.session_state["traffic_analysis_controller"] = controller
        st.session_state["traffic_analysis_running"] = True
        st.session_state["traffic_analysis_paused"] = False
        st.session_state["traffic_analysis_current_result"] = None
        st.session_state["traffic_analysis_batch_events"] = []
        st.session_state["traffic_analysis_error"] = ""
        st.session_state["traffic_analysis_source_metadata"] = metadata
    except Exception as exc:
        _close_real_controller()
        st.session_state["traffic_analysis_error"] = str(exc)


def _finish_for_review(controller: TrafficAnalysisController) -> None:
    events = controller.finish()
    now = datetime.datetime.now().isoformat()
    source_info = st.session_state.get("traffic_analysis_source_metadata")
    source_name = source_info.source_id if source_info else "fuente_local"
    line_y = (source_info.height // 2) if source_info else 360
    batch = build_traffic_event_batch(events, {
        "model_name": MODEL_PATH.name,
        "line_id": "monitoring_center_line",
        "line_y": line_y,
        "source_video": source_name,
        "processing_date": now,
        "configuration_version": "monitoring-real-v1",
    })
    st.session_state["vision_events_raw"] = [event.to_dict() for event in events]
    st.session_state["vision_events_reviewed"] = batch["events"]
    st.session_state["vision_batch_metadata"] = batch["metadata"]
    st.session_state["traffic_review_approved"] = False
    st.session_state["traffic_counts_corrected"] = {}
    st.session_state["is_synthetic_review"] = False
    st.session_state["traffic_review_source_fingerprint"] = f"real:{source_name}:{now}"
    st.session_state["traffic_analysis_batch_events"] = list(events)
    st.session_state["traffic_analysis_running"] = False


state = _load_state()
issues = validate_dashboard_state(state)
if issues:
    for issue in issues:
        st.error(issue, icon=":material/error:")
    st.stop()

initialize_demo_playback(st.session_state, DEMO_VIDEO)
st.session_state.setdefault("traffic_analysis_controller", None)
st.session_state.setdefault("traffic_analysis_running", False)
st.session_state.setdefault("traffic_analysis_paused", False)
st.session_state.setdefault("traffic_analysis_current_result", None)
st.session_state.setdefault("traffic_analysis_batch_events", [])
st.session_state.setdefault("traffic_analysis_error", "")
st.session_state.setdefault("traffic_analysis_source_metadata", None)
st.session_state.setdefault("traffic_analysis_source_type", STATIC_MODE)

title_col, action_col = st.columns([7, 4], vertical_alignment="bottom")
with title_col:
    st.title("Centro de monitoreo de tráfico")
    st.caption("Supervisión operativa del flujo vehicular y del estado del lote en tiempo casi real.")
    st.caption(
        f":material/location_on: {state.source.point_name}  ·  "
        f":material/videocam: Fuente: {state.source.label}  ·  "
        f":material/swap_horiz: Dirección: {state.source.configured_direction}"
    )
with action_col:
    st.markdown(render_status_chip("Modo demostración", "info"), unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
        if st.button("Revisar conteo", icon=":material/fact_check:", width="content"):
            st.switch_page("pages/traffic_review.py")
        st.download_button(
            "Exportar datos", data=_export_csv(), file_name="monitoreo_demo.csv",
            mime="text/csv", icon=":material/download:", type="primary", width="content",
        )

mode = st.segmented_control(
    "Fuente de análisis",
    [STATIC_MODE, VIDEO_MODE, CAMERA_MODE],
    key="traffic_analysis_source_type",
    selection_mode="single",
)
mode = mode or STATIC_MODE
previous_mode = st.session_state.get("traffic_analysis_active_mode", STATIC_MODE)
if mode != previous_mode:
    reset_demo_playback(st.session_state, last_update=time.monotonic())
    _close_real_controller()
    st.session_state["traffic_analysis_error"] = ""
st.session_state["traffic_analysis_active_mode"] = mode


@st.fragment(run_every=0.15 if mode == STATIC_MODE and st.session_state["traffic_demo_playing"] else None)
def _render_monitoring_dashboard() -> None:
    video_info = None
    video_error = ""
    if mode == STATIC_MODE and st.session_state["traffic_demo_playing"]:
        try:
            video_info = _inspect_video(str(DEMO_VIDEO))
            st.session_state["traffic_demo_total_frames"] = video_info.total_frames
            st.session_state["traffic_demo_fps"] = video_info.fps
            if st.session_state["traffic_demo_playing"]:
                frame_index, updated_at, still_playing = advance_frame(
                    int(st.session_state["traffic_demo_frame_index"]),
                    video_info.total_frames,
                    video_info.fps,
                    float(st.session_state["traffic_demo_last_update"]),
                    time.monotonic(),
                    loop=bool(st.session_state["traffic_demo_loop"]),
                )
                st.session_state["traffic_demo_frame_index"] = frame_index
                st.session_state["traffic_demo_last_update"] = updated_at
                st.session_state["traffic_demo_playing"] = still_playing
        except (FileNotFoundError, ValueError) as exc:
            video_error = str(exc)
            st.session_state["traffic_demo_error"] = video_error
            st.session_state["traffic_demo_playing"] = False

    progress = playback_progress(
        int(st.session_state["traffic_demo_frame_index"]),
        int(st.session_state["traffic_demo_total_frames"]),
    ) if mode == STATIC_MODE and video_info else 0.0
    demo_metrics = compute_demo_metrics(progress)

    main_col, side_col = st.columns([9, 3], gap="medium")
    with main_col:
        with st.container(border=True, gap="small"):
            header_left, header_right = st.columns([2, 3], vertical_alignment="center")
            header_left.markdown("**:material/videocam: Conteo automático simulado**")
            badges = render_status_chip("MÉTRICAS SIMULADAS", "info")
            badges = render_status_chip("DEMOSTRACIÓN SINTÉTICA", "success") + " " + badges
            header_right.markdown(badges, unsafe_allow_html=True)

            displayed_video = False
            if displayed_video:
                try:
                    image = frame_to_rgb(read_frame(DEMO_VIDEO, int(st.session_state["traffic_demo_frame_index"])))
                    st.image(image, width="stretch")
                except ValueError as exc:
                    video_error = str(exc)
                    st.session_state["traffic_demo_error"] = video_error
                    st.session_state["traffic_demo_playing"] = False
                    displayed_video = False
            if not displayed_video:
                if video_error:
                    st.error(f"{video_error} Se muestra la imagen demostrativa segura.", icon=":material/video_file:")
                if MONITORING_FRAME.is_file():
                    st.image(str(MONITORING_FRAME), width="stretch")
                else:
                    st.warning("No se encontró el fotograma demostrativo.", icon=":material/image_not_supported:")

            if displayed_video and video_info:
                elapsed = int(st.session_state["traffic_demo_frame_index"]) / video_info.fps
                st.progress(progress, text=f"Fotograma {int(st.session_state['traffic_demo_frame_index']) + 1} de {video_info.total_frames}")
                st.caption(
                    f"{_format_clock(elapsed)} / {_format_clock(video_info.duration_seconds)} · "
                    f"{video_info.fps:.1f} FPS fuente · {video_info.resolution}"
                )
            else:
                st.caption("Fotograma urbano demostrativo con overlays preprocesados; no ejecuta YOLO ni ByteTrack.")

            controls_disabled = True
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                st.button(
                    "Reproducir", icon=":material/play_arrow:", key="monitor_play",
                    width="content", disabled=controls_disabled or bool(st.session_state["traffic_demo_playing"]),
                    on_click=_play,
                )
                st.button(
                    "Pausar", icon=":material/pause:", key="monitor_pause",
                    width="content", disabled=controls_disabled or not bool(st.session_state["traffic_demo_playing"]),
                    on_click=_pause,
                )
                st.button(
                    "Reiniciar", icon=":material/replay:", key="monitor_replay",
                    width="content", disabled=controls_disabled, on_click=_restart,
                )

        st.caption("Métricas demostrativas, no calculadas desde el video.")
        st.markdown("**Clasificación vehicular** · Total acumulado")
        category_cols = st.columns(5, gap="small")
        for index, (column, category) in enumerate(zip(category_cols, state.categories)):
            count = demo_metrics.category_counts[index] if mode == VIDEO_MODE else category.count
            column.metric(category.label, f"{count:,}", f"{category.trend_percent:+.1f}%", border=True)

        direction_values = demo_metrics.direction_counts if mode == VIDEO_MODE else tuple(item.count for item in state.directions)
        direction_cols = st.columns(3, gap="small")
        for column, direction, count in zip(direction_cols, state.directions, direction_values):
            column.metric(direction.label, f"{count:,}", border=True)
        direction_cols[2].metric("Total", f"{sum(direction_values):,}", border=True)

        with st.container(border=True, gap="small"):
            st.markdown("**Flujo vehicular** · Ambos sentidos (veh/min)")
            flow_df = pd.DataFrame(state.time_series).set_index("time")
            st.line_chart(flow_df, x_label="Hora", y_label="veh/min", color=["#1A56DB", "#CA8A04"], height=230)

    with side_col:
        with st.container(border=True, gap="small"):
            st.markdown("**Estado actual**")
            congestion_label = demo_metrics.congestion if mode == VIDEO_MODE else state.congestion.label
            chip_col, lot_col = st.columns([3, 2], vertical_alignment="center")
            chip_col.markdown(render_status_chip(congestion_label, "warning"), unsafe_allow_html=True)
            lot_col.markdown(render_status_chip(state.review.label, "warning"), unsafe_allow_html=True)
            status_left, status_right = st.columns(2, gap="small")
            flow = demo_metrics.flow_veh_min if mode == VIDEO_MODE else state.metrics.current_flow_veh_min
            in_scene = demo_metrics.vehicles_in_scene if mode == VIDEO_MODE else state.metrics.vehicles_in_scene
            status_left.metric("Flujo", format_unit(flow, "veh/min"), border=True)
            status_right.metric("Velocidad", format_unit(state.metrics.average_speed_kmh, "km/h"), border=True)
            status_left.metric("Ocupación est.", format_unit(state.metrics.visual_occupancy_percent, "%"), border=True)
            status_right.metric("En escena", f"{in_scene:,}", border=True)
            st.metric("Total acumulado", f"{sum(direction_values):,}", border=True)

        with st.container(border=True, gap="small"):
            st.markdown("**Reconocimiento de placas** :blue-badge[Experimental]")
            ocr_left, ocr_mid, ocr_right = st.columns(3, gap="small")
            ocr_left.metric("Detectadas", state.ocr.detected)
            ocr_mid.metric("Válidas", state.ocr.valid)
            ocr_right.metric("Pendientes", state.ocr.pending)
            doubtful_col, confidence_col = st.columns(2, gap="small")
            doubtful_col.metric("Dudosas", state.ocr.doubtful)
            confidence_col.metric("Confianza", format_unit(state.ocr.average_confidence_percent, "%"))
            if st.button("Ver lecturas", icon=":material/visibility:", width="stretch"):
                st.switch_page("pages/ocr_plate_review.py")

        with st.container(border=True, gap="small"):
            st.markdown("**Alertas recientes**")
            visible_alerts = state.alerts if mode == STATIC_MODE else state.alerts[:demo_metrics.alert_count]
            if visible_alerts:
                alert_df = pd.DataFrame([vars(item) for item in visible_alerts]).rename(columns={
                    "time": "Hora", "alert_type": "Tipo", "description": "Descripción",
                    "level": "Nivel", "status": "Estado",
                })
                st.dataframe(alert_df[["Hora", "Tipo", "Nivel", "Estado"]], hide_index=True, height=145)
                with st.expander("Ver descripción de alertas"):
                    for alert in visible_alerts:
                        st.caption(f"**{alert.time} · {alert.alert_type}:** {alert.description}")
            else:
                st.info("Sin alertas simuladas en este punto del video.", icon=":material/check_circle:")


def _render_real_analysis(source_mode: str) -> None:
    st.markdown(
        render_status_chip(
            "ANÁLISIS REAL DE VIDEO" if source_mode == VIDEO_MODE else "CÁMARA EN VIVO",
            "success",
        ),
        unsafe_allow_html=True,
    )
    camera_index = 0
    if source_mode == VIDEO_MODE:
        st.selectbox(
            "Video local",
            [str(DEMO_VIDEO.relative_to(PROJECT_ROOT))],
            key="traffic_analysis_video_selection",
            help="Solo se muestran videos locales validados dentro del proyecto.",
        )
        try:
            selected_info = _inspect_video(str(DEMO_VIDEO))
            st.caption(
                f"{selected_info.resolution} · {selected_info.fps:.1f} FPS · "
                f"{selected_info.total_frames} fotogramas · {_format_clock(selected_info.duration_seconds)}"
            )
        except (FileNotFoundError, ValueError) as exc:
            st.error(str(exc), icon=":material/video_file:")
    else:
        camera_index = st.selectbox("Índice de cámara local", [0, 1], key="traffic_analysis_camera_index")
        st.caption("La cámara solo se abre mediante acción explícita y se libera al detener o finalizar.")

    controller = st.session_state.get("traffic_analysis_controller")
    running = controller is not None and controller.state is AnalysisState.RUNNING
    paused = controller is not None and controller.state is AnalysisState.PAUSED
    with st.container(horizontal=True, gap="small"):
        start_label = "Iniciar análisis" if source_mode == VIDEO_MODE else "Iniciar cámara"
        if st.button(start_label, icon=":material/play_arrow:", type="primary", disabled=controller is not None):
            with st.spinner("Inicializando YOLOv8 y ByteTrack…"):
                _start_real_analysis(source_mode, int(camera_index))
            st.rerun()
        if st.button("Pausar", icon=":material/pause:", disabled=not running, key="real_pause"):
            controller.pause()
            st.session_state["traffic_analysis_running"] = False
            st.session_state["traffic_analysis_paused"] = True
            st.rerun()
        if st.button("Continuar", icon=":material/resume:", disabled=not paused, key="real_resume"):
            controller.resume()
            st.session_state["traffic_analysis_running"] = True
            st.session_state["traffic_analysis_paused"] = False
            st.rerun()
        if st.button("Reiniciar", icon=":material/replay:", disabled=controller is None, key="real_reset"):
            controller.reset()
            st.session_state["traffic_analysis_current_result"] = None
            st.session_state["traffic_analysis_running"] = True
            st.session_state["traffic_analysis_paused"] = False
            st.rerun()
        stop_label = "Detener cámara" if source_mode == CAMERA_MODE else "Finalizar análisis"
        if st.button(stop_label, icon=":material/stop_circle:", disabled=controller is None, key="real_stop"):
            controller.finish()
            st.session_state["traffic_analysis_running"] = False
            st.rerun()

    if st.session_state["traffic_analysis_error"]:
        st.error(st.session_state["traffic_analysis_error"], icon=":material/error:")
        if MONITORING_FRAME.is_file():
            st.image(str(MONITORING_FRAME), width="stretch")

    @st.fragment(run_every=0.15 if running else None)
    def _real_frame_fragment() -> None:
        active_controller = st.session_state.get("traffic_analysis_controller")
        if active_controller is None:
            if not st.session_state["traffic_analysis_error"] and MONITORING_FRAME.is_file():
                st.image(str(MONITORING_FRAME), width="stretch")
                st.info("Selecciona una fuente e inicia el análisis explícitamente.")
            return
        result = active_controller.process_next() if active_controller.state is AnalysisState.RUNNING else active_controller.last_result
        st.session_state["traffic_analysis_current_result"] = result
        if result is None:
            return
        if result.annotated_frame is not None:
            st.image(frame_to_rgb(result.annotated_frame), width="stretch")
        elif MONITORING_FRAME.is_file():
            st.image(str(MONITORING_FRAME), width="stretch")
        if result.warnings:
            for warning in result.warnings:
                st.warning(warning, icon=":material/warning:")
        source_info = st.session_state.get("traffic_analysis_source_metadata")
        if source_info and source_info.total_frames:
            progress = min(1.0, result.frame_index / source_info.total_frames)
            st.progress(progress, text=f"Fotograma {result.frame_index} de {source_info.total_frames}")
        st.caption(
            f"Tiempo procesado {_format_clock(result.timestamp_seconds)} · "
            f"FPS de procesamiento {result.processing_fps:.1f} · Estado {active_controller.state.value}"
        )

        st.caption("Métricas provenientes del pipeline real; no se muestran cifras sintéticas.")
        metric_cols = st.columns(4)
        metric_cols[0].metric("Vehículos en escena", result.vehicles_in_scene, border=True)
        metric_cols[1].metric("Cruces totales", result.total_crossings, border=True)
        metric_cols[2].metric("Velocidad", "No calibrada", border=True)
        metric_cols[3].metric("Congestión", result.congestion, border=True)
        st.caption("Estimación operativa, no nivel de servicio normativo.")

        category_labels = (("AUTO", "Automóviles"), ("MOTO", "Motocicletas"), ("BUS", "Buses"), ("CAMION", "Camiones"))
        category_cols = st.columns(4)
        for column, (category, label) in zip(category_cols, category_labels):
            column.metric(label, result.category_counts.get(category, 0), border=True)
        direction_cols = st.columns(3)
        direction_cols[0].metric("Sentido +1", result.direction_counts.get(1, 0), border=True)
        direction_cols[1].metric("Sentido −1", result.direction_counts.get(-1, 0), border=True)
        direction_cols[2].metric("Total", result.total_crossings, border=True)

        if result.end_of_source:
            st.session_state["traffic_analysis_running"] = False

    _real_frame_fragment()

    controller = st.session_state.get("traffic_analysis_controller")
    if controller is not None:
        st.caption(f"Eventos técnicos acumulados para revisión: {len(controller.events)}")
        if st.button(
            "Finalizar y revisar", icon=":material/fact_check:", type="primary",
            key="real_finish_review",
        ):
            try:
                _finish_for_review(controller)
                st.switch_page("pages/traffic_review.py")
            except Exception as exc:
                st.session_state["traffic_analysis_error"] = str(exc)
                st.error(f"No se pudo preparar el lote: {exc}")

    st.caption("OCR permanece opcional e independiente; esta ejecución no realiza lectura de placas.")


if mode == STATIC_MODE:
    _render_monitoring_dashboard()
else:
    _render_real_analysis(mode)
