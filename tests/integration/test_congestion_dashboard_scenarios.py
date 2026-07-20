"""Escenarios E2E deterministas de congestión hasta la presentación del dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field

from pavement_intelligence.domain.traffic.congestion import CongestionLevel
from pavement_intelligence.domain.traffic.congestion_runtime import (
    CongestionRuntimeState,
)
from pavement_intelligence.ui.utils.congestion_session import (
    ALERTS_KEY,
    LAST_FRAME_KEY,
    PRESENTATION_KEY,
    SNAPSHOT_KEY,
    finish_congestion_session,
    pause_congestion_session,
    process_congestion_result_once,
    reset_congestion_session,
    resume_congestion_session,
    start_congestion_session,
)


@dataclass(frozen=True)
class Result:
    frame_index: int
    timestamp_seconds: float
    vehicles_in_scene: int
    source_type: str = "video_file"
    crossing_events: tuple[object, ...] = ()
    direction_counts: dict[object, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    end_of_source: bool = False


def emit(session, frame_index: int, timestamp: float, scene: int):
    presentation = process_congestion_result_once(
        session, Result(frame_index, timestamp, scene)
    )
    assert presentation is session[PRESENTATION_KEY]
    assert presentation.normative is False
    assert session[SNAPSHOT_KEY].normative is False
    assert session[SNAPSHOT_KEY].origin == "OPERATIONAL_ESTIMATE"
    return session[SNAPSHOT_KEY]


def high_sequence(session):
    emit(session, 0, 0, 10)
    emit(session, 1, 5, 12)
    candidate = emit(session, 2, 10, 14)
    pending = emit(session, 3, 20, 16)
    confirmed = emit(session, 4, 25, 18)
    return candidate, pending, confirmed


def test_scenario_a_warmup_requires_time_and_samples_before_normal():
    session = {}
    start_congestion_session(session, "video:a")

    first = emit(session, 0, 0, 2)
    second = emit(session, 1, 5, 2)
    normal = emit(session, 2, 10, 2)

    assert first.level is second.level is CongestionLevel.INSUFFICIENT_DATA
    assert not first.evidence.sufficient_data
    assert not second.evidence.sufficient_data
    assert normal.level is CongestionLevel.NORMAL
    assert normal.evidence.sufficient_data
    assert normal.observation_duration_seconds == 10
    assert normal.sample_count == 3


def test_scenario_b_moderate_hysteresis_and_exit_thresholds():
    session = {}
    start_congestion_session(session, "video:b")
    emit(session, 0, 0, 2)
    emit(session, 1, 5, 2)
    assert emit(session, 2, 10, 2).level is CongestionLevel.NORMAL

    entered = emit(session, 3, 11, 8)
    held = emit(session, 4, 12, 7)
    exited = emit(session, 5, 13, 5)

    assert entered.level is CongestionLevel.MODERATE
    assert held.level is CongestionLevel.MODERATE
    assert exited.level is CongestionLevel.NORMAL


def test_scenario_c_high_requires_15_seconds_and_alert_is_deduplicated():
    session = {}
    start_congestion_session(session, "video:c", monitoring_point_id="P-04")

    candidate, pending, confirmed = high_sequence(session)
    assert candidate.candidate_level is CongestionLevel.HIGH
    assert candidate.candidate_elapsed_seconds == 0
    assert pending.level is CongestionLevel.MODERATE
    assert pending.candidate_elapsed_seconds == 10
    assert pending.alert is None
    assert confirmed.level is CongestionLevel.HIGH
    assert confirmed.candidate_elapsed_seconds == 15
    assert confirmed.alert is not None and confirmed.alert.active
    assert len(session[ALERTS_KEY]) == 1

    before = confirmed.sample_count
    duplicate_view = process_congestion_result_once(session, Result(4, 25, 18))
    assert duplicate_view is session[PRESENTATION_KEY]
    assert session[SNAPSHOT_KEY] is confirmed
    assert session[SNAPSHOT_KEY].sample_count == before
    assert len(session[ALERTS_KEY]) == 1


def test_scenario_d_high_recovery_requires_5_seconds_without_new_alert():
    session = {}
    start_congestion_session(session, "video:d", monitoring_point_id="P-04")
    _, _, high = high_sequence(session)
    alert_id = high.alert.alert_id

    recovering = emit(session, 5, 27, 5)
    recovered = emit(session, 6, 30, 5)

    assert recovering.level is CongestionLevel.HIGH
    assert recovered.level is CongestionLevel.MODERATE
    assert recovered.alert is not None and not recovered.alert.active
    assert recovered.alert.alert_id == alert_id
    assert len(session[ALERTS_KEY]) == 1
    assert session[ALERTS_KEY][0].alert_id == alert_id
    assert session[ALERTS_KEY][0].status == "Cerrada"


def test_scenario_e_pause_and_rerun_do_not_advance_confirmation():
    session = {}
    start_congestion_session(session, "video:e")
    emit(session, 0, 0, 10)
    emit(session, 1, 5, 12)
    candidate = emit(session, 2, 10, 14)
    paused_view = pause_congestion_session(session)
    assert paused_view.is_paused

    paused = emit(session, 3, 20, 20)
    assert paused.state is CongestionRuntimeState.PAUSED
    assert paused.sample_count == candidate.sample_count
    assert paused.observation_duration_seconds == candidate.observation_duration_seconds
    assert paused.candidate_elapsed_seconds == candidate.candidate_elapsed_seconds
    process_congestion_result_once(session, Result(3, 20, 20))
    assert session[SNAPSHOT_KEY] is paused

    resume_congestion_session(session)
    resumed = emit(session, 4, 25, 16)
    assert resumed.state is CongestionRuntimeState.ACTIVE
    assert resumed.observation_duration_seconds == 15
    assert resumed.candidate_elapsed_seconds == 5
    assert resumed.alert is None


def test_scenario_f_reset_and_source_change_clear_previous_congestion():
    session = {}
    start_congestion_session(session, "video:f", monitoring_point_id="P-04")
    high_sequence(session)
    assert session[ALERTS_KEY]

    coordinator = reset_congestion_session(session, "video:f")
    assert coordinator.state is CongestionRuntimeState.IDLE
    assert session[SNAPSHOT_KEY] is None
    assert session[PRESENTATION_KEY] is None
    assert session[LAST_FRAME_KEY] is None
    assert session[ALERTS_KEY] == ()

    start_congestion_session(session, "camera:0")
    fresh = emit(session, 0, 100, 1)
    assert fresh.source_id == "camera:0"
    assert fresh.level is CongestionLevel.INSUFFICIENT_DATA
    assert fresh.sample_count == 1
    assert fresh.observation_duration_seconds == 0
    assert fresh.vehicles_per_minute == 0
    assert fresh.alert is None
    assert session[ALERTS_KEY] == ()


def test_finalization_and_last_frame_rerun_are_idempotent():
    session = {}
    coordinator = start_congestion_session(session, "video:final")
    emit(session, 0, 0, 2)
    emit(session, 1, 5, 2)
    final_frame = emit(session, 2, 10, 2)
    process_congestion_result_once(session, Result(2, 10, 2))
    assert session[SNAPSHOT_KEY] is final_frame

    first = finish_congestion_session(session)
    first_snapshot = session[SNAPSHOT_KEY]
    second = finish_congestion_session(session)

    assert first.is_final and second.is_final
    assert session[SNAPSHOT_KEY] is first_snapshot
    assert first_snapshot.is_final
    assert first_snapshot.sample_count == 3
    assert coordinator.state is CongestionRuntimeState.FINISHED
    assert session[ALERTS_KEY] == ()
