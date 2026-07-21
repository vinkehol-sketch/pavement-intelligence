from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pavement_intelligence.demo import (
    DEMO_DATA_ORIGIN,
    DEMO_NOTICE,
    DemoSessionConflict,
    build_demo_case,
    build_demo_traffic_events,
    load_demo_session,
    reset_demo_session,
)


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "src/pavement_intelligence/ui/app.py"


def test_demo_case_runs_existing_workflows_end_to_end() -> None:
    case = build_demo_case()
    state = case.session_payload

    assert case.data_origin == DEMO_DATA_ORIGIN
    assert case.is_demo is True
    assert case.notice == DEMO_NOTICE
    assert state["tpda_phase1_result"].methodological_status == "VALIDO_PARA_DEMOSTRACION"
    assert state["weighing_phase2_result"].methodological_status == "VALIDO_PARA_DEMOSTRACION"
    assert state["esal_phase3_result"].methodological_status == "VALIDO_PARA_DEMOSTRACION"
    assert state["esal_projection_result"].methodological_status == "VALIDO_PARA_DEMOSTRACION"
    assert state["geotechnical_phase4a_result"].is_demonstrative is True
    assert state["geotechnical_phase4b_result"].is_demonstrative is True
    assert state["aashto93_phase5a_result"].is_demonstrative is True
    assert state["aashto93_phase5b_result"].is_demonstrative is True
    assert state["integrated_dossier"].overall_state == "COMPLETO_DEMOSTRATIVO"
    assert not state["integrated_dossier"].blockers


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
    reset_demo_session(session)
    assert session == {"unrelated_preference": "keep"}


def test_streamlit_demo_controls_load_and_reset_without_exceptions() -> None:
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not app.exception
    next(item for item in app.button if item.label == "Cargar caso demostrativo").click().run(
        timeout=60
    )
    assert not app.exception
    assert app.session_state["demo_mode_active"] is True
    assert any(DEMO_NOTICE in item.value for item in app.error)
    next(item for item in app.button if item.label == "Reiniciar demostración").click().run(
        timeout=60
    )
    assert not app.exception
    assert "demo_mode_active" not in app.session_state
