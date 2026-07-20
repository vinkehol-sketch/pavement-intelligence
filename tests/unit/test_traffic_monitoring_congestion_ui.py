from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pavement_intelligence.domain.traffic.congestion import CongestionLevel
from pavement_intelligence.domain.traffic.congestion_runtime import (
    CongestionRuntimeState,
)
from pavement_intelligence.ui.utils import congestion_session
from pavement_intelligence.ui.utils.congestion_session import (
    ALERTS_KEY,
    COORDINATOR_KEY,
    ERROR_KEY,
    LAST_FRAME_KEY,
    PRESENTATION_KEY,
    SNAPSHOT_KEY,
    SOURCE_ID_KEY,
    clear_congestion_session,
    finish_congestion_session,
    initialize_congestion_session,
    pause_congestion_session,
    process_congestion_result_once,
    reset_congestion_session,
    resume_congestion_session,
    start_congestion_session,
)
from pavement_intelligence.ui.utils.uploaded_video import store_uploaded_video
from pavement_intelligence.vision.analysis import AnalysisState, FrameAnalysisResult
from pavement_intelligence.vision.capture import SourceInfo


ROOT = Path(__file__).resolve().parents[2]
MONITORING_PAGE = ROOT / "src/pavement_intelligence/ui/pages/traffic_monitoring.py"
APP_ENTRYPOINT = ROOT / "src/pavement_intelligence/ui/app.py"
DEMO_VIDEO_RELATIVE = "data/samples/ui/assets/traffic_monitoring_demo.mp4"
COMPLEX_VIDEO_RELATIVE = "data/videos/samples/complex_traffic.mp4"
DEMO_VIDEO_PATH = ROOT / DEMO_VIDEO_RELATIVE
COMPLEX_VIDEO_PATH = ROOT / COMPLEX_VIDEO_RELATIVE


@dataclass(frozen=True)
class FakeResult:
    frame_index: int
    timestamp_seconds: float
    vehicles_in_scene: int = 2
    crossing_events: tuple[object, ...] = ()
    direction_counts: dict[object, int] | None = None
    source_type: str = "video_file"
    warnings: tuple[str, ...] = ()
    end_of_source: bool = False

    def __post_init__(self):
        if self.direction_counts is None:
            object.__setattr__(self, "direction_counts", {})


def frame(index: int, timestamp: float, **kwargs):
    return FakeResult(index, timestamp, **kwargs)


def ready_session():
    session = {}
    initialize_congestion_session(session)
    start_congestion_session(session, "video-a.mp4", monitoring_point_id="P-04")
    return session


def warm(session):
    process_congestion_result_once(session, frame(1, 0))
    process_congestion_result_once(session, frame(2, 5))
    return process_congestion_result_once(session, frame(3, 10))


def confirm_high(session):
    process_congestion_result_once(session, frame(1, 0, vehicles_in_scene=10))
    process_congestion_result_once(session, frame(2, 5, vehicles_in_scene=12))
    process_congestion_result_once(session, frame(3, 10, vehicles_in_scene=14))
    process_congestion_result_once(session, frame(4, 15, vehicles_in_scene=18))
    return process_congestion_result_once(session, frame(5, 30, vehicles_in_scene=20))


def test_session_keys_are_isolated_and_initialized():
    session = {}
    initialize_congestion_session(session)
    assert {
        COORDINATOR_KEY,
        SNAPSHOT_KEY,
        PRESENTATION_KEY,
        ERROR_KEY,
        SOURCE_ID_KEY,
        LAST_FRAME_KEY,
        ALERTS_KEY,
    } <= session.keys()
    assert not any(
        key.startswith("traffic_review") or key.startswith("tpda") for key in session
    )


def test_start_creates_new_coordinator_and_clears_previous_batch():
    session = ready_session()
    first = session[COORDINATOR_KEY]
    warm(session)
    second = start_congestion_session(session, "video-b.mp4")
    assert second is not first and second.source_id == "video-b.mp4"
    assert session[SNAPSHOT_KEY] is session[PRESENTATION_KEY] is None
    assert session[ALERTS_KEY] == () and session[LAST_FRAME_KEY] is None


def test_real_result_is_processed_once_across_reruns():
    session = ready_session()
    result = frame(1, 0)
    first = process_congestion_result_once(session, result)
    second = process_congestion_result_once(session, result)
    assert second is first
    assert session[SNAPSHOT_KEY].sample_count == 1


def test_frame_key_includes_source_index_timestamp_and_terminal_flag():
    key = congestion_session.congestion_frame_key("video", frame(7, 1.25))
    terminal = congestion_session.congestion_frame_key(
        "video", frame(7, 1.25, end_of_source=True)
    )
    assert key == ("video", 7, 1.25, False)
    assert terminal != key


def test_pause_and_resume_keep_valid_observation_time():
    session = ready_session()
    active = warm(session)
    paused = pause_congestion_session(session)
    resumed = resume_congestion_session(session)
    assert paused.is_paused and not resumed.is_paused
    assert paused.observation_time_text == active.observation_time_text
    assert session[COORDINATOR_KEY].state is CongestionRuntimeState.ACTIVE


def test_reset_clears_snapshot_alert_and_deduplication():
    session = ready_session()
    confirm_high(session)
    reset_congestion_session(session, "video-a.mp4")
    assert session[SNAPSHOT_KEY] is session[PRESENTATION_KEY] is None
    assert session[ALERTS_KEY] == () and session[LAST_FRAME_KEY] is None
    assert session[COORDINATOR_KEY].state is CongestionRuntimeState.IDLE


def test_source_change_never_keeps_previous_window_or_alert():
    session = ready_session()
    confirm_high(session)
    start_congestion_session(session, "camera:0")
    process_congestion_result_once(
        session, frame(1, 100, source_type="camera", vehicles_in_scene=1)
    )
    assert session[SNAPSHOT_KEY].sample_count == 1
    assert session[SNAPSHOT_KEY].level is CongestionLevel.INSUFFICIENT_DATA
    assert session[ALERTS_KEY] == ()


def test_finish_is_idempotent_and_preserves_last_snapshot():
    session = ready_session()
    warm(session)
    first = finish_congestion_session(session)
    second = finish_congestion_session(session)
    assert second == first and second.is_final
    assert session[SNAPSHOT_KEY].is_final


def test_confirmed_alert_is_deduplicated_by_alert_id():
    session = ready_session()
    confirmed = confirm_high(session)
    process_congestion_result_once(session, frame(6, 45, vehicles_in_scene=22))
    assert confirmed.level_code == "HIGH"
    assert len(session[ALERTS_KEY]) == 1
    assert session[ALERTS_KEY][0].alert_id == session[SNAPSHOT_KEY].alert.alert_id


class BrokenCoordinator:
    source_id = "video-a.mp4"

    def process_frame_result(self, result):
        raise RuntimeError("motor no disponible")


def test_congestion_error_is_controlled_without_discarding_previous_view():
    session = ready_session()
    previous = process_congestion_result_once(session, frame(1, 0))
    session[COORDINATOR_KEY] = BrokenCoordinator()
    returned = process_congestion_result_once(session, frame(2, 1))
    assert returned is previous
    assert session[ERROR_KEY] == "motor no disponible"


def test_congestion_lifecycle_does_not_approve_or_transfer_counts():
    sentinel = {"batch": "untouched"}
    session = {
        "traffic_review_approved": False,
        "tpda_input_from_review": sentinel,
        "traffic_counts_corrected": {"AUTO": 3},
    }
    start_congestion_session(session, "video")
    warm(session)
    finish_congestion_session(session)
    clear_congestion_session(session)
    assert session["traffic_review_approved"] is False
    assert session["tpda_input_from_review"] is sentinel
    assert session["traffic_counts_corrected"] == {"AUTO": 3}


def real_frame_result():
    return FrameAnalysisResult(
        frame_index=1,
        timestamp_seconds=0.0,
        source_type="video_file",
        annotated_frame=None,
        detections=(),
        active_tracks=(),
        crossing_events=(),
        category_counts={},
        direction_counts={},
        vehicles_in_scene=0,
        total_crossings=0,
        processing_fps=20,
        warnings=(),
        end_of_source=False,
        congestion="INSUFFICIENT_DATA",
    )


class AppTestController:
    state = AnalysisState.RUNNING
    events = ()

    def __init__(self):
        self.last_result = real_frame_result()
        self.calls = 0

    def process_next(self):
        self.calls += 1
        return self.last_result

    def close(self):
        self.state = AnalysisState.FINISHED


def real_video_app():
    controller = AppTestController()
    app = AppTest.from_file(str(MONITORING_PAGE), default_timeout=30)
    app.session_state["traffic_analysis_source_type"] = "Video pregrabado"
    app.session_state["traffic_analysis_active_mode"] = "Video pregrabado"
    app.session_state["traffic_analysis_controller"] = controller
    app.session_state["traffic_analysis_source_metadata"] = SourceInfo(
        "video-a.mp4", "video_file", 8, 100, 50, 64, 1
    )
    app.session_state["traffic_analysis_error"] = ""
    congestion_state = {}
    start_congestion_session(congestion_state, "video-a.mp4")
    for key, value in congestion_state.items():
        app.session_state[key] = value
    return app, controller


def test_real_video_apptest_uses_snapshot_without_exceptions_or_duplicates():
    app, controller = real_video_app()
    app.run()
    assert not app.exception
    assert app.session_state[SNAPSHOT_KEY].sample_count == 1
    metric_labels = {metric.label for metric in app.metric}
    assert {
        "Flujo",
        "En escena",
        "Acumulación",
        "Tiempo observado",
        "Velocidad",
    } <= metric_labels
    assert any(
        "no corresponde a un Nivel de Servicio normativo" in caption.value
        for caption in app.caption
    )
    assert all("MÉTRICAS SIMULADAS" not in item.value for item in app.markdown)
    app.run()
    assert not app.exception
    assert app.session_state[SNAPSHOT_KEY].sample_count == 1
    assert controller.calls >= 1


def test_static_apptest_is_separate_and_does_not_create_coordinator():
    app = AppTest.from_file(str(MONITORING_PAGE), default_timeout=30).run()
    assert not app.exception
    assert app.segmented_control[0].value == "Imagen demostrativa"
    assert app.session_state[COORDINATOR_KEY] is None
    assert app.session_state[SNAPSHOT_KEY] is None


def test_camera_apptest_does_not_open_device_or_create_congestion_batch():
    app = AppTest.from_file(str(MONITORING_PAGE), default_timeout=30).run()
    app.segmented_control[0].set_value("Cámara en vivo").run()
    assert not app.exception
    assert app.session_state[COORDINATOR_KEY] is None


def video_selection_app():
    app = AppTest.from_file(str(MONITORING_PAGE), default_timeout=30).run()
    app.segmented_control[0].set_value("Video pregrabado").run()
    assert not app.exception
    return app


def uploaded_video_app():
    app = video_selection_app()
    source_control = next(
        item
        for item in app.segmented_control
        if item.label == "Origen del video pregrabado"
    )
    source_control.set_value("Cargar video").run()
    assert not app.exception
    return app


def upload_demo_video(app, *, name="session-video.mp4"):
    app.file_uploader[0].set_value(
        (name, DEMO_VIDEO_PATH.read_bytes(), "video/mp4")
    ).run()
    assert not app.exception
    return app.session_state["traffic_uploaded_video_handle"]


def test_video_selector_lists_controlled_videos_and_preserves_demo_default():
    app = video_selection_app()
    selector = app.selectbox[0]
    assert selector.label == "Seleccionar video de análisis"
    assert selector.value == DEMO_VIDEO_RELATIVE
    assert app.session_state["traffic_selected_video_path"] == DEMO_VIDEO_RELATIVE
    assert app.session_state["traffic_selected_video_duration"] == 8.0
    assert any("complex_traffic.mp4" in option for option in selector.options)
    assert any("video dura menos de 10 segundos" in item.value for item in app.warning)


def test_selecting_complex_video_updates_safe_path_without_auto_start():
    app = video_selection_app()
    app.selectbox[0].set_value(COMPLEX_VIDEO_RELATIVE).run()
    assert not app.exception
    assert app.session_state["traffic_selected_video_path"] == COMPLEX_VIDEO_RELATIVE
    assert app.session_state["traffic_selected_video_duration"] == pytest.approx(
        53.9166666667
    )
    assert app.session_state["traffic_analysis_controller"] is None
    assert app.session_state["traffic_analysis_running"] is False
    assert any("supera el calentamiento de 10 segundos" in item.value for item in app.info)


def test_start_uses_selected_complex_video_without_loading_yolo(monkeypatch):
    opened_paths = []

    class SelectedVideoSource:
        def __init__(self, path):
            self.path = Path(path)
            opened_paths.append(self.path)

        def close(self):
            return None

    class SelectedVideoController:
        events = ()

        def __init__(self, source, pipeline_factory):
            self.source = source
            self.pipeline_factory = pipeline_factory
            self.state = AnalysisState.IDLE
            self.last_result = None

        def start(self):
            self.state = AnalysisState.RUNNING
            return SourceInfo(
                self.source.path.name, "video_file", 12, 640, 360, 647, 0
            )

        def process_next(self):
            return None

        def close(self):
            self.state = AnalysisState.FINISHED

        def finish(self):
            self.close()
            return ()

    monkeypatch.setattr(
        "pavement_intelligence.vision.capture.VideoFileSource", SelectedVideoSource
    )
    monkeypatch.setattr(
        "pavement_intelligence.vision.analysis.TrafficAnalysisController",
        SelectedVideoController,
    )

    app = video_selection_app()
    app.selectbox[0].set_value(COMPLEX_VIDEO_RELATIVE).run()
    next(button for button in app.button if button.label == "Iniciar análisis").click().run()

    assert not app.exception
    assert opened_paths == [ROOT / COMPLEX_VIDEO_RELATIVE]
    assert app.session_state[COORDINATOR_KEY] is not None
    assert app.session_state[SOURCE_ID_KEY].startswith("local-video:")
    assert app.session_state["traffic_analysis_running"] is True


def test_changing_selected_video_closes_previous_lot_and_congestion():
    app, controller = real_video_app()
    app.run()
    assert app.session_state[SNAPSHOT_KEY] is not None
    app.session_state[ALERTS_KEY] = ("old-alert",)
    app.session_state["traffic_analysis_batch_events"] = ["old-event"]

    app.selectbox[0].set_value(COMPLEX_VIDEO_RELATIVE).run()

    assert not app.exception
    assert controller.state is AnalysisState.FINISHED
    assert app.session_state["traffic_analysis_controller"] is None
    assert app.session_state[SNAPSHOT_KEY] is None
    assert app.session_state[PRESENTATION_KEY] is None
    assert app.session_state[ERROR_KEY] == ""
    assert app.session_state[ALERTS_KEY] == ()
    assert app.session_state[LAST_FRAME_KEY] is None
    assert app.session_state["traffic_analysis_batch_events"] == []
    assert app.session_state["traffic_analysis_current_result"] is None
    assert app.session_state["traffic_analysis_running"] is False


def test_video_selector_is_hidden_in_static_and_camera_modes():
    app = AppTest.from_file(str(MONITORING_PAGE), default_timeout=30).run()
    assert not app.selectbox
    app.segmented_control[0].set_value("Cámara en vivo").run()
    assert not app.exception
    assert all(
        selector.label != "Seleccionar video de análisis" for selector in app.selectbox
    )
    assert app.session_state["traffic_analysis_controller"] is None


def test_video_change_does_not_approve_review_or_transfer_tpda():
    app = video_selection_app()
    sentinel = {"source": "previous-reviewed-batch"}
    app.session_state["traffic_review_approved"] = False
    app.session_state["tpda_input_from_review"] = sentinel
    app.selectbox[0].set_value(COMPLEX_VIDEO_RELATIVE).run()
    assert app.session_state["traffic_review_approved"] is False
    assert app.session_state["tpda_input_from_review"] is sentinel


def test_upload_option_and_uploader_only_appear_in_uploaded_video_mode():
    app = video_selection_app()
    assert any(
        item.label == "Origen del video pregrabado" for item in app.segmented_control
    )
    assert not app.file_uploader
    app = uploaded_video_app()
    assert len(app.file_uploader) == 1
    assert app.file_uploader[0].label == "Cargar video de análisis"
    assert not app.file_uploader[0].accept_multiple_files
    app.segmented_control[0].set_value("Cámara en vivo").run()
    assert not app.file_uploader


def test_uploaded_video_shows_metadata_privacy_and_does_not_auto_start():
    app = uploaded_video_app()
    handle = upload_demo_video(app, name="authorized.mp4")
    try:
        captions = [item.value for item in app.caption]
        assert any("authorized.mp4" in value and "1.54 MiB" in value for value in captions)
        assert any("no se incorpora al repositorio" in value for value in captions)
        assert any("datos sensibles" in item.value for item in app.warning)
        assert app.session_state["traffic_analysis_controller"] is None
        assert app.session_state["traffic_analysis_running"] is False
        start = next(button for button in app.button if button.label == "Iniciar análisis")
        assert not start.disabled
        assert handle.duration_seconds == 8.0
        assert handle.temporary_path.is_file()
    finally:
        next(
            item
            for item in app.segmented_control
            if item.label == "Origen del video pregrabado"
        ).set_value("Video local del proyecto").run()


def test_same_uploaded_file_reuses_temporary_handle_across_reruns():
    app = uploaded_video_app()
    first = upload_demo_video(app)
    first_path = first.temporary_path
    app.run()
    second = app.session_state["traffic_uploaded_video_handle"]
    assert second is first
    assert second.temporary_path == first_path
    assert first_path.is_file()
    next(
        item
        for item in app.segmented_control
        if item.label == "Origen del video pregrabado"
    ).set_value("Video local del proyecto").run()
    assert not first_path.exists()


def test_replacing_upload_removes_previous_temporary_file():
    app = uploaded_video_app()
    previous = upload_demo_video(app, name="first.mp4")
    previous_path = previous.temporary_path
    app.file_uploader[0].set_value(
        ("replacement.mp4", COMPLEX_VIDEO_PATH.read_bytes(), "video/mp4")
    ).run()
    replacement = app.session_state["traffic_uploaded_video_handle"]
    assert not app.exception
    assert not previous_path.exists()
    assert replacement.temporary_path.is_file()
    assert replacement.sha256 != previous.sha256
    next(
        item
        for item in app.segmented_control
        if item.label == "Origen del video pregrabado"
    ).set_value("Video local del proyecto").run()


@pytest.mark.parametrize("target_mode", ("Imagen demostrativa", "Cámara en vivo"))
def test_leaving_video_mode_cleans_uploaded_temporary(target_mode):
    app = uploaded_video_app()
    handle = upload_demo_video(app)
    temporary_path = handle.temporary_path
    app.segmented_control[0].set_value(target_mode).run()
    assert not app.exception
    assert not temporary_path.exists()
    assert app.session_state["traffic_uploaded_video_handle"] is None
    assert app.session_state[COORDINATOR_KEY] is None


def test_corrupt_upload_is_controlled_and_never_starts_analysis():
    app = uploaded_video_app()
    app.file_uploader[0].set_value(
        ("corrupt.mp4", b"not-a-video", "video/mp4")
    ).run()
    assert not app.exception
    assert app.session_state["traffic_uploaded_video_handle"] is None
    assert app.session_state["traffic_analysis_controller"] is None
    assert any("OpenCV no pudo abrir" in item.value for item in app.error)
    start = next(button for button in app.button if button.label == "Iniciar análisis")
    assert start.disabled


def test_missing_temporary_file_is_controlled_before_start():
    app = uploaded_video_app()
    handle = upload_demo_video(app)
    handle.temporary_path.unlink()
    app.run()
    assert not app.exception
    assert app.session_state["traffic_uploaded_video_handle"] is None
    assert app.session_state["traffic_analysis_controller"] is None
    assert any("temporal ya no está disponible" in item.value for item in app.error)
    start = next(button for button in app.button if button.label == "Iniciar análisis")
    assert start.disabled


def test_uploaded_video_start_pause_reset_and_finish_are_clean(monkeypatch):
    opened_paths = []

    class UploadedSource:
        def __init__(self, path):
            self.path = Path(path)
            opened_paths.append(self.path)

        def close(self):
            return None

    class UploadedController:
        events = ()

        def __init__(self, source, pipeline_factory):
            self.source = source
            self.pipeline_factory = pipeline_factory
            self.state = AnalysisState.IDLE
            self.last_result = real_frame_result()

        def metadata(self):
            return SourceInfo(self.source.path.name, "video_file", 8, 100, 50, 64, 0)

        def start(self):
            self.state = AnalysisState.RUNNING
            return self.metadata()

        def process_next(self):
            return self.last_result

        def pause(self):
            self.state = AnalysisState.PAUSED

        def resume(self):
            self.state = AnalysisState.RUNNING

        def reset(self):
            self.state = AnalysisState.RUNNING
            return self.metadata()

        def close(self):
            self.state = AnalysisState.FINISHED

        def finish(self):
            self.close()
            return ()

    monkeypatch.setattr(
        "pavement_intelligence.vision.capture.VideoFileSource", UploadedSource
    )
    monkeypatch.setattr(
        "pavement_intelligence.vision.analysis.TrafficAnalysisController",
        UploadedController,
    )

    app = uploaded_video_app()
    handle = upload_demo_video(app)
    temporary_path = handle.temporary_path
    next(button for button in app.button if button.label == "Iniciar análisis").click().run()
    assert not app.exception
    assert opened_paths == [temporary_path]
    assert app.session_state[SOURCE_ID_KEY].startswith("uploaded-video:")
    assert app.session_state[SNAPSHOT_KEY].level is CongestionLevel.INSUFFICIENT_DATA

    next(button for button in app.button if button.label == "Pausar").click().run()
    assert app.session_state["traffic_analysis_paused"] is True
    next(button for button in app.button if button.label == "Continuar").click().run()
    assert app.session_state["traffic_analysis_running"] is True
    next(button for button in app.button if button.label == "Reiniciar").click().run()
    assert app.session_state[SNAPSHOT_KEY].sample_count == 1

    next(button for button in app.button if button.label == "Finalizar análisis").click().run()
    assert not app.exception
    assert not temporary_path.exists()
    assert app.session_state[SNAPSHOT_KEY].is_final
    assert app.session_state["traffic_analysis_controller"].state is AnalysisState.FINISHED
    assert app.session_state["traffic_review_approved"] is False


def test_navigation_away_closes_controller_and_cleans_upload(tmp_path):
    class Upload:
        name = "session.mp4"
        type = "video/mp4"
        data = b"video"
        size = len(data)

        def getvalue(self):
            return self.data

    class Controller:
        closed = False

        def close(self):
            self.closed = True

    handle = store_uploaded_video(
        Upload(),
        temporary_parent=tmp_path,
        duration_reader=lambda _path: 12.0,
    )
    temporary_path = handle.temporary_path
    controller = Controller()
    app = AppTest.from_file(str(APP_ENTRYPOINT), default_timeout=30)
    app.session_state["traffic_analysis_controller"] = controller
    app.session_state["traffic_uploaded_video_handle"] = handle
    app.session_state["traffic_uploaded_video_hash"] = handle.sha256
    app.session_state["traffic_uploaded_video_cleanup_token"] = handle.cleanup_token
    app.run()
    assert not app.exception
    assert controller.closed
    assert not temporary_path.exists()
    assert app.session_state["traffic_analysis_controller"] is None
    assert app.session_state["traffic_uploaded_video_handle"] is None
    assert app.session_state[COORDINATOR_KEY] is None


def test_page_contains_no_congestion_engine_or_aggregator_calculation():
    source = MONITORING_PAGE.read_text(encoding="utf-8")
    assert "CongestionEngine" not in source
    assert "CongestionIntervalAggregator" not in source
    assert "high_confirmation_seconds" not in source
    assert "result.congestion" not in source
    assert "traffic_review_approved = True" not in source
    assert "tpda_input_from_review" not in source
    assert 'st.switch_page("pages/traffic_review.py")' in source


def test_session_helper_has_no_streamlit_opencv_yolo_or_global_batch_state():
    source = inspect.getsource(congestion_session).lower()
    for forbidden in (
        "streamlit",
        "cv2",
        "yolo",
        "bytetrack",
        "tpda_input",
        "traffic_review",
    ):
        assert forbidden not in source
