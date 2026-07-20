"""Revisión experimental y aislada de placas OCR sintéticas."""
from __future__ import annotations

import base64
import importlib.util

import pandas as pd
import streamlit as st

from pavement_intelligence.domain.traffic.ocr_presentation import (
    PlateCorrectionRequest, PlateReviewStatus,
)
from pavement_intelligence.ui.utils.demo_data import PROJECT_ROOT
from pavement_intelligence.ui.utils.ocr_privacy import (
    confirm_correction, confirm_unchanged, export_reviewed_csv, initialize_ocr_session,
    load_demo_plate_readings, mark_status, render_plate_crop, save_review,
    select_reading, summarize_readings, toggle_plate_visibility,
)
from pavement_intelligence.ui.utils.plate_session import (
    cleanup_plate_session,
    correct_plate_reading,
    initialize_plate_session,
    mask_plate_text,
    reject_plate_reading,
    toggle_plate_reveal,
)
from pavement_intelligence.ui.utils.plate_visualization import annotate_plate_frame
from pavement_intelligence.ui.utils.styles import load_dashboard_css, render_status_chip
from pavement_intelligence.ui.utils.uploaded_video import (
    ALLOWED_UPLOAD_EXTENSIONS,
    MAX_UPLOAD_SIZE_MIB,
    UploadedVideoError,
    UploadedVideoHandle,
    cleanup_uploaded_video,
    store_uploaded_video,
)
from pavement_intelligence.ui.utils.video_catalog import (
    discover_local_videos,
    resolve_video_path,
    stable_video_source_id,
)
from pavement_intelligence.vision.analysis.ocr_controller import (
    NormalizedRoiExtractor,
    PlateAnalysisConfig,
    PlateAnalysisController,
)
from pavement_intelligence.vision.analysis.ocr_models import PlateAnalysisState
from pavement_intelligence.vision.capture import CameraSource, VideoFileSource
from pavement_intelligence.vision.plates.paddleocr_reader import PaddleOCRPlateReader

st.set_page_config(page_title="Lecturas de placas", page_icon=":material/license:", layout="wide")
load_dashboard_css()

REVIEWERS = ("jperez", "mrodriguez", "dvelasco")
REASONS = (
    "Seleccione un motivo...", "Carácter confundido por OCR", "Imagen obstruida / sucia",
    "Reflejo o iluminación deficiente", "Recorte incorrecto", "Lectura duplicada", "Otro",
)
SYNTHETIC_MODE = "Demostración sintética"
REAL_MODE = "Análisis OCR real"
LOCAL_SOURCE = "Video local"
UPLOAD_SOURCE = "Cargar video"
CAMERA_SOURCE = "Cámara"
DEMO_VIDEO_RELATIVE = "data/samples/ui/assets/traffic_monitoring_demo.mp4"


@st.cache_data(max_entries=1)
def _load_readings():
    return load_demo_plate_readings()


def _protected_data_url(text: str) -> str:
    payload = base64.b64encode(render_plate_crop(text, protected=True)).decode("ascii")
    return f"data:image/png;base64,{payload}"


def _paddleocr_available() -> bool:
    try:
        return importlib.util.find_spec("paddleocr") is not None
    except (ImportError, ValueError):
        return False


def _process_plate_upload(uploaded_file) -> UploadedVideoHandle | None:
    previous = st.session_state.get("plate_session_uploaded_video")
    previous = previous if isinstance(previous, UploadedVideoHandle) else None
    if uploaded_file is None:
        if previous is not None:
            cleanup_plate_session(st.session_state)
            initialize_plate_session(st.session_state)
        return None
    file_id = str(getattr(uploaded_file, "file_id", "") or "")
    if (
        previous is not None
        and previous.is_available
        and st.session_state.get("plate_session_uploaded_file_id") == file_id
    ):
        return previous
    if (
        st.session_state.get("plate_session_upload_status") == "finalized"
        and st.session_state.get("plate_session_uploaded_file_id") == file_id
    ):
        return None
    cleanup_plate_session(st.session_state)
    initialize_plate_session(st.session_state)
    try:
        handle = store_uploaded_video(uploaded_file, previous=previous)
    except (OSError, UploadedVideoError) as exc:
        st.session_state["plate_session_error"] = str(exc)
        st.session_state["plate_session_uploaded_file_id"] = file_id
        st.session_state["plate_session_upload_status"] = "invalid"
        return None
    st.session_state["plate_session_uploaded_video"] = handle
    st.session_state["plate_session_uploaded_file_id"] = file_id
    st.session_state["plate_session_uploaded_hash"] = handle.sha256
    st.session_state["plate_session_upload_status"] = "ready"
    return handle


def _plate_reader():
    override = st.session_state.get("plate_session_reader_override")
    if override is not None:
        return override
    if not _paddleocr_available():
        raise RuntimeError(
            "PaddleOCR no está instalado. El análisis real permanece opcional."
        )
    return PaddleOCRPlateReader(anonymize=False)


def _start_real_ocr(source_kind: str, selected_relative: str, every_n: int) -> None:
    try:
        source_override = st.session_state.get("plate_session_source_override")
        if source_override is not None:
            source = source_override
            source_id = source.source_id
        elif source_kind == LOCAL_SOURCE:
            path = resolve_video_path(
                PROJECT_ROOT,
                selected_relative,
                built_in_video=DEMO_VIDEO_RELATIVE,
            )
            source = VideoFileSource(path)
            source_id = stable_video_source_id(selected_relative)
        elif source_kind == UPLOAD_SOURCE:
            handle = st.session_state.get("plate_session_uploaded_video")
            if not isinstance(handle, UploadedVideoHandle) or not handle.is_available:
                raise UploadedVideoError(
                    "El video cargado no está disponible; vuelve a seleccionarlo."
                )
            source = VideoFileSource(handle.temporary_path)
            source_id = handle.source_id
        else:
            source = CameraSource(0)
            source_id = source.source_id
        controller = PlateAnalysisController(
            source,
            _plate_reader(),
            NormalizedRoiExtractor(),
            PlateAnalysisConfig(every_n_frames=every_n, source_id=source_id),
        )
        source_info = controller.start()
        st.session_state["plate_session_controller"] = controller
        st.session_state["plate_session_source_id"] = source_id
        st.session_state["plate_session_batch_id"] = controller.plate_batch_id
        st.session_state["plate_session_batch_readings"] = ()
        st.session_state["plate_session_frame_result"] = None
        st.session_state["plate_session_annotated_frame"] = None
        st.session_state["plate_session_last_frame"] = None
        st.session_state["plate_session_last_detections"] = ()
        st.session_state["plate_session_source_info"] = source_info
        st.session_state["plate_session_last_processed_frame"] = None
        st.session_state["plate_session_error"] = ""
        st.session_state["plate_session_skip_auto_once"] = False
    except Exception as exc:
        st.session_state["plate_session_error"] = str(exc)


def _sync_plate_controller(
    controller: PlateAnalysisController, *, single_step: bool = False
) -> None:
    result = controller.step() if single_step else controller.process_next()
    st.session_state["plate_session_frame_result"] = result
    st.session_state["plate_session_batch_readings"] = controller.readings
    if result is not None:
        st.session_state["plate_session_last_processed_frame"] = result.frame_index
        if result.frame is not None:
            st.session_state["plate_session_last_frame"] = result.frame
            st.session_state["plate_session_last_detections"] = result.detections
            st.session_state["plate_session_annotated_frame"] = annotate_plate_frame(
                result.frame,
                result.detections,
                protect_plate=bool(
                    st.session_state.get("plate_session_protect_viewer", True)
                ),
            )
    if controller.state is PlateAnalysisState.ERROR:
        st.session_state["plate_session_error"] = controller.error
    if controller.state in {
        PlateAnalysisState.COMPLETED,
        PlateAnalysisState.ERROR,
    }:
        _cleanup_finished_upload()


def _cleanup_finished_upload() -> None:
    handle = st.session_state.get("plate_session_uploaded_video")
    if isinstance(handle, UploadedVideoHandle):
        cleanup_uploaded_video(handle)
        st.session_state["plate_session_uploaded_video"] = None
        st.session_state["plate_session_upload_status"] = "finalized"


def _reset_real_ocr_session() -> None:
    """Callback ejecutado antes de crear widgets en el rerun de reinicio."""
    cleanup_plate_session(st.session_state)
    initialize_plate_session(st.session_state)


def _render_progressive_viewer(source_kind: str) -> None:
    controller = st.session_state.get("plate_session_controller")
    state = (
        controller.state
        if isinstance(controller, PlateAnalysisController)
        else (
            PlateAnalysisState.ERROR
            if st.session_state.get("plate_session_error")
            else PlateAnalysisState.IDLE
        )
    )
    auto_running = (
        state is PlateAnalysisState.RUNNING
        and source_kind in {LOCAL_SOURCE, UPLOAD_SOURCE}
    )

    @st.fragment(run_every=0.15 if auto_running else None)
    def progressive_viewer() -> None:
        active = st.session_state.get("plate_session_controller")
        if (
            isinstance(active, PlateAnalysisController)
            and active.state is PlateAnalysisState.RUNNING
            and source_kind in {LOCAL_SOURCE, UPLOAD_SOURCE}
        ):
            if st.session_state.get("plate_session_skip_auto_once", False):
                st.session_state["plate_session_skip_auto_once"] = False
            else:
                _sync_plate_controller(active)

        active = st.session_state.get("plate_session_controller")
        active_state = (
            active.state
            if isinstance(active, PlateAnalysisController)
            else (
                PlateAnalysisState.ERROR
                if st.session_state.get("plate_session_error")
                else PlateAnalysisState.IDLE
            )
        )
        frame_result = st.session_state.get("plate_session_frame_result")
        source_info = st.session_state.get("plate_session_source_info")
        current = int(getattr(frame_result, "frame_index", 0) or 0)
        total_value = getattr(source_info, "total_frames", None)
        total = int(total_value) if total_value else None
        progress = min(1.0, current / total) if total else 0.0
        if active_state is PlateAnalysisState.COMPLETED and total:
            progress = 1.0
        readings = tuple(st.session_state.get("plate_session_batch_readings", ()))
        processing_fps = float(getattr(frame_result, "processing_fps", 0.0) or 0.0)

        last_frame = st.session_state.get("plate_session_last_frame")
        last_detections = tuple(
            st.session_state.get("plate_session_last_detections", ())
        )
        if last_frame is not None:
            st.session_state["plate_session_annotated_frame"] = annotate_plate_frame(
                last_frame,
                last_detections,
                protect_plate=bool(
                    st.session_state.get("plate_session_protect_viewer", True)
                ),
            )

        with st.container(horizontal=True):
            st.metric("Estado", active_state.value, border=True)
            st.metric(
                "Fotograma",
                f"{current}/{total}" if total else str(current),
                border=True,
            )
            st.metric("Progreso", f"{progress:.1%}", border=True)
            st.metric("Lecturas encontradas", len(readings), border=True)
            st.metric("FPS de procesamiento", f"{processing_fps:.2f}", border=True)
        progress_text = (
            f"Fotograma {current} de {total} · {progress:.1%}"
            if total
            else f"Fotograma {current} · total no disponible"
        )
        st.progress(progress, text=progress_text)

        frame = st.session_state.get("plate_session_annotated_frame")
        if frame is not None:
            st.image(
                frame,
                channels="BGR",
                caption="Video OCR procesado progresivamente",
                width="stretch",
            )
        elif active_state is PlateAnalysisState.IDLE:
            st.info("Inicia el análisis para ver el video procesado.")

    progressive_viewer()


def _render_real_ocr() -> None:
    st.title("Lecturas de placas")
    st.markdown(
        render_status_chip("Experimental", "info")
        + " "
        + render_status_chip("Fuente OCR independiente", "neutral"),
        unsafe_allow_html=True,
    )
    st.info(
        "Las lecturas OCR son auxiliares y requieren revisión humana.",
        icon=":material/privacy_tip:",
    )
    st.caption(
        "Estrategia: ROI central configurable; no se utiliza un detector automático "
        "de placas ni se transfieren resultados al aforo o TPDA."
    )
    source_kind = st.segmented_control(
        "Fuente OCR",
        [LOCAL_SOURCE, UPLOAD_SOURCE, CAMERA_SOURCE],
        default=LOCAL_SOURCE,
        key="plate_session_source_kind",
    ) or LOCAL_SOURCE
    previous_kind = st.session_state.get("plate_session_active_source_kind")
    if previous_kind is not None and previous_kind != source_kind:
        cleanup_plate_session(st.session_state)
        initialize_plate_session(st.session_state)
    st.session_state["plate_session_active_source_kind"] = source_kind

    catalog = discover_local_videos(
        PROJECT_ROOT, built_in_video=DEMO_VIDEO_RELATIVE
    )
    selected_relative = DEMO_VIDEO_RELATIVE
    source_token = source_kind
    input_ready = True
    if source_kind == LOCAL_SOURCE:
        paths = [item.relative_path for item in catalog]
        selected_relative = st.selectbox(
            "Video OCR local",
            paths,
            key="plate_session_local_video",
            format_func=lambda path: next(
                item.filename for item in catalog if item.relative_path == path
            ),
        )
        source_token = f"local:{selected_relative}"
    elif source_kind == UPLOAD_SOURCE:
        uploaded = st.file_uploader(
            "Cargar video OCR",
            type=sorted(item.lstrip(".") for item in ALLOWED_UPLOAD_EXTENSIONS),
            accept_multiple_files=False,
            max_upload_size=MAX_UPLOAD_SIZE_MIB,
            key="plate_session_upload_widget",
        )
        handle = _process_plate_upload(uploaded)
        upload_hash = (
            handle.sha256
            if handle is not None
            else st.session_state.get("plate_session_uploaded_hash")
        )
        source_token = f"upload:{upload_hash}" if upload_hash else "upload:none"
        input_ready = handle is not None
        if handle is not None:
            st.caption(
                f"{handle.original_name} · {handle.size_bytes / 1024 / 1024:.2f} MiB"
            )
    else:
        st.warning(
            "La cámara es opcional y solo se abre al iniciar; las pruebas no requieren "
            "un dispositivo físico.",
            icon=":material/videocam:",
        )
        source_token = "camera:0"

    previous_token = st.session_state.get("plate_session_active_source_token")
    if previous_token is not None and previous_token != source_token:
        cleanup_plate_session(st.session_state)
        initialize_plate_session(st.session_state)
        if source_kind == UPLOAD_SOURCE and uploaded is not None:
            handle = _process_plate_upload(uploaded)
            input_ready = handle is not None
    st.session_state["plate_session_active_source_token"] = source_token

    every_n = st.slider(
        "Evaluar OCR cada N frames",
        min_value=1,
        max_value=30,
        value=15,
        key="plate_session_every_n_frames",
    )
    st.caption(
        "En CPU se recomienda iniciar en 10–15. Auméntalo si necesitas una "
        "visualización más fluida; la calidad OCR no se reduce automáticamente."
    )
    protect_viewer = st.toggle(
        "Enmascarar matrículas en el visor",
        key="plate_session_protect_viewer",
        help=(
            "Desactívalo explícitamente para mostrar texto completo y la región "
            "sin ocultar. El fotograma permanece solo en esta sesión."
        ),
    )
    if not protect_viewer:
        st.warning(
            "Privacidad desactivada: el visor puede mostrar matrículas completas.",
            icon=":material/visibility:",
        )
    backend = "disponible" if _paddleocr_available() else "no instalado"
    st.caption(f"Backend PaddleOCR: {backend} · Placas ocultas por defecto")

    controller = st.session_state.get("plate_session_controller")
    state = (
        controller.state
        if isinstance(controller, PlateAnalysisController)
        else (
            PlateAnalysisState.ERROR
            if st.session_state.get("plate_session_error")
            else PlateAnalysisState.IDLE
        )
    )
    with st.container(horizontal=True):
        if st.button(
            "Iniciar",
            type="primary",
            disabled=not input_ready or state is not PlateAnalysisState.IDLE,
        ):
            _start_real_ocr(source_kind, selected_relative, every_n)
            st.rerun()
        if st.button(
            "Pausar", disabled=state is not PlateAnalysisState.RUNNING
        ) and isinstance(controller, PlateAnalysisController):
            controller.pause()
            st.rerun()
        if st.button(
            "Continuar", disabled=state is not PlateAnalysisState.PAUSED
        ) and isinstance(controller, PlateAnalysisController):
            controller.resume()
            st.rerun()
        if st.button(
            "Procesar siguiente fotograma",
            disabled=state
            not in {PlateAnalysisState.RUNNING, PlateAnalysisState.PAUSED},
        ) and isinstance(controller, PlateAnalysisController):
            _sync_plate_controller(controller, single_step=True)
            st.session_state["plate_session_skip_auto_once"] = True
            st.rerun()
        if st.button(
            "Finalizar",
            disabled=state not in {PlateAnalysisState.RUNNING, PlateAnalysisState.PAUSED},
        ) and isinstance(controller, PlateAnalysisController):
            batch = controller.finish()
            st.session_state["plate_session_batch_readings"] = batch.readings
            _cleanup_finished_upload()
            st.rerun()
        st.button(
            "Reiniciar",
            disabled=controller is None
            and not st.session_state.get("plate_session_error"),
            on_click=_reset_real_ocr_session,
        )

    error = st.session_state.get("plate_session_error", "")
    if error:
        st.error(str(error))

    _render_progressive_viewer(source_kind)

    readings = tuple(st.session_state.get("plate_session_batch_readings", ()))
    reviews = dict(st.session_state.get("plate_session_reviews", {}))
    if not readings:
        st.info("Aún no hay lecturas OCR reales en este lote independiente.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Lectura": mask_plate_text(item.normalized_text),
                    "Confianza": item.confidence,
                    "Timestamp": item.timestamp_seconds,
                    "Estado": reviews.get(item.reading_id, item).status.value,
                    "Origen": item.origin.value,
                }
                for item in readings
            ]
        ),
        hide_index=True,
    )
    by_id = {item.reading_id: item for item in readings}
    selected_id = st.selectbox(
        "Lectura OCR real",
        list(by_id),
        format_func=lambda value: mask_plate_text(by_id[value].normalized_text),
        key="plate_session_selected_reading_id",
    )
    selected = by_id[selected_id]
    reviewer = st.selectbox("Revisor OCR", REVIEWERS, key="plate_session_reviewer")
    visible = st.session_state.get("plate_session_visible_reading_id") == selected_id
    if st.button("Ocultar lectura" if visible else "Mostrar lectura"):
        toggle_plate_reveal(st.session_state, selected_id, reviewer)
        st.rerun()
    visible = st.session_state.get("plate_session_visible_reading_id") == selected_id
    st.text_input(
        "Lectura detectada",
        value=selected.raw_text if visible else mask_plate_text(selected.normalized_text),
        disabled=True,
        key=f"plate_session_display_{selected_id}",
    )
    correction = st.text_input(
        "Corrección manual",
        value="",
        placeholder="Ingrese la lectura corregida",
        key=f"plate_session_correction_{selected_id}",
    )
    review_left, review_right = st.columns(2)
    if review_left.button("Guardar corrección OCR"):
        try:
            correct_plate_reading(
                st.session_state, selected_id, correction, reviewer
            )
            st.success("Corrección OCR guardada para revisión; no afecta el aforo.")
        except ValueError as exc:
            st.error(str(exc))
    if review_right.button("Rechazar lectura OCR"):
        reject_plate_reading(st.session_state, selected_id, reviewer)
        st.warning("Lectura OCR rechazada; no se inventó una sustitución.")


initialize_plate_session(st.session_state)
page_mode = st.segmented_control(
    "Modo de lecturas de placas",
    [SYNTHETIC_MODE, REAL_MODE],
    default=SYNTHETIC_MODE,
    key="plate_session_ui_mode",
) or SYNTHETIC_MODE
previous_page_mode = st.session_state.get("plate_session_active_ui_mode")
if previous_page_mode == REAL_MODE and page_mode != REAL_MODE:
    cleanup_plate_session(st.session_state)
    initialize_plate_session(st.session_state)
st.session_state["plate_session_active_ui_mode"] = page_mode
if page_mode == REAL_MODE:
    _render_real_ocr()
    st.stop()


readings = _load_readings()
initialize_ocr_session(st.session_state, readings)

heading, actions = st.columns([7, 5], vertical_alignment="center")
with heading:
    st.title("Lecturas de placas")
    st.markdown(
        render_status_chip("Experimental", "info") + " " +
        render_status_chip("Datos sintéticos", "neutral"),
        unsafe_allow_html=True,
    )
with actions:
    with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
        if st.button("Volver al monitoreo", icon=":material/arrow_back:", width="content"):
            st.switch_page("pages/traffic_monitoring.py")
        st.download_button(
            "Exportar lecturas revisadas",
            data=export_reviewed_csv(readings, st.session_state["ocr_review_records"]),
            file_name="lecturas_ocr_sinteticas_revisadas.csv", mime="text/csv",
            icon=":material/download:", type="primary", width="content",
        )

st.info("Las lecturas requieren validación humana.", icon=":material/privacy_tip:")

summary = summarize_readings(readings, st.session_state["ocr_review_records"])
with st.container(horizontal=True):
    st.metric("Detectadas", summary.detected, border=True)
    st.metric("Válidas", summary.valid, border=True)
    st.metric("Dudosas", summary.doubtful, border=True)
    st.metric("Pendientes", summary.pending, border=True)
    st.metric("Ilegibles", summary.illegible, border=True)
    st.metric("Confianza media", f"{summary.average_confidence_percent:.0f}%", border=True)

with st.container(border=True, gap="small"):
    st.markdown("**Filtros**")
    f_date, f_status, f_category, f_direction, f_conf = st.columns(5)
    selected_date = f_date.date_input("Fecha", value=readings[0].timestamp.date(), key="ocr_filter_date")
    status_filter = f_status.selectbox("Estado", ["Todos", *[item.value for item in PlateReviewStatus]], key="ocr_filter_status")
    category_filter = f_category.selectbox("Categoría", ["Todas", *sorted({item.vehicle_category for item in readings})], key="ocr_filter_category")
    direction_filter = f_direction.selectbox("Sentido", ["Todos", *sorted({item.direction for item in readings})], key="ocr_filter_direction")
    min_confidence = f_conf.slider("Confianza mínima", 0, 100, 0, 5, key="ocr_filter_confidence")
    search = st.text_input("Buscar lectura", placeholder="reading_id, track_id o placa anonimizada", key="ocr_filter_search")
    st.session_state["ocr_filters"] = {
        "date": selected_date.isoformat(), "status": status_filter,
        "category": category_filter, "direction": direction_filter,
        "minimum_confidence": min_confidence, "search": search,
    }

filtered = [item for item in readings if item.timestamp.date() == selected_date]
if status_filter != "Todos":
    filtered = [item for item in filtered if item.status.value == status_filter]
if category_filter != "Todas":
    filtered = [item for item in filtered if item.vehicle_category == category_filter]
if direction_filter != "Todos":
    filtered = [item for item in filtered if item.direction == direction_filter]
filtered = [item for item in filtered if item.confidence * 100 >= min_confidence]
needle = search.strip().upper()
if needle:
    filtered = [item for item in filtered if needle in f"{item.reading_id} {item.track_id} {item.masked_text}".upper()]

left, right = st.columns([8, 4], gap="medium")
with left:
    with st.container(border=True, gap="small"):
        st.markdown(f"**Lecturas protegidas** · {len(filtered)} registros")
        if filtered:
            selection_ids = [item.reading_id for item in filtered]
            current = st.session_state.get("ocr_selected_reading_id")
            selected_index = selection_ids.index(current) if current in selection_ids else 0
            chosen = st.selectbox("Revisar lectura", selection_ids, index=selected_index, key="ocr_selected_widget_id")
            select_reading(st.session_state, chosen)
            table = pd.DataFrame([{
                "Hora": item.timestamp.strftime("%H:%M:%S"), "Lectura ID": item.reading_id,
                "Track ID": item.track_id, "Miniatura protegida": _protected_data_url(item.original_text),
                "Placa anonimizada": item.masked_text, "Confianza": item.confidence,
                "Categoría": item.vehicle_category, "Sentido": item.direction,
                "Estado": st.session_state["ocr_review_records"].get(item.reading_id, item).status.value,
            } for item in filtered])
            st.dataframe(
                table, hide_index=True, height=390,
                column_config={
                    "Miniatura protegida": st.column_config.ImageColumn("Miniatura"),
                    "Confianza": st.column_config.ProgressColumn("Confianza", min_value=0, max_value=1, format="percent"),
                },
            )
        else:
            chosen = None
            st.warning("No hay lecturas para los filtros seleccionados.")

with right:
    with st.container(border=True, gap="small"):
        st.markdown("**Revisión manual**")
        selected_id = st.session_state.get("ocr_selected_reading_id") if chosen else None
        selected = next((item for item in readings if item.reading_id == selected_id), None)
        if selected is None:
            st.info("Seleccione una lectura para revisar.")
        else:
            frame_path = PROJECT_ROOT / selected.frame_image_path
            if frame_path.is_file():
                st.image(str(frame_path), caption="Fotograma sintético de referencia", width="stretch")
            reviewer = st.selectbox("Revisor", REVIEWERS, key="ocr_reviewer")
            visible = st.session_state.get("ocr_visible_reading_id") == selected.reading_id
            if st.button(
                "Ocultar placa" if visible else "Mostrar placa",
                icon=":material/visibility_off:" if visible else ":material/visibility:",
                key="ocr_toggle_visibility", width="stretch",
            ):
                toggle_plate_visibility(st.session_state, selected.reading_id, reviewer)
                st.rerun()
            visible = st.session_state.get("ocr_visible_reading_id") == selected.reading_id
            st.image(
                render_plate_crop(selected.original_text, protected=not visible),
                caption="Recorte legible auditado" if visible else "Recorte protegido",
                width="stretch",
            )
            shown_text = selected.original_text if visible else selected.masked_text
            st.text_input("Lectura original OCR (inmutable)", value=shown_text, disabled=True, key=f"ocr_original_{selected.reading_id}")
            st.caption(f"Confianza: {selected.confidence:.0%} · Alternativas: {', '.join(selected.suggested_alternatives) or 'Ninguna'}")
            corrected = st.text_input("Lectura corregida", value=selected.original_text, key=f"ocr_corrected_{selected.reading_id}")
            reason = st.selectbox("Motivo de corrección", REASONS, key=f"ocr_reason_{selected.reading_id}")
            notes = st.text_area("Observaciones", key=f"ocr_notes_{selected.reading_id}")

            action_a, action_b = st.columns(2)
            if action_a.button("Confirmar sin cambios", key="ocr_confirm_unchanged", width="stretch"):
                try:
                    save_review(st.session_state, confirm_unchanged(selected, reviewer, notes))
                    st.success("Lectura confirmada sin cambios.")
                except ValueError as exc:
                    st.error(str(exc))
            if action_b.button("Guardar corrección", type="primary", key="ocr_confirm_correction", width="stretch"):
                try:
                    request = PlateCorrectionRequest(selected.reading_id, corrected, "" if reason == REASONS[0] else reason, notes, reviewer)
                    save_review(st.session_state, confirm_correction(selected, request))
                    st.success("Corrección guardada y confirmada.")
                except ValueError as exc:
                    st.error(str(exc))
            state_a, state_b = st.columns(2)
            if state_a.button("Marcar como dudosa", key="ocr_mark_doubtful", width="stretch"):
                save_review(st.session_state, mark_status(selected, PlateReviewStatus.DOUBTFUL, reviewer, notes))
                st.warning("Lectura marcada como dudosa.")
            if state_b.button("Marcar como ilegible", key="ocr_mark_illegible", width="stretch"):
                save_review(st.session_state, mark_status(selected, PlateReviewStatus.ILLEGIBLE, reviewer, notes))
                st.warning("Lectura marcada como ilegible.")
            with st.expander("Historial y auditoría"):
                review = st.session_state["ocr_review_records"].get(selected.reading_id)
                if review:
                    st.write(f"Estado: {review.status.value} · Revisor: {review.reviewed_by} · {review.reviewed_at.isoformat()}")
                reveal_events = [item for item in st.session_state["ocr_reveal_audit"] if item.reading_id == selected.reading_id]
                for event in reveal_events:
                    st.caption(f"{event.action} · {event.reviewed_by} · {event.revealed_at.isoformat()}")
