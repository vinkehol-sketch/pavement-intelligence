from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, dataclass

import pytest

from pavement_intelligence.domain.traffic import congestion_runtime
from pavement_intelligence.domain.traffic.congestion import (
    CongestionEngine,
    CongestionLevel,
)
from pavement_intelligence.domain.traffic.congestion_aggregation import (
    CongestionIntervalAggregator,
)
from pavement_intelligence.domain.traffic.congestion_runtime import (
    CongestionRuntimeState,
    TrafficCongestionCoordinator,
)
from pavement_intelligence.vision.analysis.controller import FrameAnalysisResult


@dataclass(frozen=True)
class FakeResult:
    timestamp_seconds: float
    vehicles_in_scene: int = 2
    crossing_events: tuple[object, ...] = ()
    direction_counts: dict[object, int] | None = None
    source_type: str = "video_file"
    warnings: tuple[str, ...] = ()
    end_of_source: bool = False

    def __post_init__(self):
        if self.direction_counts is None:
            object.__setattr__(self, "direction_counts", {})


def event(event_id="evt-1", direction=1):
    return {"event_id": event_id, "direction": direction}


def coordinator(*, aggregator=None, engine=None):
    value = TrafficCongestionCoordinator(
        aggregator or CongestionIntervalAggregator(),
        engine or CongestionEngine(),
        monitoring_point_id="P-04",
    )
    value.set_source("video-a.mp4")
    return value


def process(runtime, timestamp, **kwargs):
    return runtime.process_frame_result(FakeResult(timestamp, **kwargs))


def warm(runtime):
    process(runtime, 0, vehicles_in_scene=2)
    process(runtime, 5, vehicles_in_scene=2)
    return process(runtime, 10, vehicles_in_scene=2)


def confirm_high(runtime):
    process(runtime, 0, vehicles_in_scene=10)
    process(runtime, 5, vehicles_in_scene=12)
    process(runtime, 10, vehicles_in_scene=14)
    pending = process(runtime, 15, vehicles_in_scene=18)
    confirmed = process(runtime, 30, vehicles_in_scene=20)
    return pending, confirmed


def test_initial_state():
    runtime = TrafficCongestionCoordinator(
        CongestionIntervalAggregator(), CongestionEngine()
    )
    assert runtime.state is CongestionRuntimeState.IDLE
    assert runtime.source_id is runtime.last_snapshot is None
    assert runtime.error_message == ""


def test_first_sample_is_warming_up():
    snapshot = process(coordinator(), 0)
    assert snapshot.state is CongestionRuntimeState.WARMING_UP
    assert snapshot.level is CongestionLevel.INSUFFICIENT_DATA
    assert snapshot.sample_count == 1


def test_warming_up_until_real_minimums_are_met():
    runtime = coordinator()
    assert process(runtime, 0).state is CongestionRuntimeState.WARMING_UP
    assert process(runtime, 5).state is CongestionRuntimeState.WARMING_UP


def test_becomes_active_with_sufficient_data():
    snapshot = warm(coordinator())
    assert snapshot.state is CongestionRuntimeState.ACTIVE
    assert snapshot.level is CongestionLevel.NORMAL


def test_normal_snapshot():
    snapshot = warm(coordinator())
    assert snapshot.vehicles_in_scene == 2
    assert snapshot.observation_duration_seconds == 10
    assert snapshot.evidence.sufficient_data


def test_moderate_snapshot():
    runtime = coordinator()
    process(runtime, 0)
    process(runtime, 5)
    assert process(runtime, 10, vehicles_in_scene=8).level is CongestionLevel.MODERATE


def test_high_is_pending_before_confirmation():
    pending, _ = confirm_high(coordinator())
    assert pending.level is CongestionLevel.MODERATE
    assert pending.candidate_level is CongestionLevel.HIGH
    assert pending.candidate_elapsed_seconds == 5


def test_high_is_confirmed_and_alert_is_exposed_unchanged():
    _, snapshot = confirm_high(coordinator())
    assert snapshot.level is CongestionLevel.HIGH
    assert snapshot.alert is not None and snapshot.alert.active
    assert snapshot.alert.normative is False
    assert snapshot.alert.evidence is snapshot.evidence


def test_sustained_high_does_not_duplicate_alert():
    runtime = coordinator()
    _, first = confirm_high(runtime)
    second = process(runtime, 45, vehicles_in_scene=22)
    assert second.alert.alert_id == first.alert.alert_id
    assert second.alert is first.alert


def test_snapshot_is_explainable():
    snapshot = warm(coordinator())
    assert snapshot.evidence.summary
    assert snapshot.evidence.observed_metrics
    assert snapshot.evidence.compared_thresholds


def test_pause_freezes_snapshot_and_level():
    runtime = coordinator()
    active = warm(runtime)
    paused = runtime.pause()
    assert paused.state is CongestionRuntimeState.PAUSED and paused.is_paused
    assert paused.level is active.level
    assert paused.sample_count == active.sample_count


def test_paused_result_does_not_advance_time_or_add_event():
    runtime = coordinator()
    active = warm(runtime)
    paused = runtime.pause()
    same = runtime.process_frame_result(
        FakeResult(20, vehicles_in_scene=30, crossing_events=(event("new"),))
    )
    assert same is paused
    assert same.observation_duration_seconds == active.observation_duration_seconds
    assert same.sample_count == active.sample_count


def test_resume_uses_next_valid_interval_after_paused_observation():
    runtime = coordinator()
    warm(runtime)
    runtime.pause()
    runtime.process_paused_state(FakeResult(20))
    resumed = runtime.resume()
    assert resumed.state is CongestionRuntimeState.ACTIVE and not resumed.is_paused
    following = process(runtime, 22)
    assert following.observation_duration_seconds == 12


def test_pause_timestamp_and_resume_timestamp_exclude_pause_interval():
    runtime = coordinator()
    warm(runtime)
    runtime.pause(12)
    runtime.resume(20)
    assert process(runtime, 22).observation_duration_seconds == 12


def test_pause_before_start_is_rejected_without_changing_state():
    runtime = coordinator()
    with pytest.raises(RuntimeError, match="iniciado"):
        runtime.pause()
    assert runtime.state is CongestionRuntimeState.IDLE


def test_double_pause_and_double_resume_are_idempotent():
    runtime = coordinator()
    warm(runtime)
    first = runtime.pause()
    assert runtime.pause() is first
    runtime.resume()
    second = runtime.resume()
    assert second.state is CongestionRuntimeState.ACTIVE


def test_reset_clears_all_runtime_and_dependencies():
    runtime = coordinator()
    confirm_high(runtime)
    runtime.reset()
    assert runtime.state is CongestionRuntimeState.IDLE
    assert runtime.source_id is runtime.last_snapshot is None
    runtime.set_source("video-b.mp4")
    assert process(runtime, 100).sample_count == 1


def test_repeated_reset_is_safe():
    runtime = coordinator()
    runtime.reset()
    runtime.reset()
    assert runtime.state is CongestionRuntimeState.IDLE


def test_source_change_requires_explicit_reset():
    runtime = coordinator()
    process(runtime, 0)
    with pytest.raises(RuntimeError, match="reset"):
        runtime.set_source("video-b.mp4")


def test_same_source_assignment_is_idempotent():
    runtime = coordinator()
    runtime.set_source("video-a.mp4")
    assert runtime.source_id == "video-a.mp4"


@pytest.mark.parametrize("source", ["", "   ", None, 4])
def test_empty_or_invalid_source_is_rejected(source):
    runtime = TrafficCongestionCoordinator(
        CongestionIntervalAggregator(), CongestionEngine()
    )
    with pytest.raises((TypeError, ValueError)):
        runtime.set_source(source)


def test_end_of_source_finalizes_without_new_sample():
    runtime = coordinator()
    last = warm(runtime)
    final = process(
        runtime,
        20,
        end_of_source=True,
        crossing_events=(event("ignored"),),
        warnings=("Fin de la fuente.",),
    )
    assert final.state is CongestionRuntimeState.FINISHED and final.is_final
    assert final.sample_count == last.sample_count
    assert final.warnings == ("Fin de la fuente.",)


def test_end_of_source_before_samples_produces_empty_final_snapshot():
    final = process(coordinator(), 0, end_of_source=True)
    assert final.is_final and final.sample_count == 0
    assert final.level is CongestionLevel.INSUFFICIENT_DATA


def test_repeated_finish_preserves_snapshot_and_alert():
    runtime = coordinator()
    _, high = confirm_high(runtime)
    first = runtime.finish()
    second = runtime.finish()
    assert second is first
    assert first.alert is high.alert


def test_result_after_finished_is_rejected_without_mutation():
    runtime = coordinator()
    warm(runtime)
    final = runtime.finish()
    with pytest.raises(RuntimeError, match="finalizó"):
        process(runtime, 20)
    assert runtime.last_snapshot is final


class BrokenAggregator:
    def reset(self):
        pass

    def add(self, *args, **kwargs):
        raise LookupError("aggregator exploded")


class BrokenEngine:
    def reset(self):
        pass

    def evaluate(self, sample):
        raise LookupError("engine exploded")


def test_aggregator_exception_sets_error_and_is_not_hidden():
    runtime = coordinator(aggregator=BrokenAggregator())
    with pytest.raises(LookupError, match="aggregator exploded"):
        process(runtime, 0)
    assert runtime.state is CongestionRuntimeState.ERROR
    assert runtime.error_message == "aggregator exploded"


def test_engine_exception_sets_error_and_is_not_hidden():
    runtime = coordinator(engine=BrokenEngine())
    with pytest.raises(LookupError, match="engine exploded"):
        process(runtime, 0)
    assert runtime.state is CongestionRuntimeState.ERROR


def test_error_rejects_processing_until_reset():
    runtime = coordinator(engine=BrokenEngine())
    with pytest.raises(LookupError):
        process(runtime, 0)
    with pytest.raises(RuntimeError, match="ERROR"):
        process(runtime, 1)


def test_reset_recovers_from_error():
    runtime = coordinator(engine=BrokenEngine())
    with pytest.raises(LookupError):
        process(runtime, 0)
    runtime.reset()
    assert runtime.state is CongestionRuntimeState.IDLE and runtime.error_message == ""


def test_null_result_is_explicit_and_enters_error():
    runtime = coordinator()
    with pytest.raises(ValueError, match="nulo"):
        runtime.process_frame_result(None)
    assert runtime.state is CongestionRuntimeState.ERROR


def test_wrong_result_type_is_explicit_and_enters_error():
    runtime = coordinator()
    with pytest.raises(TypeError, match="FrameAnalysisResult"):
        runtime.process_frame_result(object())
    assert runtime.state is CongestionRuntimeState.ERROR


@pytest.mark.parametrize("timestamp", [-1, float("nan"), float("inf"), "1", True])
def test_invalid_timestamp_is_explicit(timestamp):
    runtime = coordinator()
    with pytest.raises((TypeError, ValueError), match="timestamp_seconds"):
        process(runtime, timestamp)
    assert runtime.state is CongestionRuntimeState.ERROR


def test_input_result_and_crossing_events_are_not_mutated():
    runtime = coordinator()
    crossing = {"event_id": "a", "direction": 1, "payload": [1]}
    result = FakeResult(0, crossing_events=(crossing,), direction_counts={1: 1})
    before = (dict(crossing), dict(result.direction_counts))
    runtime.process_frame_result(result)
    assert crossing == before[0] and result.direction_counts == before[1]


def test_snapshot_copies_direction_counts_and_is_frozen():
    runtime = coordinator()
    process(runtime, 0, crossing_events=(event("a"),))
    snapshot = process(runtime, 10, crossing_events=(event("b", -1),))
    with pytest.raises(TypeError):
        snapshot.direction_counts[1] = 99
    with pytest.raises(FrozenInstanceError):
        snapshot.sample_count = 99


def test_same_sequence_is_deterministic():
    sequence = [
        FakeResult(0),
        FakeResult(5),
        FakeResult(10, crossing_events=(event(),)),
    ]
    first, second = coordinator(), coordinator()
    assert [first.process_frame_result(item) for item in sequence] == [
        second.process_frame_result(item) for item in sequence
    ]


def test_real_engine_and_aggregator_are_compatible_in_full_sequence():
    runtime = coordinator()
    states = [process(runtime, time).state for time in (0, 5, 10, 15)]
    assert states == [
        CongestionRuntimeState.WARMING_UP,
        CongestionRuntimeState.WARMING_UP,
        CongestionRuntimeState.ACTIVE,
        CongestionRuntimeState.ACTIVE,
    ]


def test_real_frame_analysis_result_contract_is_accepted():
    result = FrameAnalysisResult(
        frame_index=1,
        timestamp_seconds=0.0,
        source_type="video_file",
        annotated_frame=None,
        detections=(),
        active_tracks=(),
        crossing_events=(),
        category_counts={},
        direction_counts={},
        vehicles_in_scene=0,
        total_crossings=0,
        processing_fps=20,
        warnings=(),
        end_of_source=False,
        congestion="INSUFFICIENT_DATA",
    )
    assert coordinator().process_frame_result(result).sample_count == 1


def test_high_flow_alone_stays_moderate():
    runtime = coordinator()
    process(runtime, 0, crossing_events=tuple(event(f"a-{i}") for i in range(5)))
    process(runtime, 5, crossing_events=tuple(event(f"b-{i}") for i in range(5)))
    snapshot = process(
        runtime, 10, crossing_events=tuple(event(f"c-{i}") for i in range(5))
    )
    assert snapshot.vehicles_per_minute >= 60
    assert snapshot.level is CongestionLevel.MODERATE
    assert snapshot.candidate_level is None


def test_growing_scene_exposes_positive_accumulation():
    runtime = coordinator()
    process(runtime, 0, vehicles_in_scene=2)
    snapshot = process(runtime, 10, vehicles_in_scene=6)
    assert snapshot.accumulation_delta == 24


def test_reset_removes_confirmed_alert():
    runtime = coordinator()
    confirm_high(runtime)
    runtime.reset()
    runtime.set_source("new")
    assert process(runtime, 0).alert is None


def test_snapshot_is_explicitly_operational_and_non_normative():
    snapshot = process(coordinator(), 0)
    assert snapshot.origin == "OPERATIONAL_ESTIMATE"
    assert snapshot.normative is False


def test_runtime_has_no_ui_vision_disk_approval_or_tpda_dependencies():
    source = inspect.getsource(congestion_runtime).lower()
    for forbidden in (
        "streamlit",
        "cv2",
        "numpy",
        "traffic_monitoring",
        "tpda",
        "approval",
        "open(",
    ):
        assert forbidden not in source


def test_final_snapshot_preserves_metrics_and_is_not_paused():
    runtime = coordinator()
    active = warm(runtime)
    runtime.pause()
    final = runtime.finish()
    assert final.is_final and not final.is_paused
    assert final.sample_count == active.sample_count
    assert final.observation_duration_seconds == active.observation_duration_seconds
