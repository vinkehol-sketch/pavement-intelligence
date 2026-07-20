from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest

from pavement_intelligence.ui.utils.uploaded_video import (
    UploadedVideoError,
    cleanup_uploaded_video,
    store_uploaded_video,
    uploaded_video_digest,
)


@dataclass
class Upload:
    name: str
    data: bytes
    type: str | None

    @property
    def size(self) -> int:
        return len(self.data)

    def getvalue(self) -> bytes:
        return self.data


def duration(_path: Path) -> float:
    return 12.5


@pytest.mark.parametrize(
    ("name", "mime"),
    (("traffic.mp4", "video/mp4"), ("traffic.avi", "video/x-msvideo")),
)
def test_accepts_supported_video_and_returns_typed_metadata(
    tmp_path: Path, name: str, mime: str
):
    handle = store_uploaded_video(
        Upload(name, b"valid-video", mime),
        temporary_parent=tmp_path,
        duration_reader=duration,
    )
    try:
        assert handle.original_name == name
        assert handle.extension == Path(name).suffix
        assert handle.duration_seconds == 12.5
        assert handle.size_bytes == 11
        assert handle.temporary_path.read_bytes() == b"valid-video"
    finally:
        cleanup_uploaded_video(handle)


def test_rejects_unsupported_extension_and_mime(tmp_path: Path):
    with pytest.raises(UploadedVideoError, match="Formato no permitido"):
        store_uploaded_video(
            Upload("payload.exe", b"content", "application/octet-stream"),
            temporary_parent=tmp_path,
            duration_reader=duration,
        )
    with pytest.raises(UploadedVideoError, match="MIME"):
        store_uploaded_video(
            Upload("traffic.mp4", b"content", "text/plain"),
            temporary_parent=tmp_path,
            duration_reader=duration,
        )


def test_rejects_empty_file(tmp_path: Path):
    with pytest.raises(UploadedVideoError, match="vacío"):
        store_uploaded_video(
            Upload("empty.mp4", b"", "video/mp4"),
            temporary_parent=tmp_path,
            duration_reader=duration,
        )


def test_rejects_oversized_file_before_reading_content(tmp_path: Path):
    class OversizedUpload:
        name = "large.mp4"
        type = "video/mp4"
        size = 101

        def getvalue(self):
            raise AssertionError("No debe leerse un archivo que ya excede el límite.")

    with pytest.raises(UploadedVideoError, match="límite"):
        store_uploaded_video(
            OversizedUpload(),
            max_size_bytes=100,
            temporary_parent=tmp_path,
            duration_reader=duration,
        )


def test_safe_name_hash_and_source_id_do_not_reuse_original_path(tmp_path: Path):
    content = b"hash-me"
    handle = store_uploaded_video(
        Upload("authorized-video.mp4", content, "video/mp4"),
        temporary_parent=tmp_path,
        duration_reader=duration,
    )
    try:
        expected = sha256(content).hexdigest()
        assert handle.sha256 == expected
        assert handle.source_id == f"uploaded-video:{expected[:16]}"
        assert handle.safe_name.startswith("video-")
        assert handle.safe_name.endswith(".mp4")
        assert "authorized-video" not in handle.safe_name
        assert handle.temporary_path.name == handle.safe_name
        assert handle.temporary_path.parent.parent == tmp_path
    finally:
        cleanup_uploaded_video(handle)


@pytest.mark.parametrize("name", ("../escape.mp4", "folder/video.mp4", "folder\\video.mp4"))
def test_rejects_client_path_and_traversal(tmp_path: Path, name: str):
    with pytest.raises(UploadedVideoError, match="ruta"):
        store_uploaded_video(
            Upload(name, b"content", "video/mp4"),
            temporary_parent=tmp_path,
            duration_reader=duration,
        )


def test_two_different_uploads_never_overwrite_each_other(tmp_path: Path):
    first = store_uploaded_video(
        Upload("first.mp4", b"first", "video/mp4"),
        temporary_parent=tmp_path,
        duration_reader=duration,
    )
    second = store_uploaded_video(
        Upload("second.mp4", b"second", "video/mp4"),
        temporary_parent=tmp_path,
        duration_reader=duration,
    )
    try:
        assert first.temporary_path != second.temporary_path
        assert first.temporary_path.read_bytes() == b"first"
        assert second.temporary_path.read_bytes() == b"second"
    finally:
        cleanup_uploaded_video(first)
        cleanup_uploaded_video(second)


def test_cleanup_is_explicit_and_idempotent(tmp_path: Path):
    handle = store_uploaded_video(
        Upload("video.mov", b"content", "video/quicktime"),
        temporary_parent=tmp_path,
        duration_reader=duration,
    )
    directory = handle.temporary_path.parent
    assert directory.is_dir()
    cleanup_uploaded_video(handle)
    cleanup_uploaded_video(handle)
    assert not directory.exists()


def test_replacement_removes_previous_temporary_directory(tmp_path: Path):
    previous = store_uploaded_video(
        Upload("first.mkv", b"first", "video/x-matroska"),
        temporary_parent=tmp_path,
        duration_reader=duration,
    )
    old_directory = previous.temporary_path.parent
    replacement = store_uploaded_video(
        Upload("second.mkv", b"second", "video/x-matroska"),
        previous=previous,
        temporary_parent=tmp_path,
        duration_reader=duration,
    )
    try:
        assert not old_directory.exists()
        assert replacement.is_available
    finally:
        cleanup_uploaded_video(replacement)


def test_same_content_reuses_live_handle_without_duplicate(tmp_path: Path):
    first = store_uploaded_video(
        Upload("first.mp4", b"same", "video/mp4"),
        temporary_parent=tmp_path,
        duration_reader=duration,
    )
    duplicate = store_uploaded_video(
        Upload("renamed.mp4", b"same", "video/mp4"),
        previous=first,
        temporary_parent=tmp_path,
        duration_reader=duration,
    )
    try:
        assert duplicate is first
        assert len(list(tmp_path.iterdir())) == 1
    finally:
        cleanup_uploaded_video(first)


def test_corrupt_video_is_removed_and_previous_handle_is_cleaned(tmp_path: Path):
    previous = store_uploaded_video(
        Upload("first.mp4", b"first", "video/mp4"),
        temporary_parent=tmp_path,
        duration_reader=duration,
    )
    old_directory = previous.temporary_path.parent
    with pytest.raises(UploadedVideoError, match="OpenCV"):
        store_uploaded_video(
            Upload("corrupt.mp4", b"corrupt", "video/mp4"),
            previous=previous,
            temporary_parent=tmp_path,
            duration_reader=lambda _path: None,
        )
    assert not old_directory.exists()
    assert list(tmp_path.iterdir()) == []


def test_digest_is_stable_and_does_not_write(tmp_path: Path):
    upload = Upload("video.mp4", b"stable", "application/octet-stream")
    first = uploaded_video_digest(upload)
    second = uploaded_video_digest(upload)
    assert first == second == sha256(b"stable").hexdigest()
    assert list(tmp_path.iterdir()) == []
