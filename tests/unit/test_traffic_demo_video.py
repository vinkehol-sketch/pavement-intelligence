from __future__ import annotations

import inspect
from pathlib import Path

import cv2
import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from pavement_intelligence.vision.analysis import AnalysisState
from pavement_intelligence.ui.utils import demo_video
from pavement_intelligence.ui.utils.demo_video import (
    advance_frame,
    clamp_frame_index,
    compute_demo_metrics,
    frame_to_rgb,
    initialize_demo_playback,
    inspect_video,
    playback_progress,
    read_frame,
    reset_demo_playback,
)


ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / "data/samples/ui/assets/traffic_monitoring_demo.mp4"
MONITORING_PAGE = ROOT / "src/pavement_intelligence/ui/pages/traffic_monitoring.py"


def test_inspect_demo_video():
    info = inspect_video(VIDEO)
    assert (info.fps, info.total_frames, info.width, info.height) == (8.0, 64, 1672, 766)
    assert info.duration_seconds == 8.0
    assert info.resolution == "1672 × 766"


def test_inspect_missing_video():
    with pytest.raises(FileNotFoundError):
        inspect_video(VIDEO.with_name("missing.mp4"))


def test_inspect_corrupt_video(tmp_path):
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"not a video")
    with pytest.raises(ValueError):
        inspect_video(corrupt)


@pytest.mark.parametrize("index,expected", [(-5, 0), (0, 0), (63, 63), (99, 63)])
def test_clamp_frame_index(index, expected):
    assert clamp_frame_index(index, 64) == expected


@pytest.mark.parametrize("index", [0, 63, -1, 100])
def test_read_frame_supports_boundaries(index):
    frame = read_frame(VIDEO, index)
    assert frame.shape == (766, 1672, 3)
    assert frame.dtype == np.uint8


def test_frame_to_rgb_changes_channel_order():
    bgr = np.array([[[1, 2, 3]]], dtype=np.uint8)
    assert frame_to_rgb(bgr).tolist() == [[[3, 2, 1]]]


@pytest.mark.parametrize("value", [None, np.array([]), np.zeros((2, 2), dtype=np.uint8)])
def test_frame_to_rgb_rejects_invalid_images(value):
    with pytest.raises(ValueError):
        frame_to_rgb(value)


def test_playback_progress_is_clamped():
    assert playback_progress(-1, 64) == 0
    assert playback_progress(63, 64) == 1
    assert playback_progress(100, 64) == 1


def test_advance_frame_uses_elapsed_time():
    assert advance_frame(4, 64, 8, 10.0, 10.5) == (8, 10.5, True)


def test_advance_frame_loops_or_pauses_at_end():
    assert advance_frame(62, 64, 8, 10.0, 10.5, loop=True) == (2, 10.5, True)
    assert advance_frame(62, 64, 8, 10.0, 10.5, loop=False) == (63, 10.5, False)


def test_demo_metrics_are_deterministic_and_bounded():
    start = compute_demo_metrics(0)
    assert start == compute_demo_metrics(0)
    assert compute_demo_metrics(-2) == start
    assert compute_demo_metrics(3) == compute_demo_metrics(1)
    assert sum(start.category_counts) == sum(start.direction_counts)


def test_demo_metrics_progress_changes_counts_and_alerts():
    start = compute_demo_metrics(0)
    end = compute_demo_metrics(1)
    assert sum(end.category_counts) > sum(start.category_counts)
    assert start.alert_count == 0
    assert end.alert_count == 1


def test_initialize_uses_only_isolated_traffic_demo_keys():
    session = {"official_count": 91}
    initialize_demo_playback(session, VIDEO)
    assert session["official_count"] == 91
    assert all(key.startswith("traffic_demo_") for key in session if key != "official_count")


def test_reset_pauses_and_returns_to_first_frame():
    session = {
        "traffic_demo_playing": True,
        "traffic_demo_frame_index": 42,
        "traffic_demo_error": "error",
    }
    reset_demo_playback(session, last_update=5.0)
    assert session == {
        "traffic_demo_playing": False,
        "traffic_demo_frame_index": 0,
        "traffic_demo_error": "",
        "traffic_demo_last_update": 5.0,
    }


def test_player_utility_has_no_ai_streamlit_or_disk_write_dependencies():
    source = inspect.getsource(demo_video).lower()
    assert "streamlit" not in source
    assert "yolo" not in source
    assert "bytetrack" not in source
    assert "paddleocr" not in source
    assert "videowriter" not in source


def test_static_mode_renders_with_disabled_controls():
    app = AppTest.from_file(str(MONITORING_PAGE), default_timeout=30).run()
    assert not app.exception
    assert app.segmented_control[0].value == "Imagen demostrativa"
    controls = {button.label: button for button in app.button}
    assert {"Reproducir", "Pausar", "Reiniciar"} <= controls.keys()
    assert all(controls[label].disabled for label in ("Reproducir", "Pausar", "Reiniciar"))


def test_video_mode_renders_metadata_and_controls():
    app = AppTest.from_file(str(MONITORING_PAGE), default_timeout=30).run()
    app.segmented_control[0].set_value("Video pregrabado").run()
    assert not app.exception
    controls = {button.label: button for button in app.button}
    assert not controls["Iniciar análisis"].disabled
    assert {"Pausar", "Continuar", "Reiniciar", "Finalizar análisis"} <= controls.keys()
    assert app.session_state["traffic_analysis_controller"] is None


def test_camera_mode_renders_without_opening_device():
    app = AppTest.from_file(str(MONITORING_PAGE), default_timeout=30).run()
    app.segmented_control[0].set_value("Cámara en vivo").run()
    assert not app.exception
    controls = {button.label: button for button in app.button}
    assert not controls["Iniciar cámara"].disabled
    assert "Detener cámara" in controls
    assert app.session_state["traffic_analysis_controller"] is None


class ClosingController:
    state = AnalysisState.FINISHED
    last_result = None
    events = ()

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_changing_real_source_closes_previous_controller():
    controller = ClosingController()
    app = AppTest.from_file(str(MONITORING_PAGE), default_timeout=30)
    app.session_state["traffic_analysis_source_type"] = "Video pregrabado"
    app.session_state["traffic_analysis_active_mode"] = "Video pregrabado"
    app.session_state["traffic_analysis_controller"] = controller
    app.run()
    app.segmented_control[0].set_value("Cámara en vivo").run()
    assert not app.exception
    assert controller.closed is True
    assert app.session_state["traffic_analysis_controller"] is None
