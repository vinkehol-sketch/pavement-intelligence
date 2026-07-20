from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from pavement_intelligence.ui.utils.video_catalog import (
    SUPPORTED_VIDEO_SUFFIXES,
    discover_local_videos,
    inspect_video_duration,
    resolve_video_path,
    stable_video_source_id,
)


DEMO_RELATIVE = "data/samples/ui/assets/traffic_monitoring_demo.mp4"
COMPLEX_RELATIVE = "data/videos/samples/complex_traffic.mp4"


@pytest.fixture
def catalog_root(tmp_path: Path) -> Path:
    for relative in (
        DEMO_RELATIVE,
        COMPLEX_RELATIVE,
        "data/videos/car-detection.MP4",
        "data/videos/clip.avi",
        "data/videos/clip.mov",
        "data/videos/clip.mkv",
        "data/videos/ignore.txt",
        "data/videos/ignore.webm",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"local-test")
    return tmp_path


def fake_duration(path: Path) -> float:
    return 53.916 if path.name == "complex_traffic.mp4" else 8.0


def test_discovers_complex_and_built_in_demo(catalog_root: Path):
    videos = discover_local_videos(
        catalog_root,
        built_in_video=DEMO_RELATIVE,
        duration_reader=fake_duration,
    )
    by_path = {video.relative_path: video for video in videos}
    assert COMPLEX_RELATIVE in by_path
    assert DEMO_RELATIVE in by_path
    assert by_path[DEMO_RELATIVE].built_in
    assert by_path[COMPLEX_RELATIVE].duration_seconds == pytest.approx(53.916)


def test_only_supported_extensions_are_discovered(catalog_root: Path):
    videos = discover_local_videos(
        catalog_root,
        built_in_video=DEMO_RELATIVE,
        duration_reader=fake_duration,
    )
    suffixes = {Path(video.relative_path).suffix.lower() for video in videos}
    assert suffixes <= SUPPORTED_VIDEO_SUFFIXES
    assert "data/videos/ignore.txt" not in {item.relative_path for item in videos}
    assert "data/videos/ignore.webm" not in {item.relative_path for item in videos}


def test_order_is_deterministic_built_in_first_and_has_no_duplicates(
    catalog_root: Path,
):
    first = discover_local_videos(
        catalog_root,
        built_in_video=DEMO_RELATIVE,
        duration_reader=fake_duration,
    )
    second = discover_local_videos(
        catalog_root,
        built_in_video=DEMO_RELATIVE,
        duration_reader=fake_duration,
    )
    paths = [item.relative_path for item in first]
    assert first == second
    assert paths[0] == DEMO_RELATIVE
    assert len(paths) == len(set(paths))
    assert paths[1:] == sorted(paths[1:], key=str.casefold)


@pytest.mark.parametrize(
    "selection",
    ("../outside.mp4", "data/videos/../../outside.mp4"),
)
def test_rejects_traversal(catalog_root: Path, selection: str):
    outside = catalog_root.parent / "outside.mp4"
    outside.write_bytes(b"outside")
    with pytest.raises(ValueError, match="traversal"):
        resolve_video_path(catalog_root, selection, built_in_video=DEMO_RELATIVE)


def test_rejects_external_absolute_path(catalog_root: Path, tmp_path: Path):
    outside = tmp_path.parent / "external.mp4"
    outside.write_bytes(b"outside")
    with pytest.raises(ValueError, match="relativa"):
        resolve_video_path(catalog_root, outside, built_in_video=DEMO_RELATIVE)


def test_rejects_project_file_outside_dynamic_roots_and_exact_built_in(
    catalog_root: Path,
):
    untrusted = catalog_root / "data/samples/ui/assets/other.mp4"
    untrusted.write_bytes(b"untrusted")
    with pytest.raises(ValueError, match="raíces permitidas"):
        resolve_video_path(
            catalog_root,
            untrusted.relative_to(catalog_root),
            built_in_video=DEMO_RELATIVE,
        )
    assert resolve_video_path(
        catalog_root, DEMO_RELATIVE, built_in_video=DEMO_RELATIVE
    ).name == "traffic_monitoring_demo.mp4"


def test_does_not_follow_resolved_target_outside_data_videos(
    catalog_root: Path, monkeypatch
):
    outside = catalog_root.parent / "linked-external.mp4"
    outside.write_bytes(b"outside")
    link = catalog_root / "data/videos/samples/external-link.mp4"
    link.write_bytes(b"simulated-link")
    original_resolve = Path.resolve

    def controlled_resolve(path, *args, **kwargs):
        if path == link:
            return outside
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", controlled_resolve)
    videos = discover_local_videos(
        catalog_root,
        built_in_video=DEMO_RELATIVE,
        duration_reader=fake_duration,
    )
    assert "data/videos/samples/external-link.mp4" not in {
        item.relative_path for item in videos
    }


def test_unavailable_duration_does_not_block_catalog(catalog_root: Path):
    def unavailable(_path: Path) -> float:
        raise ValueError("sin metadatos")

    videos = discover_local_videos(
        catalog_root,
        built_in_video=DEMO_RELATIVE,
        duration_reader=unavailable,
    )
    assert videos and all(item.duration_seconds is None for item in videos)


def test_duration_reader_releases_capture():
    class Capture:
        released = False

        def isOpened(self):
            return True

        def get(self, property_id):
            return 12.0 if property_id == cv2.CAP_PROP_FPS else 648

        def release(self):
            self.released = True

    capture = Capture()
    duration = inspect_video_duration(
        "controlled.mp4", capture_factory=lambda _path: capture
    )
    assert duration == 54.0
    assert capture.released


def test_stable_source_id_depends_only_on_safe_relative_path():
    first = stable_video_source_id(COMPLEX_RELATIVE)
    second = stable_video_source_id(COMPLEX_RELATIVE)
    other = stable_video_source_id(DEMO_RELATIVE)
    assert first == second
    assert first.startswith("local-video:")
    assert first != other
    assert "data/" not in first
