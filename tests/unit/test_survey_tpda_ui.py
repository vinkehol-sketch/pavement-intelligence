from pathlib import Path

from streamlit.testing.v1 import AppTest

from pavement_intelligence.traffic.tpda_workflow import MethodologicalStatus
from pavement_intelligence.demo import build_demo_case


PAGE = (
    Path(__file__).resolve().parents[2]
    / "src/pavement_intelligence/ui/pages/survey_tpda.py"
)


def reviewed_app(counts: dict[str, int]) -> AppTest:
    app = AppTest.from_file(str(PAGE), default_timeout=20)
    app.session_state["tpda_input_from_review"] = {
        "counts_by_category": counts,
        "source": "video_validacion.mp4",
        "data_origin": "OBSERVADO_POR_VIDEO",
        "reviewer": "Revisor inicial",
        "is_synthetic": False,
        "warnings": [],
        "batch_hash": "batch-ui-test",
    }
    return app.run()


def widget(elements, label: str):
    return next(element for element in elements if element.label == label)


def calculate(app: AppTest) -> AppTest:
    widget(app.text_input, "Responsable del cálculo").set_value("Auditor UI")
    widget(app.button, "Calcular y evaluar Fase 1").click()
    return app.run()


def test_ui_scenario_1_partial_survey_uses_one_factor() -> None:
    app = reviewed_app({"AUTO": 10})
    widget(app.number_input, "Duración declarada del aforo (horas)").set_value(2.0)
    app = app.run()
    app = calculate(app)
    result = app.session_state["tpda_phase1_result"]
    assert result.temporal_expansion_factor == 12
    assert result.tpda_base_total == 120


def test_ui_scenario_2_unverifiable_24h_requires_acknowledgement() -> None:
    app = reviewed_app({"AUTO": 10})
    app = calculate(app)
    result = app.session_state["tpda_phase1_result"]
    assert result.methodological_status == MethodologicalStatus.BLOCKED_BY_EXPANSION.value
    assert any("no puede verificarse" in warning for warning in result.warnings)


def test_ui_scenario_3_truck_stays_unconfirmed_and_blocks() -> None:
    app = reviewed_app({"AUTO": 10, "CAMION": 1})
    widget(
        app.checkbox,
        "Confirmo manualmente que la duración declarada corresponde a la cobertura del aforo",
    ).check()
    app = app.run()
    app = calculate(app)
    result = app.session_state["tpda_phase1_result"]
    assert result.pending_categories["CAMION_NO_CONFIRMADO"] == 1
    assert result.corrected_counts.get("C2", 0) == 0
    assert result.methodological_status == MethodologicalStatus.BLOCKED_BY_CLASSIFICATION.value


def test_ui_scenario_4_reclassification_can_become_fit_after_recalculation() -> None:
    app = reviewed_app({"AUTO": 10, "CAMION": 1})
    widget(app.text_input, "Motivo de reclasificación").set_value("Inspección manual: tres ejes")
    widget(app.text_input, "Revisor de clasificación").set_value("Auditor camiones")
    widget(app.button, "Registrar reclasificación").click()
    app = app.run()
    widget(
        app.checkbox,
        "Confirmo manualmente que la duración declarada corresponde a la cobertura del aforo",
    ).check()
    app = app.run()
    app = calculate(app)
    result = app.session_state["tpda_phase1_result"]
    assert result.pending_categories["CAMION_NO_CONFIRMADO"] == 0
    assert len(result.reclassifications) == 1
    assert result.methodologically_fit_for_next_phase


def test_ui_scenario_5_duration_change_marks_result_stale() -> None:
    app = reviewed_app({"AUTO": 10})
    widget(
        app.checkbox,
        "Confirmo manualmente que la duración declarada corresponde a la cobertura del aforo",
    ).check()
    app = app.run()
    app = calculate(app)
    original = app.session_state["tpda_phase1_result"]
    assert original.methodologically_fit_for_next_phase

    widget(app.number_input, "Duración declarada del aforo (horas)").set_value(23.0)
    app = app.run()
    assert app.session_state["tpda_phase1_result"].calculation_id == original.calculation_id
    assert any("DESACTUALIZADO" in element.value for element in app.error)


def test_demo_ui_preserves_two_hour_contract_and_shows_formula_and_transfer_warning() -> None:
    case = build_demo_case()
    app = AppTest.from_file(str(PAGE), default_timeout=60)
    for key, value in case.session_payload.items():
        app.session_state[key] = value

    app = app.run()

    assert not app.exception
    duration = widget(app.number_input, "Duración declarada del aforo (horas)")
    assert duration.value == 2
    assert not any("DESACTUALIZADO" in item.value for item in app.error)
    assert any("106 × 12 × 1 = 1.272 veh/día" in item.value for item in app.code)
    assert any(
        "methodologically_fit_for_next_phase=false" in item.value
        for item in app.warning
    )
