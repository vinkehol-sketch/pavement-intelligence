"""Carga y limpieza atómicas del caso demo en cualquier mapping de sesión."""
from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from .case import build_demo_case


class DemoSessionConflict(RuntimeError):
    """Evita mezclar datos sintéticos con una sesión operacional existente."""


DEMO_MANAGED_SESSION_KEYS = frozenset(
    {
        "demo_mode_active",
        "demo_case_id",
        "demo_seed",
        "demo_notice",
        "data_origin",
        "is_demo",
        "demo_loaded_at",
        "demo_review_history",
        "demo_module_provenance",
        "demo_case_summary",
        "vision_events_raw",
        "vision_events_reviewed",
        "vision_batch_metadata",
        "traffic_counts_corrected",
        "traffic_review_approved",
        "is_synthetic_review",
        "traffic_review_source_fingerprint",
        "tpda_input_from_review",
        "tpda_phase1_input",
        "tpda_phase1_result",
        "tpda_result",
        "aforos_registrados",
        "processing_done",
        "events",
        "corrected_records",
        "weighing_input_from_tpda",
        "weighing_records_current",
        "weighing_phase2_input",
        "weighing_phase2_result",
        "esal_input_from_weighing",
        "esal_phase3_input",
        "esal_phase3_result",
        "esal_projection_transfer",
        "esal_projection_input",
        "esal_projection_result",
        "esal_calculado",
        "geotechnical_cbr_records",
        "geotechnical_phase4a_input",
        "geotechnical_phase4a_result",
        "geotechnical_phase4b_input",
        "geotechnical_phase4b_result",
        "geotechnical_future_transfer",
        "muestras_suelo",
        "aashto5a_esal_transfer",
        "aashto5a_mr_transfer",
        "aashto5a_contract_date",
        "aashto93_phase5a_input",
        "aashto93_phase5a_result",
        "aashto5b_transfer",
        "aashto5b_contract_date",
        "aashto93_phase5b_input",
        "aashto93_phase5b_result",
        "diseno_calculado",
        "ocr_readings_raw",
        "ocr_review_records",
        "ocr_selected_reading_id",
        "ocr_visible_reading_id",
        "ocr_reveal_audit",
        "ocr_filters",
        "integrated_report_request",
        "integrated_dossier",
        "integrated_dossier_pdf",
        "integrated_dossier_history",
    }
)
REAL_SESSION_GUARD_KEYS = frozenset(
    {
        "traffic_analysis_controller",
        "traffic_analysis_batch_events",
        "plate_session_controller",
        "plate_session_batch_readings",
        "processing_done",
        "events",
        "corrected_records",
        "pesaje_df",
        "esal_result",
    }
)
DEMO_WIDGET_PREFIXES = (
    "demo_",
    "ocr_",
    "tpda_",
    "weighing_",
    "esal3b_",
    "geotech_",
    "aashto5",
    "5b_",
)


def _has_value(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (str, bytes, tuple, list, dict, set, frozenset)):
        return bool(value)
    if isinstance(value, (int, float)):
        return value != 0
    return True


def load_demo_session(session: MutableMapping[str, Any]) -> dict[str, Any]:
    """Carga todo o no carga nada; una sesión real no se sobrescribe."""
    if not session.get("demo_mode_active"):
        conflicts = sorted(
            key
            for key in DEMO_MANAGED_SESSION_KEYS | REAL_SESSION_GUARD_KEYS
            if key in session and _has_value(session[key])
        )
        standalone_ocr = all(
            getattr(item, "data_origin", None) in {"synthetic_demo", "SYNTHETIC_UI_DEMO"}
            for item in session.get("ocr_readings_raw", ())
        )
        if standalone_ocr:
            conflicts = [key for key in conflicts if not key.startswith("ocr_")]
        if conflicts:
            raise DemoSessionConflict(
                "La sesión contiene datos operacionales. Reiníciela o abra una sesión limpia "
                "antes de cargar la demostración. Conflictos: " + ", ".join(conflicts[:6])
            )
    case = build_demo_case()
    session.update(case.session_payload)
    return dict(case.summary)


def reset_demo_session(session: MutableMapping[str, Any]) -> None:
    """Elimina por completo el estado administrado por demo, sin tocar otros widgets."""
    was_active = bool(session.get("demo_mode_active"))
    for key in DEMO_MANAGED_SESSION_KEYS:
        session.pop(key, None)
    if was_active:
        for key in tuple(session):
            if key.startswith(DEMO_WIDGET_PREFIXES):
                session.pop(key, None)
