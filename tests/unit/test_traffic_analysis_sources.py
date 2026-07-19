from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pavement_intelligence.vision.capture import CameraSource, VideoFileSource


ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / "data/samples/ui/assets/traffic_monitoring_demo.mp4"


def test_video_file_source_metadata_and_first_frame():
    source = VideoFileSource(VIDEO)
    assert source.open()
    info = source.source_info()
    assert (info.source_type, info.fps, info.total_frames) == ("video_file", 8.0, 64)
    assert (info.width, info.height) == (1672, 766)
    result = source.read()
    assert result.success and result.frame_number == 1
    source.close()
    assert not source.is_open()


def test_video_file_source_reads_last_frame_and_end():
    source = VideoFileSource(VIDEO)
    source.open()
    results = [source.read() for _ in range(65)]
    assert results[63].success and results[63].frame_number == 64
    assert not results[64].success and results[64].frame is None
    source.close()


def test_video_file_source_reset():
    source = VideoFileSource(VIDEO)
    source.open()
    source.read(); source.read()
    assert source.reset()
    assert source.read().frame_number == 1
    source.close()


def test_video_file_source_missing_and_corrupt(tmp_path):
    with pytest.raises(FileNotFoundError):
        VideoFileSource(tmp_path / "missing.mp4").open()
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"invalid")
    with pytest.raises(ValueError):
        VideoFileSource(corrupt).open()


def test_video_file_source_rejects_extension(tmp_path):
    path = tmp_path / "video.exe"
    path.write_bytes(b"invalid")
    with pytest.raises(ValueError, match="Formato"):
        VideoFileSource(path).open()


class FakeCapture:
    def __init__(self, index, *, opened=True):
        self.index = index
        self.opened = opened
        self.released = False
        self.release_calls = 0

    def isOpened(self): return self.opened and not self.released
    def read(self): return True, np.zeros((12, 16, 3), dtype=np.uint8)
    def get(self, prop): return {5: 10.0, 3: 16.0, 4: 12.0}.get(prop, 0.0)
    def release(self): self.released = True; self.release_calls += 1


def test_camera_source_reads_and_closes(monkeypatch):
    capture = FakeCapture(1)
    monkeypatch.setattr("cv2.VideoCapture", lambda index: capture)
    source = CameraSource(1)
    assert source.open()
    result = source.read()
    assert result.success and result.frame_number == 1
    assert source.source_info().source_type == "camera"
    source.close()
    source.close()
    assert capture.released and capture.release_calls == 1 and not source.is_open()


def test_camera_unavailable_is_controlled(monkeypatch):
    capture = FakeCapture(0, opened=False)
    monkeypatch.setattr("cv2.VideoCapture", lambda index: capture)
    with pytest.raises(RuntimeError, match="no está disponible"):
        CameraSource(0).open()
    assert capture.released and capture.release_calls == 1


def test_video_close_is_idempotent():
    source = VideoFileSource(VIDEO)
    source.open()
    source.close()
    source.close()
    assert not source.is_open()


@pytest.mark.parametrize("index", [-1, 10, True, "0"])
def test_camera_index_is_limited(index):
    with pytest.raises(ValueError):
        CameraSource(index)
