"""Contratos neutrales para fuentes secuenciales de fotogramas."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class SourceInfo:
    source_id: str
    source_type: str
    fps: float
    width: int
    height: int
    total_frames: int | None
    position: int


@dataclass
class FrameResult:
    """Resultado neutral de una lectura; el frame usa BGR de OpenCV."""
    frame: Optional[np.ndarray]
    frame_number: int
    timestamp_ms: float
    success: bool
    source_id: str


class FrameSource(ABC):
    """Fuente local de frames, independiente de Streamlit y del pipeline."""

    @abstractmethod
    def open(self) -> bool: ...

    @abstractmethod
    def read(self) -> FrameResult: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def is_open(self) -> bool: ...

    @abstractmethod
    def source_info(self) -> SourceInfo: ...

    def read_frame(self) -> FrameResult:
        return self.read()

    def release(self) -> None:
        self.close()

    def get_fps(self) -> float:
        return self.source_info().fps

    def get_resolution(self) -> tuple[int, int]:
        info = self.source_info()
        return info.width, info.height

    @property
    @abstractmethod
    def source_id(self) -> str: ...

    def __enter__(self):
        if not self.open():
            raise RuntimeError(f"No se pudo abrir la fuente: {self.source_id}")
        return self

    def __exit__(self, *args):
        self.close()


# Nombre histórico conservado para no romper importaciones existentes.
AbstractVideoSource = FrameSource
