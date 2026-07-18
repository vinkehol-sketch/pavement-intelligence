"""
Fuente de video desde archivo (MP4, AVI, etc.) usando OpenCV.
"""
from __future__ import annotations
from pathlib import Path
from .base import AbstractVideoSource, FrameResult


class FileVideoSource(AbstractVideoSource):
    """
    Fuente de video desde archivo local.
    Admite MP4, AVI, MOV y otros formatos soportados por OpenCV.
    """

    def __init__(self, file_path: str | Path):
        self._path = Path(file_path)
        self._cap = None  # cv2.VideoCapture
        self._frame_number = 0

    def open(self) -> bool:
        import cv2
        if not self._path.exists():
            raise FileNotFoundError(f"Archivo de video no encontrado: {self._path}")
        self._cap = cv2.VideoCapture(str(self._path))
        self._frame_number = 0
        return self._cap.isOpened()

    def read_frame(self) -> FrameResult:
        import cv2
        if self._cap is None or not self._cap.isOpened():
            return FrameResult(frame=None, frame_number=self._frame_number,
                              timestamp_ms=0.0, success=False, source_id=self.source_id)
        ret, frame = self._cap.read()
        ts = self._cap.get(cv2.CAP_PROP_POS_MSEC)
        if ret:
            self._frame_number += 1
        return FrameResult(frame=frame if ret else None,
                          frame_number=self._frame_number,
                          timestamp_ms=ts,
                          success=ret,
                          source_id=self.source_id)

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def get_fps(self) -> float:
        import cv2
        if self._cap is None:
            return 0.0
        return self._cap.get(cv2.CAP_PROP_FPS)

    def get_resolution(self) -> tuple[int, int]:
        import cv2
        if self._cap is None:
            return (0, 0)
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h)

    @property
    def source_id(self) -> str:
        return str(self._path.name)

    @property
    def total_frames(self) -> int:
        import cv2
        if self._cap is None:
            return 0
        return int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
