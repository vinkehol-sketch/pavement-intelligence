from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pavement_intelligence.demo import (
    DEMO_DATA_ORIGIN,
    DEMO_NOTICE,
    DEMO_PROJECT_METADATA,
    DEMO_REQUIRED_FIELDS,
    DEMO_RESPONSIBLE_PARTIES,
    DemoSessionConflict,
    build_demo_case,
    build_demo_traffic_events,
    load_demo_session,
    reset_demo_session,
)
from pavement_intelligence.weighing.workflow import build_weighing_input_from_tpda


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "src/pavement_intelligence/ui/app.py"
DEMO_PAGES = (
    "home.py",
    "traffic_monitoring.py",
    "ocr_plate_review.py",
    "video_analysis.py",
    "traffic_review.py",
    "survey_tpda.py",
    "weighing.py",
    "esal_calculator.py",
    "soil_study.py",
    "aashto_sn.py",
    "layer_design.py",
    "pavement_design.py",
    "reports.py",
)
PRIMARY_ACTIONS = {
    "traffic_review.py": "🔒 Aprobar Aforo Revisado",
    "survey_tpda.py": "Calcular y evaluar Fase 1",
    "weighing.py": "Validar y calcular resultado de Pesaje",
    "esal_calculator.py": "Calcular y validar ESAL",
    "soil_study.py": "Calcular módulo resiliente estimado",
    "aashto_sn.py": "Calcular SN requerido",
    "layer_design.py": "Evaluar propuesta por capas",
    "pavement_design.py": "🛣️ Ejecutar Diseño AASHTO 93",
    "reports.py": "Generar expediente demostrativo",
}


def test_demo_case_runs_existing_workflows_end_to_end() -> None:
    case = build_demo_case()
    state = case.session_payload

    assert case.data_origin == DEMO_DATA_ORIGIN
    assert case.is_demo is True
    assert case.notice == DEMO_NOTICE
    assert state["tpda_phase1_result"].methodological_status == "VALIDO_PARA_DEMOSTRACION"
    assert state["tpda_phase1_result"].methodologically_fit_for_next_phase is False
    assert state["weighing_phase2_result"].methodological_status == "VALIDO_PARA_DEMOSTRACION"
    assert state["esal_phase3_result"].methodological_status == "VALIDO_PARA_DEMOSTRACION"
    assert state["esal_projection_result"].methodological_status == "VALIDO_PARA_DEMOSTRACION"
    assert state["geotechnical_phase4a_result"].is_demonstrative is True
    assert state["geotechnical_phase4b_result"].is_demonstrative is True
    assert state["aashto93_phase5a_result"].is_demonstrative is True
    assert state["aashto93_phase5b_result"].is_demonstrative is True
    assert state["integrated_dossier"].overall_state == "COMPLETO_DEMOSTRATIVO"
    assert not state["integrated_dossier"].blockers


def test_demo_tpda_contract_uses_two_hour_official_source() -> None:
    case = build_demo_case()
    state = case.session_payload
    contract = state["demo_tpda_authoritative_input"]
    result = state["tpda_phase1_result"]

    assert sum(contract.corrected_counts.values()) == 106
    assert contract.temporal_coverage.declared_hours == 2
    assert contract.temporal_coverage.verified_hours == 2
    assert result.temporal_expansion_factor == 12
    assert result.seasonal_factor == 1
    assert result.tpda_base_total == 1272
    assert result.projected_traffic_total == pytest.approx(2787.1085, rel=1e-6)
    assert case.summary["tpda_formula"] == "106 × 12 × 1 = 1.272 veh/día"
    assert "106 × 12 × 1 = 1.272 veh/día" in (
        state["integrated_report_request"].administrative.observations
    )


def test_demo_tpda_is_blocked_officially_but_allowed_explicitly_in_demo() -> None:
    result = build_demo_case().session_payload["tpda_phase1_result"]

    with pytest.raises(ValueError, match="no está habilitado"):
        build_weighing_input_from_tpda(result)

    transfer = build_weighing_input_from_tpda(result, allow_demonstration=True)
    assert transfer.demonstration_mode is True
    assert transfer.is_synthetic is True


def test_demo_case_is_reproducible_and_has_traceable_review() -> None:
    first = build_demo_traffic_events()
    second = build_demo_traffic_events()

    assert first == second
    assert first is not second
    assert len(first) == 120
    assert {item["direction"] for item in first} == {-1, 1}
    assert all(item["data_origin"] == DEMO_DATA_ORIGIN for item in first)
    case = build_demo_case()
    assert case.summary["initially_pending_events"] == 14
    assert case.summary["approved_crossings"] == 106
    assert len(case.session_payload["demo_review_history"]) == 14


def test_ocr_is_fictional_private_and_separate_from_official_counts() -> None:
    case = build_demo_case()
    readings = case.session_payload["ocr_readings_raw"]
    counts_before = dict(case.session_payload["traffic_counts_corrected"])

    assert {item.original_text for item in readings} == {"DEMO-01", "FICT-?2", "TEST-X3", ""}
    assert all(item.data_origin == DEMO_DATA_ORIGIN for item in readings)
    assert all(item.masked_text.startswith("***-") for item in readings)
    assert case.session_payload["ocr_visible_reading_id"] is None
    assert case.session_payload["traffic_counts_corrected"] == counts_before


def test_demo_loader_refuses_real_session_and_reset_is_complete() -> None:
    with pytest.raises(DemoSessionConflict):
        load_demo_session({"events": [{"event_id": "real"}]})

    session: dict[str, object] = {"unrelated_preference": "keep"}
    summary = load_demo_session(session)
    assert summary["data_origin"] == DEMO_DATA_ORIGIN
    assert session["demo_mode_active"] is True
    session["ocr_filter_search"] = "DEMO"
    widget_keys = tuple(session["demo_widget_keys"])
    reset_demo_session(session)
    assert session == {"unrelated_preference": "keep"}
    assert all(key not in session for key in widget_keys)


def test_demo_required_fields_are_complete_fictitious_and_centralized() -> None:
    case = build_demo_case()
    state = case.session_payload

    assert DEMO_PROJECT_METADATA.project_code == case.case_id
    assert DEMO_PROJECT_METADATA.data_origin == DEMO_DATA_ORIGIN
    assert DEMO_PROJECT_METADATA.is_demo is True
    assert DEMO_RESPONSIBLE_PARTIES.reviewer == "Auditor Vial"
    assert state["demo_project_metadata"]["project_name"]
    assert state["demo_report_metadata"]["disclaimer"].startswith("DATOS SINTÉTICOS")
    assert all(field.demo_value not in (None, "") for field in DEMO_REQUIRED_FIELDS)
    widget_fields = [field for field in DEMO_REQUIRED_FIELDS if field.state_key in state]
    assert all(state[field.state_key] not in (None, "") for field in widget_fields)
    tpda_contract = state["demo_tpda_authoritative_input"]
    assert tpda_contract.temporal_coverage.declared_hours == 2
    assert tpda_contract.reviewer == DEMO_RESPONSIBLE_PARTIES.reviewer
    assert all("demo" in value.lower() or value == "Equipo Pavement Intelligence" for value in (
        DEMO_RESPONSIBLE_PARTIES.study_lead,
        DEMO_RESPONSIBLE_PARTIES.traffic_operator,
        DEMO_RESPONSIBLE_PARTIES.pavement_designer,
        DEMO_RESPONSIBLE_PARTIES.report_prepared_by,
        DEMO_RESPONSIBLE_PARTIES.report_approved_by,
    ))


@pytest.mark.parametrize("page_name", DEMO_PAGES)
def test_all_thirteen_demo_pages_load_prefilled_without_exceptions(page_name: str) -> None:
    case = build_demo_case()
    page = ROOT / "src/pavement_intelligence/ui/pages" / page_name
    app = AppTest.from_file(str(page), default_timeout=60)
    for key, value in case.session_payload.items():
        app.session_state[key] = value

    app = app.run()

    assert not app.exception
    assert app.session_state["demo_mode_active"] is True
    action_label = PRIMARY_ACTIONS.get(page_name)
    if action_label:
        action = next(item for item in app.button if item.label == action_label)
        assert action.disabled is False


def test_real_mode_does_not_receive_demo_administrative_defaults() -> None:
    page = ROOT / "src/pavement_intelligence/ui/pages/reports.py"
    app = AppTest.from_file(str(page), default_timeout=30).run()

    assert not app.exception
    assert "demo_project_metadata" not in app.session_state
    assert next(item for item in app.text_input if item.label == "Nombre del proyecto").value == ""


def test_streamlit_demo_controls_load_and_reset_without_exceptions() -> None:
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not app.exception
    next(item for item in app.button if item.label == "Cargar caso demostrativo").click().run(
        timeout=60
    )
    assert not app.exception
    assert app.session_state["demo_mode_active"] is True
    assert not any(DEMO_NOTICE in item.value for item in app.error)
    assert any("Modo demo activo" in item.value for item in app.caption)
    next(item for item in app.button if item.label == "Reiniciar demostración").click().run(
        timeout=60
    )
    assert not app.exception
    assert "demo_mode_active" not in app.session_state
