"""Fuente para una cámara local por índice de dispositivo."""
from __future__ import annotations

import cv2

from .base import FrameResult, FrameSource, SourceInfo


class CameraSource(FrameSource):
    def __init__(self, camera_index: int = 0):
        if isinstance(camera_index, bool) or not isinstance(camera_index, int) or not 0 <= camera_index <= 9:
            raise ValueError("El índice de cámara debe ser un entero entre 0 y 9.")
        self.camera_index = camera_index
        self._cap: cv2.VideoCapture | None = None
        self._frame_number = 0

    def open(self) -> bool:
        self.close()
        self._cap = cv2.VideoCapture(self.camera_index)
        self._frame_number = 0
        if not self._cap.isOpened():
            self.close()
            raise RuntimeError(f"La cámara local {self.camera_index} no está disponible.")
        return True

    def read(self) -> FrameResult:
        if not self.is_open():
            return FrameResult(None, self._frame_number, 0.0, False, self.source_id)
        assert self._cap is not None
        ok, frame = self._cap.read()
        if ok:
            self._frame_number += 1
        fps = self.get_fps()
        timestamp_ms = self._frame_number / fps * 1000 if fps > 0 else 0.0
        return FrameResult(frame if ok else None, self._frame_number, timestamp_ms, bool(ok), self.source_id)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def source_info(self) -> SourceInfo:
        if not self.is_open():
            return SourceInfo(self.source_id, "camera", 0.0, 0, 0, None, self._frame_number)
        assert self._cap is not None
        return SourceInfo(
            self.source_id, "camera",
            float(self._cap.get(cv2.CAP_PROP_FPS)),
            int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            None,
            self._frame_number,
        )

    @property
    def source_id(self) -> str:
        return f"camera:{self.camera_index}"
