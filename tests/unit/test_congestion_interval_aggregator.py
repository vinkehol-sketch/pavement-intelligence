from __future__ import annotations

import inspect
from dataclasses import dataclass

import pytest

from pavement_intelligence.domain.traffic import congestion_aggregation
from pavement_intelligence.domain.traffic.congestion import CongestionEngine, CongestionInput
from pavement_intelligence.domain.traffic.congestion_aggregation import (
    CongestionAggregationConfig,
    CongestionIntervalAggregator,
)
from pavement_intelligence.vision.analysis.controller import FrameAnalysisResult


@dataclass(frozen=True)
class FakeResult:
    timestamp_seconds: float
    vehicles_in_scene: int = 2
    crossing_events: tuple[object, ...] = ()
    direction_counts: dict[object, int] | None = None
    source_type: str = "video_file"
    end_of_source: bool = False

    def __post_init__(self):
        if self.direction_counts is None:
            object.__setattr__(self, "direction_counts", {})


def event(event_id="evt-1", direction=1):
    return {"event_id": event_id, "direction": direction}


def add(aggregator, timestamp, **kwargs):
    source = kwargs.pop("source_id", "video-a.mp4")
    point = kwargs.pop("monitoring_point_id", "P-04")
    paused = kwargs.pop("is_paused", False)
    return aggregator.add(FakeResult(timestamp, **kwargs), source_id=source, monitoring_point_id=point, is_paused=paused)


def test_initial_state():
    aggregator = CongestionIntervalAggregator()
    assert aggregator.last_output is None
    assert aggregator.retained_event_count == aggregator.deduplication_size == 0


def test_first_sample_has_zero_duration_flow_and_accumulation():
    aggregator = CongestionIntervalAggregator()
    result = add(aggregator, 0, vehicles_in_scene=3, crossing_events=(event(),))
    assert result.observation_duration_seconds == 0
    assert result.sample_count == 1
    assert result.vehicles_per_minute == 0
    assert result.accumulation_delta == 0


def test_warmup_window_scales_events_to_vehicles_per_minute():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0, crossing_events=(event("a"),))
    result = add(aggregator, 10, crossing_events=(event("b"),))
    assert result.vehicles_per_minute == pytest.approx(12.0)


def test_full_window_flow_formula():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0, crossing_events=(event("a"),))
    result = add(aggregator, 60, crossing_events=(event("b"), event("c")))
    assert result.vehicles_per_minute == 3


def test_multiple_events_in_one_sample():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0)
    result = add(aggregator, 10, crossing_events=(event("a"), event("b", -1)))
    assert result.vehicles_per_minute == 12
    assert result.direction_counts == {1: 1, -1: 1}


def test_duplicate_event_is_ignored():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0, crossing_events=(event("a"),))
    result = add(aggregator, 10, crossing_events=(event("a"),))
    assert aggregator.retained_event_count == 1
    assert result.vehicles_per_minute == 6


def test_events_and_deduplication_expire_outside_window():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0, crossing_events=(event("a"),))
    result = add(aggregator, 61)
    assert result.vehicles_per_minute == 0
    assert aggregator.retained_event_count == aggregator.deduplication_size == 0


def test_named_directions_are_preserved():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0)
    result = add(aggregator, 10, crossing_events=(event("a", "Norte-Sur"), event("b", "Sur-Norte")))
    assert result.direction_counts == {"Norte-Sur": 1, "Sur-Norte": 1}


def test_latest_scene_replaces_previous_observation():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0, vehicles_in_scene=3)
    assert add(aggregator, 10, vehicles_in_scene=9).vehicles_in_scene == 9


def test_positive_accumulation_uses_real_interval():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0, vehicles_in_scene=3)
    assert add(aggregator, 10, vehicles_in_scene=6).accumulation_delta == 18


def test_negative_accumulation_uses_real_interval():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0, vehicles_in_scene=6)
    assert add(aggregator, 10, vehicles_in_scene=3).accumulation_delta == -18


def test_scene_deadband_suppresses_one_vehicle_noise():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0, vehicles_in_scene=3)
    assert add(aggregator, 10, vehicles_in_scene=4).accumulation_delta == 0


def test_repeated_timestamp_is_valid_but_has_zero_slope():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 5, vehicles_in_scene=2)
    result = add(aggregator, 5, vehicles_in_scene=8)
    assert result.sample_count == 2
    assert result.observation_duration_seconds == 0
    assert result.accumulation_delta == 0


def test_pause_returns_frozen_copy_and_does_not_add_events_or_sample():
    aggregator = CongestionIntervalAggregator()
    first = add(aggregator, 0, crossing_events=(event("a"),))
    paused = add(
        aggregator, 8, vehicles_in_scene=20, crossing_events=(event("b"),), is_paused=True,
    )
    assert paused.is_paused
    assert paused.sample_count == first.sample_count
    assert paused.observation_duration_seconds == first.observation_duration_seconds
    assert paused.vehicles_per_minute == first.vehicles_per_minute
    assert aggregator.retained_event_count == 1


def test_resume_counts_only_time_after_latest_pause_observation():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0)
    add(aggregator, 8, is_paused=True)
    resumed = add(aggregator, 10)
    assert resumed.observation_duration_seconds == 2
    assert resumed.sample_count == 2


def test_pause_before_first_sample_returns_none():
    assert add(CongestionIntervalAggregator(), 0, is_paused=True) is None


def test_reset_clears_all_state_and_allows_new_source():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0, crossing_events=(event(),))
    aggregator.reset()
    result = add(aggregator, 20, source_id="video-b.mp4", monitoring_point_id="P-05")
    assert result.sample_count == 1 and result.observation_duration_seconds == 0
    assert aggregator.deduplication_size == 0


@pytest.mark.parametrize("field,value", [("source_id", "video-b.mp4"), ("monitoring_point_id", "P-05")])
def test_source_or_monitoring_point_change_requires_reset(field, value):
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 0)
    kwargs = {field: value}
    with pytest.raises(ValueError, match="reset"):
        add(aggregator, 1, **kwargs)


def test_regressive_timestamp_is_rejected():
    aggregator = CongestionIntervalAggregator()
    add(aggregator, 10)
    with pytest.raises(ValueError, match="retroceder"):
        add(aggregator, 9)


@pytest.mark.parametrize("timestamp", [-1, float("nan"), float("inf")])
def test_invalid_timestamps_are_rejected(timestamp):
    with pytest.raises(ValueError):
        add(CongestionIntervalAggregator(), timestamp)


def test_negative_scene_is_rejected():
    with pytest.raises(ValueError, match="vehicles_in_scene"):
        add(CongestionIntervalAggregator(), 0, vehicles_in_scene=-1)


def test_negative_source_direction_count_is_rejected():
    with pytest.raises(ValueError, match="direction_counts"):
        add(CongestionIntervalAggregator(), 0, direction_counts={1: -1})


def test_event_without_id_is_rejected():
    with pytest.raises(ValueError, match="event_id"):
        add(CongestionIntervalAggregator(), 0, crossing_events=({"direction": 1},))


@pytest.mark.parametrize("direction", [None, ""])
def test_empty_event_direction_is_rejected(direction):
    with pytest.raises(ValueError, match="dirección"):
        add(CongestionIntervalAggregator(), 0, crossing_events=(event(direction=direction),))


def test_end_of_source_returns_last_sample_without_mutation():
    aggregator = CongestionIntervalAggregator()
    first = add(aggregator, 0, crossing_events=(event("a"),))
    final = add(
        aggregator, 10, end_of_source=True, crossing_events=(event("b"),), vehicles_in_scene=99,
    )
    assert final is first
    assert aggregator.retained_event_count == 1


def test_sample_without_events_is_valid():
    result = add(CongestionIntervalAggregator(), 0)
    assert result.direction_counts == {}
    assert result.vehicles_per_minute == 0


def test_memory_remains_bounded_to_window():
    aggregator = CongestionIntervalAggregator(CongestionAggregationConfig(window_seconds=5))
    for timestamp in range(30):
        add(aggregator, timestamp, crossing_events=(event(f"e-{timestamp}"),))
    assert aggregator.retained_event_count <= 6
    assert aggregator.deduplication_size == aggregator.retained_event_count


@pytest.mark.parametrize("window", [0, -1, float("nan"), float("inf")])
def test_window_must_be_positive_and_finite(window):
    with pytest.raises(ValueError):
        CongestionAggregationConfig(window_seconds=window)


def test_same_sequence_is_deterministic():
    sequence = [
        FakeResult(0, 2, (event("a"),), {}),
        FakeResult(5, 5, (event("b", -1),), {}),
        FakeResult(10, 8, (), {}),
    ]
    first = CongestionIntervalAggregator()
    second = CongestionIntervalAggregator()
    assert [first.add(item, source_id="v", monitoring_point_id="P") for item in sequence] == [
        second.add(item, source_id="v", monitoring_point_id="P") for item in sequence
    ]


def test_output_is_compatible_with_congestion_engine():
    aggregator = CongestionIntervalAggregator()
    engine = CongestionEngine()
    add(aggregator, 0)
    add(aggregator, 5)
    congestion_input = add(aggregator, 10)
    assert isinstance(congestion_input, CongestionInput)
    assessment = engine.evaluate(congestion_input)
    assert assessment.timestamp_seconds == 10


def test_real_frame_analysis_contract_is_accepted_without_image_dependency():
    result = FrameAnalysisResult(
        frame_index=1, timestamp_seconds=0.0, source_type="video_file",
        annotated_frame=None, detections=(), active_tracks=(),
        crossing_events=(), category_counts={}, direction_counts={},
        vehicles_in_scene=0, total_crossings=0, processing_fps=20,
        warnings=(), end_of_source=False, congestion="INSUFFICIENT_DATA",
    )
    output = CongestionIntervalAggregator().add(result, source_id="video.mp4")
    assert output.sample_count == 1


def test_domain_has_no_streamlit_opencv_clock_or_disk_writes():
    source = inspect.getsource(congestion_aggregation).lower()
    assert "streamlit" not in source
    assert "cv2" not in source
    assert "datetime" not in source
    assert "time.time" not in source
    assert "sleep" not in source
    assert "open(" not in source
