from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

from pavement_intelligence.domain.traffic import congestion
from pavement_intelligence.domain.traffic.congestion import (
    DEMONSTRATIVE_CONFIGURATION_NOTICE,
    CongestionEngine,
    CongestionInput,
    CongestionLevel,
    CongestionThresholds,
)


def sample(
    timestamp=10.0, *, duration=None, count=3, scene=2, flow=5.0,
    accumulation=0.0, paused=False, directions=None, point="P-04",
):
    return CongestionInput(
        timestamp_seconds=timestamp,
        observation_duration_seconds=timestamp if duration is None else duration,
        sample_count=count,
        vehicles_in_scene=scene,
        vehicles_per_minute=flow,
        accumulation_delta=accumulation,
        direction_counts=directions or {1: 1, -1: 1},
        is_paused=paused,
        monitoring_point_id=point,
    )


def high_sample(timestamp, *, duration=None, paused=False):
    return sample(timestamp, duration=duration, count=20, scene=18, flow=8, accumulation=3, paused=paused)


def confirmed_high_engine():
    engine = CongestionEngine()
    engine.evaluate(sample(10))
    engine.evaluate(high_sample(20))
    assessment = engine.evaluate(high_sample(35))
    assert assessment.level is CongestionLevel.HIGH
    return engine, assessment


def test_insufficient_data_at_start():
    result = CongestionEngine().evaluate(sample(6, count=2))
    assert result.level is CongestionLevel.INSUFFICIENT_DATA
    assert not result.evidence.sufficient_data
    assert "6.0 de 10.0" in result.evidence.summary


def test_exactly_ten_seconds_is_sufficient():
    assert CongestionEngine().evaluate(sample(10)).level is CongestionLevel.NORMAL


def test_sample_count_can_keep_data_insufficient():
    result = CongestionEngine().evaluate(sample(20, count=2))
    assert result.level is CongestionLevel.INSUFFICIENT_DATA
    assert "2 de 3 muestras" in result.evidence.summary


def test_normal_state():
    result = CongestionEngine().evaluate(sample(15, scene=3, flow=12))
    assert result.level is CongestionLevel.NORMAL


def test_enters_moderate_at_exact_scene_threshold():
    result = CongestionEngine().evaluate(sample(10, scene=8))
    assert result.level is CongestionLevel.MODERATE
    assert "MODERATE_SCENE" in result.evidence.active_rules


def test_moderate_hysteresis_and_exit():
    engine = CongestionEngine()
    engine.evaluate(sample(10, scene=8))
    assert engine.evaluate(sample(11, scene=7)).level is CongestionLevel.MODERATE
    assert engine.evaluate(sample(12, scene=5)).level is CongestionLevel.NORMAL


def test_high_starts_as_pending_moderate():
    engine = CongestionEngine()
    engine.evaluate(sample(10))
    result = engine.evaluate(high_sample(20))
    assert result.level is CongestionLevel.MODERATE
    assert result.evidence.high_candidate_pending
    assert result.evidence.candidate_elapsed_seconds == 0
    assert "pendiente" in result.evidence.summary


def test_high_not_confirmed_before_fifteen_seconds():
    engine = CongestionEngine()
    engine.evaluate(sample(10)); engine.evaluate(high_sample(20))
    result = engine.evaluate(high_sample(34.9))
    assert result.level is CongestionLevel.MODERATE
    assert result.alert is None


def test_high_confirms_exactly_at_fifteen_seconds():
    _, result = confirmed_high_engine()
    assert result.alert_emitted
    assert result.alert is not None and result.alert.active
    assert result.alert.confirmed_at_seconds == 35


def test_high_candidate_is_cancelled_when_condition_disappears():
    engine = CongestionEngine()
    engine.evaluate(sample(10)); engine.evaluate(high_sample(20))
    result = engine.evaluate(sample(25, scene=8, accumulation=0))
    assert not result.evidence.high_candidate_pending
    assert result.alert is None


def test_sustained_high_does_not_duplicate_alert():
    engine, first = confirmed_high_engine()
    second = engine.evaluate(high_sample(40))
    assert first.alert_emitted
    assert not second.alert_emitted
    assert second.alert.alert_id == first.alert.alert_id


def test_recovery_from_high_is_confirmed_and_closes_alert():
    engine, _ = confirmed_high_engine()
    result = engine.evaluate(sample(40, scene=5, flow=10, accumulation=0))
    assert result.level is CongestionLevel.MODERATE
    assert result.alert is not None and not result.alert.active
    assert engine.evaluate(sample(41, scene=5)).level is CongestionLevel.NORMAL


def test_pause_does_not_advance_high_timer():
    engine = CongestionEngine()
    engine.evaluate(sample(10)); engine.evaluate(high_sample(20))
    paused = engine.evaluate(high_sample(30, duration=20, paused=True))
    assert paused.evidence.candidate_elapsed_seconds == 0
    resumed = engine.evaluate(high_sample(31, duration=21))
    assert resumed.evidence.candidate_elapsed_seconds == 1


def test_pause_cannot_increment_observation_duration():
    engine = CongestionEngine(); engine.evaluate(sample(10))
    with pytest.raises(ValueError, match="pausa"):
        engine.evaluate(sample(11, duration=11, paused=True))


def test_reset_clears_level_candidate_timer_alert_and_evidence():
    engine, _ = confirmed_high_engine()
    engine.reset()
    assert engine.level is CongestionLevel.INSUFFICIENT_DATA
    result = engine.evaluate(sample(0, duration=0, count=0, directions={}))
    assert result.level is CongestionLevel.INSUFFICIENT_DATA
    assert result.alert is None
    assert result.evidence.candidate_elapsed_seconds == 0


def test_high_flow_with_stable_low_scene_is_not_high():
    result = CongestionEngine().evaluate(sample(10, scene=4, flow=80, accumulation=0))
    assert result.level is CongestionLevel.MODERATE
    assert "HIGH_FLOW_SUPPORTING_ONLY" in result.evidence.active_rules


def test_growing_accumulation_enters_moderate():
    result = CongestionEngine().evaluate(sample(10, scene=4, accumulation=2))
    assert result.level is CongestionLevel.MODERATE


def test_direction_counts_are_copied_and_immutable():
    counts = {1: 2, -1: 3}
    value = sample(directions=counts)
    counts[1] = 99
    assert value.direction_counts[1] == 2
    with pytest.raises(TypeError):
        value.direction_counts[1] = 4


@pytest.mark.parametrize("field,value", [
    ("timestamp_seconds", -1), ("observation_duration_seconds", -1),
    ("vehicles_per_minute", -1), ("timestamp_seconds", float("nan")),
    ("vehicles_per_minute", float("inf")),
])
def test_input_rejects_invalid_numeric_values(field, value):
    values = vars(sample()).copy(); values[field] = value
    with pytest.raises((TypeError, ValueError)):
        CongestionInput(**values)


@pytest.mark.parametrize("field,value", [("sample_count", -1), ("vehicles_in_scene", -1)])
def test_input_rejects_negative_integer_values(field, value):
    values = vars(sample()).copy(); values[field] = value
    with pytest.raises(ValueError):
        CongestionInput(**values)


def test_input_rejects_negative_direction_count():
    with pytest.raises(ValueError, match="direction_counts"):
        sample(directions={1: -1})


def test_input_rejects_inconsistent_duration():
    with pytest.raises(ValueError, match="duración"):
        sample(5, duration=6)


def test_regressive_timestamp_is_rejected():
    engine = CongestionEngine(); engine.evaluate(sample(10))
    with pytest.raises(ValueError, match="retroceder"):
        engine.evaluate(sample(9))


def test_regressive_observation_duration_is_rejected():
    engine = CongestionEngine(); engine.evaluate(sample(10))
    with pytest.raises(ValueError, match="use reset"):
        engine.evaluate(sample(11, duration=9))


def test_custom_thresholds_are_applied():
    thresholds = CongestionThresholds(moderate_scene_enter=4, moderate_scene_exit=2)
    assert CongestionEngine(thresholds).evaluate(sample(10, scene=4)).level is CongestionLevel.MODERATE


@pytest.mark.parametrize("kwargs", [
    {"moderate_scene_exit": 9},
    {"high_scene_enter": 8},
    {"moderate_flow_exit": 50},
    {"high_flow_enter": 40},
    {"moderate_accumulation_exit": 3},
    {"high_accumulation_enter": 2},
    {"minimum_sample_count": 0},
])
def test_incoherent_thresholds_are_rejected(kwargs):
    with pytest.raises(ValueError):
        CongestionThresholds(**kwargs)


def test_thresholds_and_inputs_are_frozen():
    with pytest.raises(FrozenInstanceError):
        CongestionThresholds().minimum_sample_count = 8
    with pytest.raises(FrozenInstanceError):
        sample().sample_count = 8


def test_default_configuration_is_identified_as_demonstrative():
    assert CongestionThresholds().configuration_notice == DEMONSTRATIVE_CONFIGURATION_NOTICE


def test_same_sequence_is_deterministic():
    sequence = [sample(10), high_sample(20), high_sample(35), high_sample(36)]
    first = [CongestionEngine().evaluate(sequence[0])]
    engine_a = CongestionEngine(); engine_b = CongestionEngine()
    assert [engine_a.evaluate(item) for item in sequence] == [engine_b.evaluate(item) for item in sequence]
    assert first[0].level is CongestionLevel.NORMAL


def test_alert_is_stable_and_explicitly_non_normative():
    _, result = confirmed_high_engine()
    assert len(result.alert.alert_id) == 16
    assert result.alert.origin == "OPERATIONAL_ESTIMATE"
    assert result.alert.normative is False
    assert "no normativa" in result.alert.message


def test_domain_has_no_streamlit_opencv_approval_tpda_or_disk_writes():
    source = inspect.getsource(congestion).lower()
    assert "streamlit" not in source
    assert "cv2" not in source
    assert "session_state" not in source
    assert "tpda" not in source
    assert "approve" not in source
    assert "open(" not in source
