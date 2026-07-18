"""
Interfaz abstracta para fuentes de video e imagen.
Permite intercambiar entre archivo, cámara en vivo o stream RTSP.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class FrameResult:
    """Resultado de la lectura de un frame."""
    frame: Optional[np.ndarray]   # imagen BGR (OpenCV)
    frame_number: int
    timestamp_ms: float           # milisegundos desde inicio
    success: bool
    source_id: str


class AbstractVideoSource(ABC):
    """
    Contrato para fuentes de video o imagen.
    Implementaciones: FileVideoSource, CameraSource, RTSPSource.
    """

    @abstractmethod
    def open(self) -> bool:
        """Abre la fuente. Retorna True si exitoso."""
        ...

    @abstractmethod
    def read_frame(self) -> FrameResult:
        """Lee el siguiente frame de la fuente."""
        ...

    @abstractmethod
    def release(self) -> None:
        """Libera recursos de la fuente."""
        ...

    @abstractmethod
    def get_fps(self) -> float:
        """Retorna los fotogramas por segundo de la fuente."""
        ...

    @abstractmethod
    def get_resolution(self) -> tuple[int, int]:
        """Retorna (ancho, alto) en píxeles."""
        ...

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Identificador único de la fuente."""
        ...

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.release()
