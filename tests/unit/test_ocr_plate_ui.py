from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from pavement_intelligence.ui.utils.uploaded_video import store_uploaded_video
from pavement_intelligence.vision.analysis.ocr_models import PlateAnalysisState
from pavement_intelligence.vision.plates.base import PlateResult


ROOT = Path(__file__).resolve().parents[2]
OCR_PAGE = ROOT / "src/pavement_intelligence/ui/pages/ocr_plate_review.py"
APP_ENTRYPOINT = ROOT / "src/pavement_intelligence/ui/app.py"
DEMO_VIDEO = ROOT / "data/samples/ui/assets/traffic_monitoring_demo.mp4"


class FakeReader:
    def __init__(self, readings: list[PlateResult | None] | None = None) -> None:
        self.readings = list(readings or [])
        self.calls = 0

    def detect_and_read(self, _frame, _bbox):
        self.calls += 1
        return self.readings.pop(0) if self.readings else None


def plate(text="ABC-123", confidence=0.93):
    return PlateResult(
        text,
        None,
        confidence,
        (20.0, 30.0, 80.0, 55.0),
        is_anonymized=False,
        polygon=((20.0, 30.0), (80.0, 30.0), (80.0, 55.0), (20.0, 55.0)),
    )


def real_app(*, reader: FakeReader | None = None):
    app = AppTest.from_file(str(OCR_PAGE), default_timeout=30).run()
    app.session_state["plate_session_reader_override"] = reader or FakeReader()
    next(
        item
        for item in app.segmented_control
        if item.label == "Modo de lecturas de placas"
    ).set_value("Análisis OCR real").run()
    assert not app.exception
    return app


def button(app, label: str):
    return next(item for item in app.button if item.label == label)


def state_metric(app) -> str:
    return next(item for item in app.metric if item.label == "Estado").value


def start_and_process(app):
    button(app, "Iniciar").click().run()
    assert not app.exception
    button(app, "Procesar siguiente fotograma").click().run()
    assert not app.exception
    return app


def test_synthetic_mode_remains_default_and_separate():
    app = AppTest.from_file(str(OCR_PAGE), default_timeout=30).run()
    assert not app.exception
    mode = next(
        item
        for item in app.segmented_control
        if item.label == "Modo de lecturas de placas"
    )
    assert mode.value == "Demostración sintética"
    assert "Mostrar placa" in {item.label for item in app.button}
    assert "Iniciar" not in {item.label for item in app.button}
    assert all(item.data_origin == "synthetic_demo" for item in app.session_state["ocr_readings_raw"])


def test_real_mode_has_independent_sources_controls_and_warning():
    app = real_app()
    labels = {item.label for item in app.button}
    assert {
        "Iniciar",
        "Procesar siguiente fotograma",
        "Pausar",
        "Continuar",
        "Finalizar",
        "Reiniciar",
    } <= labels
    source = next(item for item in app.segmented_control if item.label == "Fuente OCR")
    assert set(source.options) == {"Video local", "Cargar video", "Cámara"}
    assert any(
        "auxiliares y requieren revisión humana" in item.value for item in app.info
    )
    assert any("ROI" in item.value and "no se utiliza" in item.value for item in app.caption)
    assert any(
        "Backend PaddleOCR: disponible" in item.value for item in app.caption
    )
    assert next(
        item for item in app.slider if item.label == "Evaluar OCR cada N frames"
    ).value == 15


def test_real_mode_does_not_start_automatically():
    app = real_app(reader=FakeReader([plate()]))
    assert app.session_state["plate_session_controller"] is None
    assert app.session_state["plate_session_batch_readings"] == ()


def test_real_start_and_first_frame_use_injected_reader_without_yolo():
    reader = FakeReader([plate()])
    app = start_and_process(real_app(reader=reader))
    controller = app.session_state["plate_session_controller"]
    assert controller.state is PlateAnalysisState.RUNNING
    assert reader.calls == 1
    assert len(app.session_state["plate_session_batch_readings"]) == 1
    assert app.session_state["plate_session_source_id"].startswith("local-video:")
    assert app.session_state["plate_session_batch_id"].startswith("plate:")
    assert app.session_state["plate_session_annotated_frame"] is not None
    assert app.session_state["plate_session_last_processed_frame"] >= 1
    metric_labels = {item.label for item in app.metric}
    assert {
        "Estado",
        "Fotograma",
        "Progreso",
        "Lecturas encontradas",
        "FPS de procesamiento",
    } <= metric_labels
    assert app.get("progress")


def test_real_plate_is_masked_until_explicit_reveal():
    app = start_and_process(real_app(reader=FakeReader([plate()])))
    display = next(item for item in app.text_input if item.label == "Lectura detectada")
    assert display.value == "***-123"
    button(app, "Mostrar lectura").click().run()
    assert not app.exception
    display = next(item for item in app.text_input if item.label == "Lectura detectada")
    assert display.value == "ABC-123"
    audit = app.session_state["plate_session_reveal_audit"]
    assert [(item.action, item.reading_id) for item in audit] == [
        ("REVEAL", app.session_state["plate_session_batch_readings"][0].reading_id)
    ]


def test_progressive_viewer_masks_detected_region_by_default():
    app = real_app(reader=FakeReader([plate()]))
    button(app, "Iniciar").click().run()
    annotated = app.session_state["plate_session_annotated_frame"]
    assert app.session_state["plate_session_protect_viewer"] is True
    assert tuple(annotated[42, 50]) == (24, 24, 24)


def test_full_plate_view_requires_explicit_privacy_toggle():
    app = real_app(reader=FakeReader([plate()]))
    button(app, "Iniciar").click().run()
    button(app, "Pausar").click().run()
    privacy = next(
        item
        for item in app.toggle
        if item.label == "Enmascarar matrículas en el visor"
    )
    privacy.set_value(False).run()
    assert not app.exception
    assert app.session_state["plate_session_protect_viewer"] is False
    annotated = app.session_state["plate_session_annotated_frame"]
    assert tuple(annotated[42, 50]) != (24, 24, 24)
    assert any("Privacidad desactivada" in item.value for item in app.warning)


def test_manual_correction_is_review_only_and_does_not_change_candidate():
    app = start_and_process(real_app(reader=FakeReader([plate()])))
    candidate = app.session_state["plate_session_batch_readings"][0]
    next(
        item for item in app.text_input if item.label == "Corrección manual"
    ).set_value("xyz-987")
    button(app, "Guardar corrección OCR").click().run()
    assert not app.exception
    review = app.session_state["plate_session_reviews"][candidate.reading_id]
    assert review.corrected_text == "XYZ-987"
    assert candidate.normalized_text == "ABC123"
    assert "tpda_input_from_review" not in app.session_state


def test_manual_rejection_does_not_approve_or_invent_replacement():
    app = start_and_process(real_app(reader=FakeReader([plate()])))
    candidate = app.session_state["plate_session_batch_readings"][0]
    button(app, "Rechazar lectura OCR").click().run()
    review = app.session_state["plate_session_reviews"][candidate.reading_id]
    assert review.status.value == "REJECTED"
    assert review.corrected_text is None
    assert "traffic_review_approved" not in app.session_state


def test_pause_continue_reset_and_finish_are_independent():
    app = start_and_process(real_app(reader=FakeReader([plate()])))
    button(app, "Pausar").click().run()
    assert app.session_state["plate_session_controller"].state is PlateAnalysisState.PAUSED
    assert state_metric(app) == "PAUSED"
    frame = app.session_state["plate_session_last_processed_frame"]
    button(app, "Continuar").click().run()
    assert app.session_state["plate_session_controller"].state is PlateAnalysisState.RUNNING
    assert state_metric(app) == "RUNNING"
    assert app.session_state["plate_session_last_processed_frame"] > frame
    button(app, "Finalizar").click().run()
    assert app.session_state["plate_session_controller"].state is PlateAnalysisState.FINISHED
    assert state_metric(app) == "COMPLETED"
    assert len(app.session_state["plate_session_batch_readings"]) == 1
    button(app, "Reiniciar").click().run()
    assert app.session_state["plate_session_controller"] is None
    assert app.session_state["plate_session_batch_readings"] == ()
    assert state_metric(app) == "IDLE"


def test_changing_source_cleans_controller_batch_and_reveal_audit():
    app = start_and_process(real_app(reader=FakeReader([plate()])))
    button(app, "Mostrar lectura").click().run()
    controller = app.session_state["plate_session_controller"]
    next(item for item in app.segmented_control if item.label == "Fuente OCR").set_value("Cámara").run()
    assert not app.exception
    assert controller.source.is_open() is False
    assert app.session_state["plate_session_controller"] is None
    assert app.session_state["plate_session_batch_readings"] == ()
    assert app.session_state["plate_session_reveal_audit"] == ()


def test_uploaded_video_is_temporary_and_switching_to_local_removes_it():
    app = real_app()
    next(item for item in app.segmented_control if item.label == "Fuente OCR").set_value("Cargar video").run()
    app.file_uploader[0].set_value(
        ("authorized.mp4", DEMO_VIDEO.read_bytes(), "video/mp4")
    ).run()
    assert not app.exception
    handle = app.session_state["plate_session_uploaded_video"]
    path = handle.temporary_path
    assert path.is_file()
    assert ROOT not in path.parents
    next(item for item in app.segmented_control if item.label == "Fuente OCR").set_value("Video local").run()
    assert not path.exists()
    assert app.session_state["plate_session_uploaded_video"] is None


def test_corrupt_upload_is_controlled_and_cannot_start():
    app = real_app()
    next(item for item in app.segmented_control if item.label == "Fuente OCR").set_value("Cargar video").run()
    app.file_uploader[0].set_value(
        ("corrupt.mp4", b"not-video", "video/mp4")
    ).run()
    assert not app.exception
    assert app.session_state["plate_session_controller"] is None
    assert app.session_state["plate_session_uploaded_video"] is None
    assert button(app, "Iniciar").disabled
    assert state_metric(app) == "ERROR"
    assert any("OpenCV no pudo abrir" in item.value for item in app.error)


def test_finishing_uploaded_video_closes_and_removes_temporary_file():
    app = real_app(reader=FakeReader([plate()]))
    next(item for item in app.segmented_control if item.label == "Fuente OCR").set_value("Cargar video").run()
    app.file_uploader[0].set_value(
        ("authorized.mp4", DEMO_VIDEO.read_bytes(), "video/mp4")
    ).run()
    handle = app.session_state["plate_session_uploaded_video"]
    path = handle.temporary_path
    start_and_process(app)
    button(app, "Finalizar").click().run()
    assert not app.exception
    assert not path.exists()
    assert app.session_state["plate_session_uploaded_video"] is None
    assert app.session_state["plate_session_upload_status"] == "finalized"


def test_missing_paddleocr_is_a_controlled_optional_error():
    app = AppTest.from_file(str(OCR_PAGE), default_timeout=30).run()
    next(item for item in app.segmented_control if item.label == "Modo de lecturas de placas").set_value("Análisis OCR real").run()
    if any("Backend PaddleOCR: no instalado" in item.value for item in app.caption):
        button(app, "Iniciar").click().run()
        assert not app.exception
        assert any("PaddleOCR no está instalado" in item.value for item in app.error)


def test_navigation_away_closes_plate_controller_and_upload(tmp_path):
    class Upload:
        name = "plates.mp4"
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
        Upload(), temporary_parent=tmp_path, duration_reader=lambda _path: 2.0
    )
    path = handle.temporary_path
    controller = Controller()
    app = AppTest.from_file(str(APP_ENTRYPOINT), default_timeout=30)
    app.session_state["plate_session_controller"] = controller
    app.session_state["plate_session_uploaded_video"] = handle
    app.run()
    assert not app.exception
    assert controller.closed
    assert not path.exists()
    assert app.session_state["plate_session_controller"] is None
    assert app.session_state["plate_session_uploaded_video"] is None


def test_real_mode_never_mutates_preexisting_traffic_keys():
    sentinel = object()
    app = AppTest.from_file(str(OCR_PAGE), default_timeout=30)
    app.session_state["traffic_analysis_controller"] = sentinel
    app.session_state["traffic_review_approved"] = False
    app.session_state["tpda_input_from_review"] = sentinel
    app.run()
    app.session_state["plate_session_reader_override"] = FakeReader([plate()])
    next(item for item in app.segmented_control if item.label == "Modo de lecturas de placas").set_value("Análisis OCR real").run()
    start_and_process(app)
    assert app.session_state["traffic_analysis_controller"] is sentinel
    assert app.session_state["traffic_review_approved"] is False
    assert app.session_state["tpda_input_from_review"] is sentinel
