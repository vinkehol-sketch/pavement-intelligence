from dataclasses import replace
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pavement_intelligence.traffic.tpda_workflow import (
    ExpansionMethod, FactorTrace, ProjectionMethod, TPDAWorkflowInput,
    TemporalCoverage, calculate_tpda_workflow,
)
from pavement_intelligence.weighing.workflow import (
    WeighingCondition, WeighingSourceType, build_manual_observation,
    WeighingWorkflowInput, build_weighing_input_from_tpda,
    calculate_weighing_workflow,
)

ROOT = Path(__file__).resolve().parents[2]
SURVEY = ROOT / "src/pavement_intelligence/ui/pages/survey_tpda.py"
WEIGHING = ROOT / "src/pavement_intelligence/ui/pages/weighing.py"
ESAL = ROOT / "src/pavement_intelligence/ui/pages/esal_calculator.py"


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def valid_tpda():
    return calculate_tpda_workflow(TPDAWorkflowInput(
        batch_id="batch-ui-weight", source="video.mp4", data_origin="VIDEO_REVISADO",
        automatic_counts={"AUTO": 100, "C2": 10},
        corrected_counts={"AUTO": 100, "C2": 10},
        pending_categories={"CAMION_NO_CONFIRMADO": 0},
        temporal_coverage=TemporalCoverage(24, 24, "TIMESTAMPS", False),
        expansion_method=ExpansionMethod.NONE_24H, temporal_factor=None,
        seasonal_factor=FactorTrace("f_e", "Identidad", 1, "Sin corrección", "Identidad", "24h"),
        projection_method=ProjectionMethod.EXPONENTIAL, growth_rate_percent=4,
        design_period_years=20, base_year=2026, directional_factor=0.5,
        lane_distribution_factor=1, reviewer="Auditor",
    ))


def valid_record():
    return build_manual_observation(
        category="C2", gross_weight=150,
        axle_groups=(("simple_single", 50), ("simple_dual", 100)), unit="kN",
        source_type=WeighingSourceType.STATIC_SCALE, source_reference="balanza-ui",
        condition=WeighingCondition.MEASURED, reviewer="Auditor",
        timestamp="2026-07-17T20:00:00+00:00",
    )


def test_survey_transfer_is_manual_not_automatic():
    app = AppTest.from_file(str(SURVEY), default_timeout=20)
    app.session_state["tpda_input_from_review"] = {
        "counts_by_category": {"AUTO": 10, "C2": 1}, "source": "video.mp4",
        "data_origin": "VIDEO_REVISADO", "reviewer": "Auditor",
        "is_synthetic": False, "warnings": [], "batch_hash": "batch-transfer",
    }
    app.run()
    widget(app.checkbox, "Confirmo manualmente que la duración declarada corresponde a la cobertura del aforo").check()
    app.run()
    widget(app.text_input, "Responsable del cálculo").set_value("Auditor")
    widget(app.button, "Calcular y evaluar Fase 1").click()
    app.run()
    assert "weighing_input_from_tpda" not in app.session_state
    widget(app.checkbox, "Confirmo que revisé el estado, categorías, periodo, factores y advertencias").check()
    app.run()
    widget(app.button, "Usar TPDA validado en Pesaje").click()
    app.run()
    assert app.session_state["weighing_input_from_tpda"].source_tpda_result_id


def test_weighing_page_without_transfer_stops_cleanly():
    app = AppTest.from_file(str(WEIGHING), default_timeout=20).run()
    assert not app.exception
    assert any("transferencia manual" in item.value for item in app.error)


def test_weighing_page_stores_only_phase2_result():
    tpda = valid_tpda()
    app = AppTest.from_file(str(WEIGHING), default_timeout=20)
    app.session_state["tpda_phase1_result"] = tpda
    app.session_state["weighing_input_from_tpda"] = build_weighing_input_from_tpda(tpda)
    app.session_state["weighing_records_current"] = (valid_record(),)
    app.run()
    widget(app.text_input, "Revisor de Pesaje").set_value("Auditor")
    app.run()
    widget(app.button, "Validar y calcular resultado de Pesaje").click()
    app.run()
    assert not app.exception
    assert "weighing_phase2_result" in app.session_state
    assert "esal_result" not in app.session_state
    assert "pesaje_df" not in app.session_state


def test_weighing_page_blocks_mismatched_tpda_signature():
    original = valid_tpda()
    changed = replace(original, input_fingerprint="changed-fingerprint")
    app = AppTest.from_file(str(WEIGHING), default_timeout=20)
    app.session_state["tpda_phase1_result"] = changed
    app.session_state["weighing_input_from_tpda"] = build_weighing_input_from_tpda(original)
    app.session_state["weighing_records_current"] = (valid_record(),)
    app.run()
    assert any("firma TPDA" in item.value for item in app.error)
    assert widget(app.button, "Validar y calcular resultado de Pesaje").disabled


def test_weighing_ui_consumes_no_legacy_traffic_keys():
    source = WEIGHING.read_text(encoding="utf-8")
    assert 'st.session_state.get("tpda_phase1_result")' in source
    for forbidden in ("traffic_counts_corrected", 'st.session_state.get("tpda_result")',
                      "corrected_records", 'st.session_state.get("events")'):
        assert forbidden not in source


def valid_weighing_result():
    tpda = valid_tpda()
    contract = build_weighing_input_from_tpda(tpda)
    return tpda, calculate_weighing_workflow(WeighingWorkflowInput(
        tpda_transfer=contract, observations=(valid_record(),),
        source_type=WeighingSourceType.STATIC_SCALE,
        source_reference="balanza-ui", source_date="2026-07-17",
        reviewer="Auditor", validation_state="REVISADO",
    ))


def test_weighing_to_esal_transfer_requires_confirmation():
    tpda, result = valid_weighing_result()
    app = AppTest.from_file(str(WEIGHING), default_timeout=20)
    app.session_state["tpda_phase1_result"] = tpda
    app.session_state["weighing_input_from_tpda"] = build_weighing_input_from_tpda(tpda)
    app.session_state["weighing_records_current"] = (valid_record(),)
    app.session_state["weighing_phase2_result"] = result
    app.run()
    assert "esal_input_from_weighing" not in app.session_state
    widget(app.checkbox, "Confirmo que revisé cargas, ejes, atípicos, estado y advertencias").check()
    app.run()
    widget(app.button, "Usar pesaje validado en ESAL").click()
    app.run()
    assert not app.exception
    assert app.session_state["esal_input_from_weighing"].source_weighing_result_id == result.result_id


def test_esal_page_navigation_and_formal_storage_only():
    from pavement_intelligence.esal.workflow import build_esal_input_from_weighing

    _, result = valid_weighing_result()
    app = AppTest.from_file(str(ESAL), default_timeout=20)
    app.session_state["weighing_phase2_result"] = result
    app.session_state["esal_input_from_weighing"] = build_esal_input_from_weighing(result)
    app.run()
    assert not app.exception
    widget(app.text_input, "Revisor ESAL").set_value("Auditor ESAL")
    app.run()
    widget(app.button, "Calcular y validar ESAL").click()
    app.run()
    assert not app.exception
    assert app.session_state["esal_phase3_result"].design_readiness == "APTO_PARA_DISENO"
    assert "esal_result" not in app.session_state


def test_esal_page_without_manual_transfer_stops_cleanly():
    app = AppTest.from_file(str(ESAL), default_timeout=20).run()
    assert not app.exception
    assert any("transferencia manual" in item.value for item in app.error)
