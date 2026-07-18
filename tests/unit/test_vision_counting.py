"""Pruebas unitarias para el módulo de conteo por visión."""
import pytest
import json
import csv
from io import StringIO
from pathlib import Path
import pandas as pd
import numpy as np

from pavement_intelligence.vision.counting.virtual_line import VirtualLineCounter, Point
from pavement_intelligence.vision.detection.base import Detection
from pavement_intelligence.vision.pipeline import TrafficEvent, VisionPipeline, export_corrected_records


def legacy_counter(p1, p2, **kwargs):
    """Conserva en pruebas geométricas el mínimo histórico previo de dos puntos."""
    kwargs.setdefault("min_history_positions", 2)
    kwargs.setdefault("min_displacement_pixels", 0.0)
    return VirtualLineCounter(p1, p2, **kwargs)


class SequenceDetector:
    def __init__(self, frames):
        self.frames = iter(frames)

    def process_frame(self, frame):
        return next(self.frames, [])

    def map_class_to_category(self, class_name):
        return {"car": "AUTO", "bus": "BUS", "motorcycle": "MOTO", "truck": "CAMION"}.get(class_name, "DESCONOCIDO")


def detection(track_id, y, class_name="car", confidence=0.8):
    return Detection(track_id, 2, class_name, confidence, (40.0, y - 5.0, 60.0, y + 5.0))


def blank_frame():
    return np.zeros((200, 200, 3), dtype=np.uint8)

def test_horizontal_line_cross():
    counter = legacy_counter(Point(0, 100), Point(200, 100))
    # Cruce de arriba hacia abajo (y=50 a y=150)
    res1 = counter.process_point(1, Point(100, 50))
    assert res1 is None
    res2 = counter.process_point(1, Point(100, 150))
    assert res2 == -1

def test_vertical_line_cross():
    counter = legacy_counter(Point(100, 0), Point(100, 200))
    # Cruce de izquierda a derecha (x=50 a x=150)
    res1 = counter.process_point(1, Point(50, 100))
    assert res1 is None
    res2 = counter.process_point(1, Point(150, 100))
    assert res2 == 1

def test_inclined_line_cross():
    counter = legacy_counter(Point(0, 0), Point(100, 100))
    # Punto por encima de la diagonal vs por debajo
    counter.process_point(1, Point(10, 50)) # Lado 1
    res = counter.process_point(1, Point(50, 10)) # Lado -1
    assert res == 1

def test_cross_both_directions():
    counter = legacy_counter(Point(0, 100), Point(200, 100))
    # ID 1 baja
    counter.process_point(1, Point(100, 50))
    assert counter.process_point(1, Point(100, 150)) == -1
    # ID 2 sube
    counter.process_point(2, Point(100, 150))
    assert counter.process_point(2, Point(100, 50)) == 1

def test_touch_and_return_no_cross():
    counter = legacy_counter(Point(0, 100), Point(200, 100))
    counter.process_point(1, Point(100, 50))
    assert counter.process_point(1, Point(100, 99)) is None
    assert counter.process_point(1, Point(100, 50)) is None

def test_multiple_detections_same_id():
    counter = legacy_counter(Point(0, 100), Point(200, 100))
    counter.process_point(1, Point(100, 50))
    assert counter.process_point(1, Point(100, 150)) == -1
    # Ya cruzó, no debería contar de nuevo
    assert counter.process_point(1, Point(100, 160)) is None
    assert counter.process_point(1, Point(100, 170)) is None

def test_oscillation_near_line():
    counter = legacy_counter(Point(0, 100), Point(200, 100))
    counter.process_point(1, Point(100, 90))
    assert counter.process_point(1, Point(100, 110)) == -1
    # Vuelve a cruzar hacia arriba (oscila)
    assert counter.process_point(1, Point(100, 90)) is None
    # Y de nuevo abajo
    assert counter.process_point(1, Point(100, 110)) is None

def test_event_serialization():
    event = TrafficEvent(
        event_id="test_1",
        track_id=1,
        original_class="car",
        category="AUTO",
        confidence=0.9,
        frame_number=10,
        video_second=0.33,
        direction=1,
        centroid_x=100.5,
        centroid_y=150.0,
        source="test.mp4",
        processing_date="2026-07-15T12:00:00"
    )
    
    data = event.to_dict()
    assert data["category"] == "AUTO"
    assert data["direction"] == 1
    
    # Probar que pandas lo puede volver CSV y JSON
    df = pd.DataFrame([data])
    csv_str = df.to_csv(index=False)
    assert "AUTO" in csv_str
    assert "test_1" in csv_str
    
    json_str = json.dumps([data])
    assert '"category": "AUTO"' in json_str


def test_missing_frames_still_count_when_track_reappears():
    counter = legacy_counter(Point(0, 100), Point(200, 100), tolerance=4.0)
    assert counter.process_point(7, Point(100, 50), frame_number=1) is None
    assert counter.process_point(7, Point(100, 150), frame_number=10) == -1


def test_inclined_line_with_deadband():
    counter = legacy_counter(Point(0, 0), Point(100, 100), tolerance=6.0)
    assert counter.process_point(11, Point(40, 35), frame_number=1) is None
    assert counter.process_point(11, Point(40, 45), frame_number=2) is None
    assert counter.process_point(11, Point(60, 20), frame_number=3) == 1


def test_oscillation_around_line_does_not_double_count():
    counter = legacy_counter(Point(0, 100), Point(200, 100), tolerance=3.0, cooldown_frames=5)
    assert counter.process_point(1, Point(100, 90), frame_number=1) is None
    assert counter.process_point(1, Point(100, 110), frame_number=2) == -1
    assert counter.process_point(1, Point(100, 90), frame_number=3) is None
    assert counter.process_point(1, Point(100, 110), frame_number=4) is None


def test_track_history_and_average_confidence():
    counter = legacy_counter(Point(0, 100), Point(200, 100), tolerance=2.0)
    counter.process_point(3, Point(100, 80), frame_number=1, confidence=0.78, class_name="car")
    counter.process_point(3, Point(100, 120), frame_number=2, confidence=0.92, class_name="truck")
    history = counter.get_track_history(3)
    assert len(history) == 2
    assert history[-1]["class_name"] == "truck"
    assert history[-1]["confidence"] == pytest.approx(0.92)


def test_cleanup_removes_stale_tracks_after_age_limit():
    counter = legacy_counter(Point(0, 100), Point(200, 100), max_state_age_frames=3)
    counter.process_point(99, Point(100, 80), frame_number=1)
    counter.cleanup_tracks([99], current_frame=5)
    assert 99 not in counter.previous_states


def test_export_corrected_records_creates_summary_files(tmp_path):
    records = [
        {
            "event_id": "evt_1",
            "track_id": 1,
            "category": "AUTO",
            "direction": 1,
            "source": "video.mp4",
            "status": "AUTOMATICO",
            "notes": "",
        },
        {
            "event_id": "evt_2",
            "track_id": 2,
            "category": "CAMION",
            "direction": -1,
            "source": "video.mp4",
            "status": "CORREGIDO_MANUALMENTE",
            "notes": "clasificación ajustada",
        },
    ]
    output_dir = tmp_path / "reports"
    export_corrected_records(records, output_dir)
    assert (output_dir / "corrected_events.csv").exists()
    assert (output_dir / "corrected_events.json").exists()
    assert (output_dir / "corrected_summary.csv").exists()


def test_track_id_minus_one_never_generates_event():
    detector = SequenceDetector([[detection(-1, 80)], [detection(-1, 90)], [detection(-1, 120)]])
    pipeline = VisionPipeline(detector, (0, 100), (200, 100))
    for frame_number in range(1, 4):
        pipeline.process_frame(blank_frame(), frame_number, 10.0, "test.mp4")
    assert pipeline.events == []
    assert pipeline.counter.track_states == {}
    assert pipeline.get_diagnostics_summary()["invalid_track_id_detections"] == 3


def test_track_id_none_never_generates_event():
    detector = SequenceDetector([[detection(None, 80)], [detection(None, 90)], [detection(None, 120)]])
    pipeline = VisionPipeline(detector, (0, 100), (200, 100))
    for frame_number in range(1, 4):
        pipeline.process_frame(blank_frame(), frame_number, 10.0, "test.mp4")
    assert pipeline.events == []
    assert pipeline.counter.track_states == {}


def test_valid_track_with_insufficient_history_does_not_cross():
    counter = VirtualLineCounter(Point(0, 100), Point(200, 100), min_history_positions=3)
    assert counter.process_point(5, Point(100, 80), frame_number=1) is None
    assert counter.process_point(5, Point(100, 120), frame_number=2) is None
    assert counter.metrics["events_blocked_insufficient_history"] == 1


def test_valid_track_with_sufficient_history_crosses():
    counter = VirtualLineCounter(Point(0, 100), Point(200, 100), min_history_positions=3)
    assert counter.process_point(5, Point(100, 70), frame_number=1) is None
    assert counter.process_point(5, Point(100, 85), frame_number=2) is None
    assert counter.process_point(5, Point(100, 120), frame_number=3) == -1


def test_car_bus_oscillation_keeps_stable_event_category():
    detector = SequenceDetector([
        [detection(8, 70, "car", 0.70)],
        [detection(8, 85, "bus", 0.95)],
        [detection(8, 120, "car", 0.75)],
    ])
    pipeline = VisionPipeline(detector, (0, 100), (200, 100))
    for frame_number in range(1, 4):
        pipeline.process_frame(blank_frame(), frame_number, 10.0, "test.mp4")
    assert len(pipeline.events) == 1
    assert pipeline.events[0].original_class == "car"
    assert pipeline.events[0].category == "AUTO"


def test_id_cannot_be_counted_twice_by_oscillation():
    counter = VirtualLineCounter(Point(0, 100), Point(200, 100), min_history_positions=3)
    counter.process_point(9, Point(100, 70), frame_number=1)
    counter.process_point(9, Point(100, 85), frame_number=2)
    assert counter.process_point(9, Point(100, 120), frame_number=3) == -1
    assert counter.process_point(9, Point(100, 80), frame_number=4) is None
    assert counter.process_point(9, Point(100, 120), frame_number=5) is None
    assert counter.metrics["events_emitted"] == 1
    assert counter.metrics["events_blocked_duplicate"] >= 1


def test_short_loss_and_recovery_does_not_duplicate_event():
    counter = VirtualLineCounter(Point(0, 100), Point(200, 100), min_history_positions=3, max_state_age_frames=30)
    counter.process_point(12, Point(100, 70), frame_number=1)
    counter.process_point(12, Point(100, 85), frame_number=2)
    assert counter.process_point(12, Point(100, 120), frame_number=3) == -1
    counter.cleanup_tracks([], current_frame=10)
    assert 12 in counter.counted_tracks
    assert counter.process_point(12, Point(100, 80), frame_number=11) is None
    assert counter.metrics["events_emitted"] == 1


def test_untracked_detections_do_not_contaminate_valid_history():
    detector = SequenceDetector([
        [detection(-1, 120), detection(15, 70)],
        [detection(None, 60), detection(15, 85)],
        [detection(-1, 130), detection(15, 120)],
    ])
    pipeline = VisionPipeline(detector, (0, 100), (200, 100))
    for frame_number in range(1, 4):
        pipeline.process_frame(blank_frame(), frame_number, 10.0, "test.mp4")
    assert set(pipeline.counter.track_states) == {15}
    assert len(pipeline.counter.get_track_history(15)) == 3
    assert len(pipeline.events) == 1
    assert pipeline.events[0].track_id == 15
