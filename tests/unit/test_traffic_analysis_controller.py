from __future__ import annotations

import inspect

import numpy as np

from pavement_intelligence.integration.traffic_event_adapter import build_traffic_event_batch
from pavement_intelligence.vision.analysis import (
    AnalysisState, TrafficAnalysisController, classify_congestion,
)
from pavement_intelligence.vision.analysis import controller as controller_module
from pavement_intelligence.vision.capture import FrameResult, FrameSource, SourceInfo
from pavement_intelligence.vision.detection.base import Detection
from pavement_intelligence.vision.pipeline import VisionPipeline


class FakeSource(FrameSource):
    def __init__(self, frame_count=3, fail=False):
        self.frame_count = frame_count
        self.position = 0
        self.opened = False
        self.fail = fail

    def open(self): self.opened = True; self.position = 0; return True
    def close(self): self.opened = False
    def is_open(self): return self.opened
    @property
    def source_id(self): return "fake.mp4"
    def source_info(self): return SourceInfo(self.source_id, "video_file", 10.0, 100, 100, self.frame_count, self.position)
    def read(self):
        if self.fail:
            raise RuntimeError("fallo controlado")
        if not self.opened or self.position >= self.frame_count:
            return FrameResult(None, self.position, self.position * 100, False, self.source_id)
        self.position += 1
        return FrameResult(np.zeros((100, 100, 3), dtype=np.uint8), self.position, self.position * 100, True, self.source_id)


class SequenceDetector:
    def __init__(self): self.index = 0
    def map_class_to_category(self, name): return {"car": "AUTO"}.get(name, "DESCONOCIDO")
    def process_frame(self, frame):
        self.index += 1
        y = (30, 40, 70)[min(self.index - 1, 2)]
        return [Detection(7, 2, "car", 0.9, (40, y - 5, 60, y + 5))]


def pipeline_factory():
    return VisionPipeline(SequenceDetector(), (0, 50), (100, 50), min_history_positions=3, min_displacement_pixels=0)


def test_controller_start_and_process_real_pipeline():
    controller = TrafficAnalysisController(FakeSource(), pipeline_factory)
    info = controller.start()
    result = controller.process_next()
    assert info.source_type == "video_file"
    assert controller.state is AnalysisState.RUNNING
    assert result.frame_index == 1
    assert result.annotated_frame is not None
    assert result.active_tracks == (7,)
    assert result.vehicles_in_scene == 1


def test_controller_emits_crossing_and_real_counts():
    controller = TrafficAnalysisController(FakeSource(), pipeline_factory)
    controller.start()
    results = [controller.process_next() for _ in range(3)]
    assert results[-1].total_crossings == 1
    assert results[-1].category_counts == {"AUTO": 1}
    assert results[-1].direction_counts == {-1: 1}
    assert len(results[-1].crossing_events) == 1


def test_pause_and_resume_freeze_processing():
    controller = TrafficAnalysisController(FakeSource(), pipeline_factory)
    controller.start()
    first = controller.process_next()
    controller.pause()
    assert controller.process_next() is first
    assert controller.source.is_open()
    assert controller.source.source_info().position == 1
    controller.resume()
    assert controller.process_next().frame_index == 2


def test_reset_reopens_source_and_clears_batch():
    controller = TrafficAnalysisController(FakeSource(), pipeline_factory)
    controller.start()
    [controller.process_next() for _ in range(3)]
    assert controller.events
    first_pipeline = controller.pipeline
    info = controller.reset()
    assert info.position == 0
    assert controller.pipeline is not first_pipeline
    assert controller.events == ()
    assert controller.state is AnalysisState.RUNNING


def test_two_batches_do_not_share_tracks_or_duplicate_events():
    controller = TrafficAnalysisController(FakeSource(), pipeline_factory)
    controller.start()
    first_results = [controller.process_next() for _ in range(3)]
    assert first_results[-1].active_tracks == (7,)
    assert len(controller.events) == 1
    controller.reset()
    second_results = [controller.process_next() for _ in range(3)]
    assert second_results[0].active_tracks == (7,)
    assert len(controller.events) == 1


def test_pipeline_factory_failure_closes_source():
    source = FakeSource()
    controller = TrafficAnalysisController(source, lambda: (_ for _ in ()).throw(RuntimeError("factory failed")))
    try:
        controller.start()
    except RuntimeError as exc:
        assert str(exc) == "factory failed"
    else:
        raise AssertionError("Se esperaba el fallo de la factoría")
    assert controller.state is AnalysisState.ERROR
    assert not source.is_open()


def test_end_of_source_closes_resource():
    controller = TrafficAnalysisController(FakeSource(frame_count=1), pipeline_factory)
    controller.start(); controller.process_next()
    result = controller.process_next()
    assert result.end_of_source
    assert controller.state is AnalysisState.FINISHED
    assert not controller.source.is_open()


def test_finish_preserves_events_and_never_approves():
    controller = TrafficAnalysisController(FakeSource(), pipeline_factory)
    controller.start()
    [controller.process_next() for _ in range(3)]
    events = controller.finish()
    assert len(events) == 1
    assert controller.state is AnalysisState.FINISHED
    assert not hasattr(controller, "approve")
    assert not hasattr(controller, "tpda")


def test_finished_events_use_official_review_adapter():
    controller = TrafficAnalysisController(FakeSource(), pipeline_factory)
    controller.start()
    [controller.process_next() for _ in range(3)]
    batch = build_traffic_event_batch(controller.finish(), {
        "model_name": "mock.pt", "line_id": "test_line", "line_y": 50,
        "source_video": "fake.mp4", "processing_date": "2026-07-18T20:00:00",
        "configuration_version": "test-v1",
    })
    assert len(batch["events"]) == 1
    assert batch["events"][0]["validation_status"] == "sin_revisar"
    assert "approved" not in batch and "tpda" not in batch


def test_pipeline_exception_is_returned_as_warning_and_closes():
    controller = TrafficAnalysisController(FakeSource(fail=True), pipeline_factory)
    controller.start()
    result = controller.process_next()
    assert controller.state is AnalysisState.ERROR
    assert result.end_of_source
    assert result.warnings == ("fallo controlado",)
    assert not controller.source.is_open()


def test_controller_has_no_streamlit_or_ocr_dependency():
    source = inspect.getsource(controller_module).lower()
    assert "streamlit" not in source
    assert "paddleocr" not in source
    assert "session_state" not in source


def test_congestion_classifier_uses_only_available_metrics():
    assert classify_congestion(100, 50, 1) == "INSUFFICIENT_DATA"
    assert classify_congestion(10, 2, 10) == "NORMAL"
    assert classify_congestion(25, 2, 10) == "MODERATE"
    assert classify_congestion(10, 20, 10) == "HIGH"
