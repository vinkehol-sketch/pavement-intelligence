"""Transiciones de sesión al pasar de demostración a análisis real."""
from __future__ import annotations

from typing import MutableMapping


def prepare_session_for_real_analysis(session: MutableMapping[str, object]) -> None:
    """Retira solo un lote sintético previo y reinicia temporales de análisis.

    Un lote real ya finalizado se conserva hasta que el usuario finalice otro lote
    de forma explícita. Los datos fuente del dashboard demostrativo no se borran.
    """
    if session.get("is_synthetic_review") is True:
        session["vision_events_raw"] = []
        session["vision_events_reviewed"] = []
        session["vision_batch_metadata"] = {}
        session["traffic_counts_corrected"] = {}
        session["traffic_review_approved"] = False
        session["traffic_review_source_fingerprint"] = None
        session["tpda_input_from_review"] = None

    session["is_synthetic_review"] = False
    session["traffic_demo_playing"] = False
    session["traffic_demo_frame_index"] = 0
    session["traffic_demo_last_update"] = 0.0
    session["traffic_demo_error"] = ""
    session["traffic_analysis_current_result"] = None
    session["traffic_analysis_batch_events"] = []
    session["traffic_analysis_error"] = ""
    session["traffic_analysis_paused"] = False
