"""Fuente secuencial de video local basada en OpenCV."""
from __future__ import annotations

from pathlib import Path

import cv2

from .base import FrameResult, FrameSource, SourceInfo


class VideoFileSource(FrameSource):
    SUPPORTED_SUFFIXES = frozenset({".mp4", ".avi", ".mov", ".mkv"})

    def __init__(self, file_path: str | Path):
        self._path = Path(file_path)
        self._cap: cv2.VideoCapture | None = None
        self._frame_number = 0

    def open(self) -> bool:
        self.close()
        if not self._path.is_file():
            raise FileNotFoundError(f"Archivo de video no encontrado: {self._path}")
        if self._path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise ValueError(f"Formato de video no admitido: {self._path.suffix or 'sin extensión'}")
        self._cap = cv2.VideoCapture(str(self._path))
        self._frame_number = 0
        if not self._cap.isOpened():
            self.close()
            raise ValueError(f"OpenCV no pudo abrir el video: {self._path}")
        return True

    def read(self) -> FrameResult:
        if not self.is_open():
            return FrameResult(None, self._frame_number, 0.0, False, self.source_id)
        assert self._cap is not None
        ok, frame = self._cap.read()
        timestamp_ms = float(self._cap.get(cv2.CAP_PROP_POS_MSEC))
        if ok:
            self._frame_number += 1
        return FrameResult(frame if ok else None, self._frame_number, timestamp_ms, bool(ok), self.source_id)

    def reset(self) -> bool:
        if not self.is_open():
            return self.open()
        assert self._cap is not None
        ok = self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._frame_number = 0
        return bool(ok)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def source_info(self) -> SourceInfo:
        if not self.is_open():
            return SourceInfo(self.source_id, "video_file", 0.0, 0, 0, 0, self._frame_number)
        assert self._cap is not None
        return SourceInfo(
            self.source_id, "video_file",
            float(self._cap.get(cv2.CAP_PROP_FPS)),
            int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            self._frame_number,
        )

    @property
    def source_id(self) -> str:
        return self._path.name

    @property
    def total_frames(self) -> int:
        return self.source_info().total_frames or 0


# Nombre histórico conservado.
FileVideoSource = VideoFileSource
