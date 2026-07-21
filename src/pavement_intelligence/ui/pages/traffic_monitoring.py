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
from pavement_intelligence.integration.traffic_event_adapter import (
    build_traffic_event_batch,
)
from pavement_intelligence.ui.utils.congestion_session import (
    ALERTS_KEY,
    ERROR_KEY as CONGESTION_ERROR_KEY,
    clear_congestion_session,
    finish_congestion_session,
    initialize_congestion_session,
    pause_congestion_session,
    process_congestion_result_once,
    reset_congestion_session,
    resume_congestion_session,
    start_congestion_session,
)
from pavement_intelligence.ui.utils.demo_data import (
    PROJECT_ROOT,
    load_demo_dashboard,
    validate_dashboard_state,
)
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
from pavement_intelligence.ui.utils.traffic_analysis_state import (
    prepare_session_for_real_analysis,
)
from pavement_intelligence.ui.utils.uploaded_video import (
    ALLOWED_UPLOAD_EXTENSIONS,
    MAX_UPLOAD_SIZE_MIB,
    UploadedVideoError,
    UploadedVideoHandle,
    cleanup_uploaded_video,
    store_uploaded_video,
    uploaded_video_digest,
)
from pavement_intelligence.ui.utils.video_catalog import (
    LocalVideo,
    discover_local_videos,
    resolve_video_path,
    stable_video_source_id,
)
from pavement_intelligence.vision.analysis import (
    AnalysisState,
    TrafficAnalysisController,
)
from pavement_intelligence.vision.capture import CameraSource, VideoFileSource
from pavement_intelligence.vision.detection.yolo_detector import YOLODetectorTracker
from pavement_intelligence.vision.pipeline import VisionPipeline

st.set_page_config(
    page_title="Centro de monitoreo de tráfico",
    page_icon=":material/traffic:",
    layout="wide",
)
load_dashboard_css()

MONITORING_FRAME = (
    PROJECT_ROOT
    / "data"
    / "samples"
    / "ui"
    / "assets"
    / "traffic_monitoring_urban_avenue.png"
)
DEMO_VIDEO = (
    PROJECT_ROOT / "data" / "samples" / "ui" / "assets" / "traffic_monitoring_demo.mp4"
)
DEMO_VIDEO_RELATIVE = DEMO_VIDEO.relative_to(PROJECT_ROOT).as_posix()
STATIC_MODE = "Imagen demostrativa"
VIDEO_MODE = "Video pregrabado"
CAMERA_MODE = "Cámara en vivo"
MODEL_PATH = PROJECT_ROOT / "data" / "models" / "yolov8n.pt"

SELECTED_VIDEO_KEY = "traffic_selected_video"
SELECTED_VIDEO_PATH_KEY = "traffic_selected_video_path"
SELECTED_VIDEO_DURATION_KEY = "traffic_selected_video_duration"
VIDEO_CATALOG_SIGNATURE_KEY = "traffic_video_catalog_signature"

LOCAL_VIDEO_SOURCE = "Video local del proyecto"
UPLOAD_VIDEO_SOURCE = "Cargar video"
VIDEO_SOURCE_MODE_KEY = "traffic_video_source_mode"
VIDEO_SOURCE_ACTIVE_MODE_KEY = "traffic_video_source_active_mode"
UPLOADED_VIDEO_WIDGET_KEY = "traffic_uploaded_video_file"
UPLOADED_VIDEO_HANDLE_KEY = "traffic_uploaded_video_handle"
UPLOADED_VIDEO_HASH_KEY = "traffic_uploaded_video_hash"
UPLOADED_VIDEO_FILE_ID_KEY = "traffic_uploaded_video_file_id"
UPLOADED_VIDEO_ERROR_KEY = "traffic_uploaded_video_error"
UPLOADED_VIDEO_CLEANUP_TOKEN_KEY = "traffic_uploaded_video_cleanup_token"


@st.cache_data(max_entries=1)
def _load_state():
    return load_demo_dashboard()


@st.cache_data(max_entries=2)
def _inspect_video(path: str):
    return inspect_video(path)


@st.cache_data(ttl=30, max_entries=1)
def _load_video_catalog() -> tuple[LocalVideo, ...]:
    return discover_local_videos(
        PROJECT_ROOT,
        built_in_video=DEMO_VIDEO_RELATIVE,
    )


def _export_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["origen", "categoría", "conteo"])
    for item in state.categories:
        writer.writerow(["synthetic_demo", item.label, item.count])
    return buffer.getvalue().encode("utf-8-sig")


def _play() -> None:
    st.session_state["traffic_demo_playing"] = True
    st.session_state["traffic_demo_last_update"] = time.monotonic()
    st.session_state["traffic_monitor_state"] = (
        DashboardOperationalState.PROCESSING_ACTIVE.value
    )


def _pause() -> None:
    st.session_state["traffic_demo_playing"] = False
    st.session_state["traffic_monitor_state"] = (
        DashboardOperationalState.PROCESSING_PAUSED.value
    )


def _restart() -> None:
    reset_demo_playback(st.session_state, last_update=time.monotonic())
    st.session_state["traffic_monitor_state"] = (
        DashboardOperationalState.PROCESSING_ACTIVE.value
    )


def _format_clock(seconds: float) -> str:
    seconds = max(0, round(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _duration_text(duration_seconds: float | None) -> str:
    if duration_seconds is None:
        return "Duración no disponible"
    return f"{duration_seconds:.1f} s ({_format_clock(duration_seconds)})"


def _video_option_label(relative_path: str, catalog: tuple[LocalVideo, ...]) -> str:
    entry = next(item for item in catalog if item.relative_path == relative_path)
    prefix = "Video demostrativo corto" if entry.built_in else entry.filename
    return f"{prefix} · {_duration_text(entry.duration_seconds)} · {entry.relative_path}"


def _close_real_controller() -> None:
    controller = st.session_state.get("traffic_analysis_controller")
    if controller is not None:
        controller.close()
    st.session_state["traffic_analysis_controller"] = None
    st.session_state["traffic_analysis_running"] = False
    st.session_state["traffic_analysis_paused"] = False
    clear_congestion_session(st.session_state)


def _clear_real_source_state() -> None:
    """Cierra la fuente y elimina todo estado transitorio del lote anterior."""
    _close_real_controller()
    st.session_state["traffic_analysis_current_result"] = None
    st.session_state["traffic_analysis_batch_events"] = []
    st.session_state["traffic_analysis_source_metadata"] = None
    st.session_state["traffic_analysis_active_source_id"] = None
    st.session_state["traffic_analysis_error"] = ""
    st.session_state["vision_events_raw"] = []
    st.session_state["vision_events_reviewed"] = []
    st.session_state["vision_batch_metadata"] = {}
    st.session_state["traffic_review_approved"] = False
    st.session_state["traffic_counts_corrected"] = {}
    st.session_state["traffic_review_source_fingerprint"] = None


def _cleanup_uploaded_video_session(*, finalized: bool = False) -> None:
    handle = st.session_state.get(UPLOADED_VIDEO_HANDLE_KEY)
    if isinstance(handle, UploadedVideoHandle):
        cleanup_uploaded_video(handle)
    st.session_state[UPLOADED_VIDEO_HANDLE_KEY] = None
    if finalized:
        st.session_state[UPLOADED_VIDEO_CLEANUP_TOKEN_KEY] = "finalized"
        return
    st.session_state[UPLOADED_VIDEO_HASH_KEY] = None
    st.session_state[UPLOADED_VIDEO_FILE_ID_KEY] = None
    st.session_state[UPLOADED_VIDEO_ERROR_KEY] = ""
    st.session_state[UPLOADED_VIDEO_CLEANUP_TOKEN_KEY] = None


def _apply_video_selection(entry: LocalVideo) -> None:
    """Cierra el lote anterior y conserva la nueva selección sin iniciarla."""
    _clear_real_source_state()
    _cleanup_uploaded_video_session()
    st.session_state[SELECTED_VIDEO_PATH_KEY] = entry.relative_path
    st.session_state[SELECTED_VIDEO_DURATION_KEY] = entry.duration_seconds


def _selected_video_input() -> tuple[Path, str]:
    video_source_mode = st.session_state.get(
        VIDEO_SOURCE_MODE_KEY, LOCAL_VIDEO_SOURCE
    )
    if video_source_mode == UPLOAD_VIDEO_SOURCE:
        handle = st.session_state.get(UPLOADED_VIDEO_HANDLE_KEY)
        if not isinstance(handle, UploadedVideoHandle) or not handle.is_available:
            raise UploadedVideoError(
                "El video cargado ya no está disponible; vuelve a seleccionarlo."
            )
        return handle.temporary_path, handle.source_id

    selected_relative = str(
        st.session_state.get(SELECTED_VIDEO_PATH_KEY, DEMO_VIDEO_RELATIVE)
    )
    selected_path = resolve_video_path(
        PROJECT_ROOT,
        selected_relative,
        built_in_video=DEMO_VIDEO_RELATIVE,
    )
    return selected_path, stable_video_source_id(selected_relative)


def _pipeline_factory(source):
    def create_pipeline() -> VisionPipeline:
        info = source.source_info()
        width, height = info.width, info.height
        line_y = max(1, height // 2)
        detector = YOLODetectorTracker(
            model_path=str(MODEL_PATH),
            device="cpu",
            conf_threshold=0.45,
            image_size=640,
            allowed_classes=["car", "motorcycle", "bus", "truck"],
            tracker_config="default",
        )
        return VisionPipeline(
            detector, (0, line_y), (max(1, width - 1), line_y), tolerance=3.0
        )

    return create_pipeline


def _start_real_analysis(source_mode: str, camera_index: int) -> None:
    _clear_real_source_state()
    prepare_session_for_real_analysis(st.session_state)
    try:
        if source_mode == VIDEO_MODE:
            selected_path, source_id = _selected_video_input()
            source = VideoFileSource(selected_path)
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
        active_source_id = source_id if source_mode == VIDEO_MODE else metadata.source_id
        st.session_state["traffic_analysis_active_source_id"] = active_source_id
        start_congestion_session(
            st.session_state,
            active_source_id,
            monitoring_point_id=state.source.point_name,
        )
    except Exception as exc:
        _close_real_controller()
        st.session_state["traffic_analysis_error"] = str(exc)


def _finish_for_review(controller: TrafficAnalysisController) -> None:
    finish_congestion_session(st.session_state)
    events = controller.finish()
    now = datetime.datetime.now().isoformat()
    source_info = st.session_state.get("traffic_analysis_source_metadata")
    source_name = source_info.source_id if source_info else "fuente_local"
    line_y = (source_info.height // 2) if source_info else 360
    batch = build_traffic_event_batch(
        events,
        {
            "model_name": MODEL_PATH.name,
            "line_id": "monitoring_center_line",
            "line_y": line_y,
            "source_video": source_name,
            "processing_date": now,
            "configuration_version": "monitoring-real-v1",
        },
    )
    st.session_state["vision_events_raw"] = [event.to_dict() for event in events]
    st.session_state["vision_events_reviewed"] = batch["events"]
    st.session_state["vision_batch_metadata"] = batch["metadata"]
    st.session_state["traffic_review_approved"] = False
    st.session_state["traffic_counts_corrected"] = {}
    st.session_state["is_synthetic_review"] = False
    st.session_state["traffic_review_source_fingerprint"] = f"real:{source_name}:{now}"
    st.session_state["traffic_analysis_batch_events"] = list(events)
    st.session_state["traffic_analysis_running"] = False
    if st.session_state.get(VIDEO_SOURCE_MODE_KEY) == UPLOAD_VIDEO_SOURCE:
        _cleanup_uploaded_video_session(finalized=True)


state = _load_state()
issues = validate_dashboard_state(state)
if issues:
    for issue in issues:
        st.error(issue, icon=":material/error:")
    st.stop()

initialize_demo_playback(st.session_state, DEMO_VIDEO)
initialize_congestion_session(st.session_state)
st.session_state.setdefault("traffic_analysis_controller", None)
st.session_state.setdefault("traffic_analysis_running", False)
st.session_state.setdefault("traffic_analysis_paused", False)
st.session_state.setdefault("traffic_analysis_current_result", None)
st.session_state.setdefault("traffic_analysis_batch_events", [])
st.session_state.setdefault("traffic_analysis_error", "")
st.session_state.setdefault("traffic_analysis_source_metadata", None)
st.session_state.setdefault("traffic_analysis_active_source_id", None)
st.session_state.setdefault("traffic_analysis_source_type", STATIC_MODE)
st.session_state.setdefault(VIDEO_SOURCE_MODE_KEY, LOCAL_VIDEO_SOURCE)
st.session_state.setdefault(VIDEO_SOURCE_ACTIVE_MODE_KEY, LOCAL_VIDEO_SOURCE)
st.session_state.setdefault(UPLOADED_VIDEO_HANDLE_KEY, None)
st.session_state.setdefault(UPLOADED_VIDEO_HASH_KEY, None)
st.session_state.setdefault(UPLOADED_VIDEO_FILE_ID_KEY, None)
st.session_state.setdefault(UPLOADED_VIDEO_ERROR_KEY, "")
st.session_state.setdefault(UPLOADED_VIDEO_CLEANUP_TOKEN_KEY, None)

video_catalog = _load_video_catalog()
if not video_catalog:
    st.error(
        "No se encontraron videos locales permitidos para el análisis.",
        icon=":material/video_file:",
    )
    st.stop()
catalog_by_path = {item.relative_path: item for item in video_catalog}
default_video = (
    DEMO_VIDEO_RELATIVE
    if DEMO_VIDEO_RELATIVE in catalog_by_path
    else video_catalog[0].relative_path
)
selected_video = str(st.session_state.get(SELECTED_VIDEO_KEY, default_video))
if selected_video not in catalog_by_path:
    selected_video = default_video
st.session_state[SELECTED_VIDEO_KEY] = selected_video
selected_entry = catalog_by_path[selected_video]
if SELECTED_VIDEO_PATH_KEY not in st.session_state:
    st.session_state[SELECTED_VIDEO_PATH_KEY] = selected_entry.relative_path
    st.session_state[SELECTED_VIDEO_DURATION_KEY] = selected_entry.duration_seconds
st.session_state[VIDEO_CATALOG_SIGNATURE_KEY] = tuple(
    (item.relative_path, item.duration_seconds) for item in video_catalog
)

title_col, action_col = st.columns([7, 4], vertical_alignment="bottom")
with title_col:
    st.title("Centro de monitoreo de tráfico")
    st.caption(
        "Supervisión operativa del flujo vehicular y del estado del lote en tiempo casi real."
    )
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
            "Exportar datos",
            data=_export_csv(),
            file_name="monitoreo_demo.csv",
            mime="text/csv",
            icon=":material/download:",
            type="primary",
            width="content",
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
    _clear_real_source_state()
    if previous_mode == VIDEO_MODE:
        _cleanup_uploaded_video_session()
st.session_state["traffic_analysis_active_mode"] = mode


@st.fragment(
    run_every=0.15
    if mode == STATIC_MODE and st.session_state["traffic_demo_playing"]
    else None
)
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

    progress = (
        playback_progress(
            int(st.session_state["traffic_demo_frame_index"]),
            int(st.session_state["traffic_demo_total_frames"]),
        )
        if mode == STATIC_MODE and video_info
        else 0.0
    )
    demo_metrics = compute_demo_metrics(progress)

    main_col, side_col = st.columns([9, 3], gap="medium")
    with main_col:
        with st.container(border=True, gap="small"):
            header_left, header_right = st.columns([2, 3], vertical_alignment="center")
            header_left.markdown("**:material/videocam: Conteo automático simulado**")
            badges = render_status_chip("MÉTRICAS SIMULADAS", "info")
            badges = (
                render_status_chip("DEMOSTRACIÓN SINTÉTICA", "success") + " " + badges
            )
            header_right.markdown(badges, unsafe_allow_html=True)

            displayed_video = False
            if displayed_video:
                try:
                    image = frame_to_rgb(
                        read_frame(
                            DEMO_VIDEO,
                            int(st.session_state["traffic_demo_frame_index"]),
                        )
                    )
                    st.image(image, width="stretch")
                except ValueError as exc:
                    video_error = str(exc)
                    st.session_state["traffic_demo_error"] = video_error
                    st.session_state["traffic_demo_playing"] = False
                    displayed_video = False
            if not displayed_video:
                if video_error:
                    st.error(
                        f"{video_error} Se muestra la imagen demostrativa segura.",
                        icon=":material/video_file:",
                    )
                if MONITORING_FRAME.is_file():
                    st.image(str(MONITORING_FRAME), width="stretch")
                else:
                    st.warning(
                        "No se encontró el fotograma demostrativo.",
                        icon=":material/image_not_supported:",
                    )

            if displayed_video and video_info:
                elapsed = (
                    int(st.session_state["traffic_demo_frame_index"]) / video_info.fps
                )
                st.progress(
                    progress,
                    text=f"Fotograma {int(st.session_state['traffic_demo_frame_index']) + 1} de {video_info.total_frames}",
                )
                st.caption(
                    f"{_format_clock(elapsed)} / {_format_clock(video_info.duration_seconds)} · "
                    f"{video_info.fps:.1f} FPS fuente · {video_info.resolution}"
                )
            else:
                st.caption(
                    "Fotograma urbano demostrativo con overlays preprocesados; no ejecuta YOLO ni ByteTrack."
                )

            controls_disabled = True
            with st.container(
                horizontal=True, vertical_alignment="center", gap="small"
            ):
                st.button(
                    "Reproducir",
                    icon=":material/play_arrow:",
                    key="monitor_play",
                    width="content",
                    disabled=controls_disabled
                    or bool(st.session_state["traffic_demo_playing"]),
                    on_click=_play,
                )
                st.button(
                    "Pausar",
                    icon=":material/pause:",
                    key="monitor_pause",
                    width="content",
                    disabled=controls_disabled
                    or not bool(st.session_state["traffic_demo_playing"]),
                    on_click=_pause,
                )
                st.button(
                    "Reiniciar",
                    icon=":material/replay:",
                    key="monitor_replay",
                    width="content",
                    disabled=controls_disabled,
                    on_click=_restart,
                )

        st.caption("Métricas demostrativas, no calculadas desde el video.")
        st.markdown("**Clasificación vehicular** · Total acumulado")
        category_cols = st.columns(5, gap="small")
        for index, (column, category) in enumerate(
            zip(category_cols, state.categories)
        ):
            count = (
                demo_metrics.category_counts[index]
                if mode == VIDEO_MODE
                else category.count
            )
            column.metric(
                category.label,
                f"{count:,}",
                f"{category.trend_percent:+.1f}%",
                border=True,
            )

        direction_values = (
            demo_metrics.direction_counts
            if mode == VIDEO_MODE
            else tuple(item.count for item in state.directions)
        )
        direction_cols = st.columns(3, gap="small")
        for column, direction, count in zip(
            direction_cols, state.directions, direction_values
        ):
            column.metric(direction.label, f"{count:,}", border=True)
        direction_cols[2].metric("Total", f"{sum(direction_values):,}", border=True)

        with st.container(border=True, gap="small"):
            st.markdown("**Flujo vehicular** · Ambos sentidos (veh/min)")
            flow_df = pd.DataFrame(state.time_series).set_index("time")
            st.line_chart(
                flow_df,
                x_label="Hora",
                y_label="veh/min",
                color=["#1A56DB", "#CA8A04"],
                height=230,
            )

    with side_col:
        with st.container(border=True, gap="small"):
            st.markdown("**Estado actual**")
            congestion_label = (
                demo_metrics.congestion
                if mode == VIDEO_MODE
                else state.congestion.label
            )
            chip_col, lot_col = st.columns([3, 2], vertical_alignment="center")
            chip_col.markdown(
                render_status_chip(congestion_label, "warning"), unsafe_allow_html=True
            )
            lot_col.markdown(
                render_status_chip(state.review.label, "warning"),
                unsafe_allow_html=True,
            )
            status_left, status_right = st.columns(2, gap="small")
            flow = (
                demo_metrics.flow_veh_min
                if mode == VIDEO_MODE
                else state.metrics.current_flow_veh_min
            )
            in_scene = (
                demo_metrics.vehicles_in_scene
                if mode == VIDEO_MODE
                else state.metrics.vehicles_in_scene
            )
            status_left.metric("Flujo", format_unit(flow, "veh/min"), border=True)
            status_right.metric(
                "Velocidad",
                format_unit(state.metrics.average_speed_kmh, "km/h"),
                border=True,
            )
            status_left.metric(
                "Ocupación est.",
                format_unit(state.metrics.visual_occupancy_percent, "%"),
                border=True,
            )
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
            confidence_col.metric(
                "Confianza", format_unit(state.ocr.average_confidence_percent, "%")
            )
            if st.button("Ver lecturas", icon=":material/visibility:", width="stretch"):
                st.switch_page("pages/ocr_plate_review.py")

        with st.container(border=True, gap="small"):
            st.markdown("**Alertas recientes**")
            visible_alerts = (
                state.alerts
                if mode == STATIC_MODE
                else state.alerts[: demo_metrics.alert_count]
            )
            if visible_alerts:
                alert_df = pd.DataFrame([vars(item) for item in visible_alerts]).rename(
                    columns={
                        "time": "Hora",
                        "alert_type": "Tipo",
                        "description": "Descripción",
                        "level": "Nivel",
                        "status": "Estado",
                    }
                )
                st.dataframe(
                    alert_df[["Hora", "Tipo", "Nivel", "Estado"]],
                    hide_index=True,
                    height=145,
                )
                with st.expander("Ver descripción de alertas"):
                    for alert in visible_alerts:
                        st.caption(
                            f"**{alert.time} · {alert.alert_type}:** {alert.description}"
                        )
            else:
                st.info(
                    "Sin alertas simuladas en este punto del video.",
                    icon=":material/check_circle:",
                )


def _process_uploaded_file(uploaded_file) -> UploadedVideoHandle | None:
    previous = st.session_state.get(UPLOADED_VIDEO_HANDLE_KEY)
    previous = previous if isinstance(previous, UploadedVideoHandle) else None
    if uploaded_file is None:
        if previous is not None or st.session_state.get(UPLOADED_VIDEO_HASH_KEY):
            _clear_real_source_state()
            _cleanup_uploaded_video_session()
        return None

    file_id = str(getattr(uploaded_file, "file_id", "") or "")
    try:
        digest = uploaded_video_digest(uploaded_file)
    except (OSError, UploadedVideoError) as exc:
        _clear_real_source_state()
        _cleanup_uploaded_video_session()
        st.session_state[UPLOADED_VIDEO_ERROR_KEY] = str(exc)
        return None

    current_hash = st.session_state.get(UPLOADED_VIDEO_HASH_KEY)
    current_file_id = st.session_state.get(UPLOADED_VIDEO_FILE_ID_KEY)
    cleanup_token = st.session_state.get(UPLOADED_VIDEO_CLEANUP_TOKEN_KEY)
    if digest == current_hash and previous is not None and previous.is_available:
        return previous
    if digest == current_hash and previous is not None and not previous.is_available:
        _clear_real_source_state()
        cleanup_uploaded_video(previous)
        st.session_state[UPLOADED_VIDEO_HANDLE_KEY] = None
        st.session_state[UPLOADED_VIDEO_ERROR_KEY] = (
            "El archivo temporal ya no está disponible; vuelve a cargar el video."
        )
        st.session_state[UPLOADED_VIDEO_CLEANUP_TOKEN_KEY] = "invalid"
        return None
    if (
        digest == current_hash
        and file_id == current_file_id
        and cleanup_token in {"finalized", "invalid"}
    ):
        return None

    _clear_real_source_state()
    try:
        handle = store_uploaded_video(uploaded_file, previous=previous)
    except (OSError, UploadedVideoError) as exc:
        st.session_state[UPLOADED_VIDEO_HANDLE_KEY] = None
        st.session_state[UPLOADED_VIDEO_HASH_KEY] = digest
        st.session_state[UPLOADED_VIDEO_FILE_ID_KEY] = file_id
        st.session_state[UPLOADED_VIDEO_ERROR_KEY] = str(exc)
        st.session_state[UPLOADED_VIDEO_CLEANUP_TOKEN_KEY] = "invalid"
        return None

    st.session_state[UPLOADED_VIDEO_HANDLE_KEY] = handle
    st.session_state[UPLOADED_VIDEO_HASH_KEY] = handle.sha256
    st.session_state[UPLOADED_VIDEO_FILE_ID_KEY] = file_id
    st.session_state[UPLOADED_VIDEO_ERROR_KEY] = ""
    st.session_state[UPLOADED_VIDEO_CLEANUP_TOKEN_KEY] = handle.cleanup_token
    return handle


def _render_uploaded_video_selector() -> None:
    uploaded_file = st.file_uploader(
        "Cargar video de análisis",
        type=sorted(extension.lstrip(".") for extension in ALLOWED_UPLOAD_EXTENSIONS),
        accept_multiple_files=False,
        key=UPLOADED_VIDEO_WIDGET_KEY,
        max_upload_size=MAX_UPLOAD_SIZE_MIB,
        help="El archivo se valida y se conserva únicamente en un temporal de sesión.",
    )
    st.caption(
        "El video se procesa localmente durante esta sesión y no se incorpora al repositorio."
    )
    st.warning(
        "Los videos pueden contener matrículas, personas u otros datos sensibles. "
        "Usa únicamente material autorizado.",
        icon=":material/privacy_tip:",
    )
    handle = _process_uploaded_file(uploaded_file)
    error = st.session_state.get(UPLOADED_VIDEO_ERROR_KEY, "")
    if error:
        st.error(str(error), icon=":material/video_file:")
        return
    if handle is None:
        if st.session_state.get(UPLOADED_VIDEO_CLEANUP_TOKEN_KEY) == "finalized":
            st.info(
                "El análisis finalizó y el archivo temporal fue eliminado. "
                "Quita y vuelve a cargar el archivo para analizarlo otra vez."
            )
        else:
            st.info("Selecciona un video autorizado para habilitar el análisis.")
        return

    st.caption(
        f"Archivo: `{handle.original_name}` · "
        f"Tamaño: {handle.size_bytes / 1024 / 1024:.2f} MiB · "
        f"Formato: {handle.extension.lstrip('.').upper()} · "
        f"Duración: {_duration_text(handle.duration_seconds)}"
    )
    if handle.duration_seconds < 10.0:
        st.warning(
            "Este video dura menos de 10 segundos y no permite completar "
            "el calentamiento de la estimación de congestión.",
            icon=":material/timer_off:",
        )
    else:
        st.info(
            "El video supera el calentamiento de 10 segundos y permite observar "
            "la transición desde Datos insuficientes.",
            icon=":material/timer:",
        )


def _render_real_analysis(source_mode: str) -> None:
    st.markdown(
        render_status_chip(
            "ANÁLISIS REAL DE VIDEO" if source_mode == VIDEO_MODE else "CÁMARA EN VIVO",
            "success",
        ),
        unsafe_allow_html=True,
    )
    camera_index = 0
    analysis_input_ready = True
    if source_mode == VIDEO_MODE:
        video_source_mode = st.segmented_control(
            "Origen del video pregrabado",
            [LOCAL_VIDEO_SOURCE, UPLOAD_VIDEO_SOURCE],
            key=VIDEO_SOURCE_MODE_KEY,
            selection_mode="single",
        )
        video_source_mode = video_source_mode or LOCAL_VIDEO_SOURCE
        previous_video_source_mode = st.session_state.get(
            VIDEO_SOURCE_ACTIVE_MODE_KEY, LOCAL_VIDEO_SOURCE
        )
        if video_source_mode != previous_video_source_mode:
            _clear_real_source_state()
            _cleanup_uploaded_video_session()
        st.session_state[VIDEO_SOURCE_ACTIVE_MODE_KEY] = video_source_mode

        if video_source_mode == LOCAL_VIDEO_SOURCE:
            selected_relative = st.selectbox(
                "Seleccionar video de análisis",
                [item.relative_path for item in video_catalog],
                key=SELECTED_VIDEO_KEY,
                format_func=lambda value: _video_option_label(value, video_catalog),
                help=(
                    "El catálogo solo incluye el video demostrativo incorporado y "
                    "archivos validados dentro de data/videos."
                ),
            )
            selected_entry = catalog_by_path[selected_relative]
            if selected_relative != st.session_state.get(SELECTED_VIDEO_PATH_KEY):
                _apply_video_selection(selected_entry)
            st.caption(
                f"Archivo seleccionado: `{selected_entry.relative_path}` · "
                f"{_duration_text(selected_entry.duration_seconds)}"
            )
            if (
                selected_entry.duration_seconds is not None
                and selected_entry.duration_seconds < 10.0
            ):
                st.warning(
                    "Este video dura menos de 10 segundos y no permite completar "
                    "el calentamiento de la estimación de congestión.",
                    icon=":material/timer_off:",
                )
            elif selected_entry.duration_seconds is not None:
                st.info(
                    "Este video supera el calentamiento de 10 segundos y permite "
                    "validar visualmente la transición desde Datos insuficientes.",
                    icon=":material/timer:",
                )
            try:
                selected_path = resolve_video_path(
                    PROJECT_ROOT,
                    selected_relative,
                    built_in_video=DEMO_VIDEO_RELATIVE,
                )
                selected_info = _inspect_video(str(selected_path))
                st.caption(
                    f"{selected_info.resolution} · {selected_info.fps:.1f} FPS · "
                    f"{selected_info.total_frames} fotogramas · "
                    f"{_format_clock(selected_info.duration_seconds)}"
                )
            except (FileNotFoundError, ValueError) as exc:
                st.error(str(exc), icon=":material/video_file:")
        else:
            _render_uploaded_video_selector()
            uploaded_handle = st.session_state.get(UPLOADED_VIDEO_HANDLE_KEY)
            analysis_input_ready = (
                isinstance(uploaded_handle, UploadedVideoHandle)
                and uploaded_handle.is_available
            )
    else:
        camera_index = st.selectbox(
            "Índice de cámara local", [0, 1], key="traffic_analysis_camera_index"
        )
        st.caption(
            "La cámara solo se abre mediante acción explícita y se libera al detener o finalizar."
        )

    controller = st.session_state.get("traffic_analysis_controller")
    running = controller is not None and controller.state is AnalysisState.RUNNING
    paused = controller is not None and controller.state is AnalysisState.PAUSED
    with st.container(horizontal=True, gap="small"):
        start_label = (
            "Iniciar análisis" if source_mode == VIDEO_MODE else "Iniciar cámara"
        )
        if st.button(
            start_label,
            icon=":material/play_arrow:",
            type="primary",
            disabled=controller is not None or not analysis_input_ready,
        ):
            with st.spinner("Inicializando YOLOv8 y ByteTrack…"):
                _start_real_analysis(source_mode, int(camera_index))
            st.rerun()
        if st.button(
            "Pausar", icon=":material/pause:", disabled=not running, key="real_pause"
        ):
            controller.pause()
            pause_congestion_session(st.session_state)
            st.session_state["traffic_analysis_running"] = False
            st.session_state["traffic_analysis_paused"] = True
            st.rerun()
        if st.button(
            "Continuar",
            icon=":material/resume:",
            disabled=not paused,
            key="real_resume",
        ):
            controller.resume()
            resume_congestion_session(st.session_state)
            st.session_state["traffic_analysis_running"] = True
            st.session_state["traffic_analysis_paused"] = False
            st.rerun()
        if st.button(
            "Reiniciar",
            icon=":material/replay:",
            disabled=controller is None,
            key="real_reset",
        ):
            metadata = controller.reset()
            active_source_id = st.session_state.get(
                "traffic_analysis_active_source_id", metadata.source_id
            )
            reset_congestion_session(
                st.session_state,
                str(active_source_id or metadata.source_id),
            )
            st.session_state["traffic_analysis_source_metadata"] = metadata
            st.session_state["traffic_analysis_current_result"] = None
            st.session_state["traffic_analysis_running"] = True
            st.session_state["traffic_analysis_paused"] = False
            st.rerun()
        stop_label = (
            "Detener cámara" if source_mode == CAMERA_MODE else "Finalizar análisis"
        )
        if st.button(
            stop_label,
            icon=":material/stop_circle:",
            disabled=controller is None,
            key="real_stop",
        ):
            controller.finish()
            finish_congestion_session(st.session_state)
            st.session_state["traffic_analysis_running"] = False
            if (
                source_mode == VIDEO_MODE
                and st.session_state.get(VIDEO_SOURCE_MODE_KEY)
                == UPLOAD_VIDEO_SOURCE
            ):
                _cleanup_uploaded_video_session(finalized=True)
            st.rerun()

    if st.session_state["traffic_analysis_error"]:
        st.error(st.session_state["traffic_analysis_error"], icon=":material/error:")
        if MONITORING_FRAME.is_file():
            st.image(str(MONITORING_FRAME), width="stretch")

    @st.fragment(run_every=0.15 if running else None)
    def _real_frame_fragment() -> None:
        active_controller = st.session_state.get("traffic_analysis_controller")
        if active_controller is None:
            if (
                not st.session_state["traffic_analysis_error"]
                and MONITORING_FRAME.is_file()
            ):
                st.image(str(MONITORING_FRAME), width="stretch")
                st.info("Selecciona una fuente e inicia el análisis explícitamente.")
            return
        result = (
            active_controller.process_next()
            if active_controller.state is AnalysisState.RUNNING
            else active_controller.last_result
        )
        st.session_state["traffic_analysis_current_result"] = result
        if result is None:
            return
        congestion = process_congestion_result_once(st.session_state, result)
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
            st.progress(
                progress,
                text=f"Fotograma {result.frame_index} de {source_info.total_frames}",
            )
        st.caption(
            f"Tiempo procesado {_format_clock(result.timestamp_seconds)} · "
            f"FPS de procesamiento {result.processing_fps:.1f} · Estado {active_controller.state.value}"
        )

        st.caption(
            "Métricas provenientes del pipeline real; no se muestran cifras sintéticas."
        )
        with st.container(border=True, gap="small"):
            st.markdown("**Estado actual**")
            if congestion is not None:
                st.markdown(
                    render_status_chip(
                        congestion.level_label, congestion.badge_variant
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{congestion.headline}**")
                st.caption(congestion.summary)
                metric_cols = st.columns(4)
                metric_cols[0].metric(
                    "Flujo", congestion.vehicles_per_minute_text, border=True
                )
                metric_cols[1].metric(
                    "En escena", congestion.vehicles_in_scene_text, border=True
                )
                metric_cols[2].metric(
                    "Acumulación", congestion.accumulation_text, border=True
                )
                metric_cols[3].metric(
                    "Tiempo observado", congestion.observation_time_text, border=True
                )
                secondary_cols = st.columns(2)
                secondary_cols[0].metric(
                    "Cruces totales", result.total_crossings, border=True
                )
                secondary_cols[1].metric("Velocidad", "No calibrada", border=True)
                if congestion.candidate_text:
                    st.warning(
                        congestion.candidate_text,
                        icon=":material/hourglass_top:",
                    )
                if congestion.alert_text:
                    st.error(congestion.alert_text, icon=":material/warning:")
                if congestion.evidence_lines:
                    with st.expander("Ver evidencia de congestión"):
                        for line in congestion.evidence_lines:
                            st.caption(line)
                for warning in congestion.warning_lines:
                    st.warning(warning, icon=":material/warning:")
            else:
                st.info("Esperando la primera estimación válida de congestión.")
            st.caption(
                "Estimación operativa; no corresponde a un Nivel de Servicio normativo."
            )

        congestion_error = st.session_state.get(CONGESTION_ERROR_KEY, "")
        if congestion_error:
            st.error(
                f"La estimación de congestión se detuvo: {congestion_error}. "
                "El análisis vehicular puede continuar; reinicia para recuperar la estimación.",
                icon=":material/error:",
            )

        category_labels = (
            ("AUTO", "Automóviles"),
            ("MOTO", "Motocicletas"),
            ("BUS", "Buses"),
            ("CAMION", "Camiones"),
        )
        category_cols = st.columns(4)
        for column, (category, label) in zip(category_cols, category_labels):
            column.metric(label, result.category_counts.get(category, 0), border=True)
        direction_cols = st.columns(3)
        direction_cols[0].metric(
            "Sentido +1", result.direction_counts.get(1, 0), border=True
        )
        direction_cols[1].metric(
            "Sentido −1", result.direction_counts.get(-1, 0), border=True
        )
        direction_cols[2].metric("Total", result.total_crossings, border=True)

        with st.container(border=True, gap="small"):
            st.markdown("**Alertas operativas recientes**")
            congestion_alerts = st.session_state.get(ALERTS_KEY, ())
            if congestion_alerts:
                alert_df = pd.DataFrame(
                    [
                        {
                            "Tiempo": item.time_text,
                            "Tipo": item.alert_type,
                            "Nivel": item.level,
                            "Estado": item.status,
                            "Origen": item.origin,
                        }
                        for item in congestion_alerts
                    ]
                )
                st.dataframe(alert_df, hide_index=True, height=145)
                st.caption(
                    "Alertas informativas no normativas; no aprueban ni transfieren el aforo."
                )
            else:
                st.info(
                    "Sin alertas operativas confirmadas.",
                    icon=":material/check_circle:",
                )

        if result.end_of_source:
            st.session_state["traffic_analysis_running"] = False

    _real_frame_fragment()

    controller = st.session_state.get("traffic_analysis_controller")
    if controller is not None:
        st.caption(
            f"Eventos técnicos acumulados para revisión: {len(controller.events)}"
        )
        if st.button(
            "Finalizar y revisar",
            icon=":material/fact_check:",
            type="primary",
            key="real_finish_review",
        ):
            try:
                _finish_for_review(controller)
                st.switch_page("pages/traffic_review.py")
            except Exception as exc:
                st.session_state["traffic_analysis_error"] = str(exc)
                st.error(f"No se pudo preparar el lote: {exc}")

    st.caption(
        "OCR permanece opcional e independiente; esta ejecución no realiza lectura de placas."
    )


if mode == STATIC_MODE:
    _render_monitoring_dashboard()
else:
    _render_real_analysis(mode)

