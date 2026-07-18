from pathlib import Path

from streamlit.testing.v1 import AppTest

from pavement_intelligence.geotechnics.cbr_workflow import CBRWorkflowInput, DesignCBRMode
from pavement_intelligence.ui.pages.soil_study import _demo_records


PAGE = Path(__file__).resolve().parents[2] / "src/pavement_intelligence/ui/pages/soil_study.py"


def widget(elements, label):
    return next(item for item in elements if item.label == label)


def test_page_renders_without_data_and_writes_nothing_to_design():
    app = AppTest.from_file(str(PAGE), default_timeout=20).run()
    assert not app.exception
    assert any("Sin registros CBR" in item.value for item in app.info)
    for forbidden in ("cbr_diseno", "mr_psi", "pavement_design_result", "aashto_result"):
        assert forbidden not in app.session_state


def test_page_calculates_demo_with_warning_and_exclusions():
    app = AppTest.from_file(str(PAGE), default_timeout=20)
    app.session_state["geotechnical_cbr_records"] = _demo_records()
    app.run()
    widget(app.selectbox, "Criterio de CBR de diseño").select(DesignCBRMode.CONSERVATIVE_MINIMUM)
    widget(app.checkbox, "Reconozco expresamente los datos sintéticos como demostrativos").check()
    widget(app.text_input, "Responsable de Fase 4A").set_value("Auditor UI")
    app.run()
    widget(app.button, "Calcular módulo resiliente estimado").click()
    app.run()
    assert not app.exception
    result = app.session_state["geotechnical_phase4a_result"]
    assert result.is_demonstrative and result.design_cbr_percent == 4
    assert any("correlación empírica" in item.value for item in app.warning)
    assert app.download_button


def test_page_marks_previous_result_stale_when_input_changes():
    records = _demo_records()
    data = CBRWorkflowInput(
        study_id="DEMO-4A", project_segment="Tramo demostrativo", records=records,
        design_mode=DesignCBRMode.CONSERVATIVE_MINIMUM.value,
        correlation_id="LINEAL_1500_PSI", reviewer="Auditor UI", synthetic_acknowledged=True,
    )
    from pavement_intelligence.geotechnics.cbr_workflow import calculate_cbr_workflow
    app = AppTest.from_file(str(PAGE), default_timeout=20)
    app.session_state["geotechnical_cbr_records"] = records
    app.session_state["geotechnical_phase4a_input"] = data
    app.session_state["geotechnical_phase4a_result"] = calculate_cbr_workflow(data)
    app.run()
    assert any("DESACTUALIZADO" in item.value for item in app.error)
