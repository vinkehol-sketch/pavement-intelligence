from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
OCR_PAGE = ROOT / "src/pavement_intelligence/ui/pages/ocr_plate_review.py"
MONITORING_PAGE = ROOT / "src/pavement_intelligence/ui/pages/traffic_monitoring.py"


def test_ocr_page_renders_without_exceptions():
    app = AppTest.from_file(str(OCR_PAGE), default_timeout=30).run()
    assert not app.exception
    assert [title.value for title in app.title] == ["Lecturas de placas"]
    labels = {button.label for button in app.button}
    assert {"Volver al monitoreo", "Mostrar placa", "Confirmar sin cambios", "Guardar corrección"} <= labels


def test_ocr_reveal_control_renders_only_selected_plate_and_audits():
    app = AppTest.from_file(str(OCR_PAGE), default_timeout=30).run()
    next(button for button in app.button if button.label == "Mostrar placa").click()
    app.run()
    assert not app.exception
    assert app.session_state["ocr_visible_reading_id"] == "LPR-001"
    assert [(item.reading_id, item.action) for item in app.session_state["ocr_reveal_audit"]] == [("LPR-001", "REVEAL")]
    assert "Ocultar placa" in {button.label for button in app.button}


def test_monitoring_page_keeps_ocr_navigation_action():
    app = AppTest.from_file(str(MONITORING_PAGE), default_timeout=30).run()
    assert not app.exception
    assert "Ver lecturas" in {button.label for button in app.button}
