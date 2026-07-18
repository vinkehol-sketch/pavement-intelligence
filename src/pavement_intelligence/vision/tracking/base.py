"""
Interfaz abstracta para trackers de vehículos.
"""
from abc import ABC, abstractmethod
from ..detection.base import Detection, DetectionResult
import numpy as np


class AbstractTracker(ABC):
    """Contrato para trackers. Implementaciones: ByteTrackAdapter."""

    @abstractmethod
    def update(self, detection_result: DetectionResult, frame: np.ndarray) -> list[Detection]:
        """
        Actualiza el tracker con las detecciones del frame actual.
        Retorna detecciones CON track_id asignado.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reinicia el tracker (nueva sesión de procesamiento)."""
        ...
