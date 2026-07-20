from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from pavement_intelligence.domain.traffic.congestion import (
    CongestionAlert,
    CongestionEvidence,
    CongestionLevel,
)
from pavement_intelligence.domain.traffic.congestion_runtime import (
    CongestionRuntimeState,
    TrafficCongestionSnapshot,
)
from pavement_intelligence.ui.utils import congestion_presentation
from pavement_intelligence.ui.utils.congestion_presentation import (
    present_congestion_alert,
    present_congestion_snapshot,
)


def evidence(
    level: CongestionLevel,
    *,
    sufficient: bool = True,
    pending: bool = False,
    elapsed: float = 0.0,
    rules: tuple[str, ...] = (),
):
    return CongestionEvidence(
        previous_level=CongestionLevel.NORMAL,
        resulting_level=level,
        high_candidate_pending=pending,
        candidate_elapsed_seconds=elapsed,
        observed_metrics=(("sample_count", 3),),
        active_rules=rules,
        compared_thresholds=(("high_confirmation_seconds", 15.0),),
        warnings=(),
        sufficient_data=sufficient,
        summary=(
            "Datos insuficientes: 5.0 de 10.0 segundos observados; 2 de 3 muestras."
            if not sufficient
            else "Evidencia operacional disponible."
        ),
    )


def snapshot(level=CongestionLevel.NORMAL, **changes):
    value = TrafficCongestionSnapshot(
        timestamp_seconds=10.0,
        source_id="video.mp4",
        state=CongestionRuntimeState.ACTIVE,
        level=level,
        previous_level=CongestionLevel.NORMAL,
        vehicles_per_minute=12.25,
        vehicles_in_scene=7,
        accumulation_delta=2.5,
        direction_counts={1: 2},
        observation_duration_seconds=10.0,
        sample_count=3,
        candidate_level=None,
        candidate_elapsed_seconds=0.0,
        alert=None,
        evidence=evidence(level),
        warnings=(),
        is_paused=False,
        is_final=False,
    )
    return replace(value, **changes)


def high_alert(*, active=True):
    proof = evidence(CongestionLevel.HIGH, rules=("HIGH_SCENE_ACCUMULATION",))
    return CongestionAlert(
        alert_id="alert-1",
        level=CongestionLevel.HIGH,
        started_at_seconds=10,
        confirmed_at_seconds=25,
        monitoring_point_id="P-04",
        message="Congestión alta confirmada; estimación operativa no normativa.",
        evidence=proof,
        active=active,
    )


def test_insufficient_data_presents_warmup_progress():
    proof = evidence(CongestionLevel.INSUFFICIENT_DATA, sufficient=False)
    view = present_congestion_snapshot(
        snapshot(
            CongestionLevel.INSUFFICIENT_DATA,
            state=CongestionRuntimeState.WARMING_UP,
            evidence=proof,
        )
    )
    assert view.level_label == "Datos insuficientes"
    assert "5.0 de 10.0" in view.summary and "2 de 3" in view.summary
    assert not view.data_sufficient and not view.alert_text


@pytest.mark.parametrize(
    "level,label,variant",
    [
        (CongestionLevel.NORMAL, "Tránsito normal", "success"),
        (CongestionLevel.MODERATE, "Congestión moderada", "warning"),
        (CongestionLevel.HIGH, "Congestión alta", "error"),
    ],
)
def test_level_mapping(level, label, variant):
    view = present_congestion_snapshot(snapshot(level))
    assert (view.level_label, view.level_code, view.badge_variant) == (
        label,
        level.value,
        variant,
    )


def test_pending_high_keeps_real_level_and_shows_confirmation_progress():
    proof = evidence(
        CongestionLevel.MODERATE,
        pending=True,
        elapsed=5,
        rules=("HIGH_SCENE_ACCUMULATION",),
    )
    view = present_congestion_snapshot(
        snapshot(
            CongestionLevel.MODERATE,
            candidate_level=CongestionLevel.HIGH,
            candidate_elapsed_seconds=5,
            evidence=proof,
        )
    )
    assert view.level_code == "MODERATE"
    assert "pendiente de confirmación" in view.candidate_text
    assert "5.0 de 15.0 segundos" in view.candidate_text


def test_confirmed_high_exposes_non_normative_alert():
    alert = high_alert()
    view = present_congestion_snapshot(
        snapshot(CongestionLevel.HIGH, alert=alert, evidence=alert.evidence)
    )
    assert "Alerta activa" in view.alert_text
    assert "Nivel de Servicio normativo" in view.alert_text


def test_units_are_explicit_and_accumulation_preserves_sign():
    view = present_congestion_snapshot(snapshot())
    assert view.vehicles_per_minute_text == "12.2 veh/min"
    assert view.vehicles_in_scene_text == "7 vehículos"
    assert view.accumulation_text == "+2.5 veh/min"
    assert view.observation_time_text == "10.0 segundos"


def test_evidence_rules_are_presented_as_labels():
    proof = evidence(
        CongestionLevel.MODERATE,
        rules=("MODERATE_SCENE", "MODERATE_ACCUMULATION"),
    )
    view = present_congestion_snapshot(
        snapshot(CongestionLevel.MODERATE, evidence=proof)
    )
    assert "Ocupación visual elevada" in view.evidence_lines
    assert "Acumulación positiva" in view.evidence_lines


def test_warnings_are_copied_to_immutable_tuple():
    view = present_congestion_snapshot(snapshot(warnings=("Calibración pendiente.",)))
    assert view.warning_lines == ("Calibración pendiente.",)


def test_paused_and_final_headlines_are_explicit():
    paused = present_congestion_snapshot(
        snapshot(is_paused=True, state=CongestionRuntimeState.PAUSED)
    )
    final = present_congestion_snapshot(
        snapshot(is_final=True, state=CongestionRuntimeState.FINISHED)
    )
    assert paused.headline.startswith("Análisis pausado") and paused.is_paused
    assert final.headline.startswith("Análisis finalizado") and final.is_final


def test_origin_and_normative_label_are_constant():
    view = present_congestion_snapshot(snapshot())
    assert view.origin_label == "Estimación operativa"
    assert view.normative is False


def test_alert_presentation_preserves_identity_origin_and_status():
    active = present_congestion_alert(high_alert())
    closed = present_congestion_alert(high_alert(active=False))
    assert active.alert_id == closed.alert_id == "alert-1"
    assert active.status == "Activa" and closed.status == "Cerrada"
    assert active.origin == "OPERATIONAL_ESTIMATE" and not active.normative


def test_adapter_has_no_streamlit_opencv_or_congestion_calculation():
    source = inspect.getsource(congestion_presentation).lower()
    assert "import streamlit" not in source
    assert "import cv2" not in source
    assert "congestionengine" not in source
    assert "congestionintervalaggregator" not in source
