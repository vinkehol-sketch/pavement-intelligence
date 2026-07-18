"""
Adaptador ByteTrack integrado en Ultralytics para seguimiento de vehículos.
ByteTrack resuelve oclusiones parciales y mantiene IDs consistentes.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import numpy as np

from .base import AbstractTracker
from ..detection.base import Detection, DetectionResult


class ByteTrackAdapter(AbstractTracker):
    """
    Adaptador para el tracker ByteTrack integrado en YOLOv8 (Ultralytics).
    Usa el archivo de configuración bytetrack.yaml de Ultralytics.
    """

    def __init__(self, tracker_config: str = "bytetrack.yaml"):
        self._tracker_config = tracker_config
        self._model = None  # Se reutiliza el modelo YOLO con tracking
        self._track_history: dict[int, list] = {}  # historial de posiciones por track_id

    def set_model(self, yolo_model) -> None:
        """Vincula el modelo YOLO al tracker."""
        self._model = yolo_model

    def update(self, detection_result: DetectionResult, frame: np.ndarray) -> list[Detection]:
        """
        Nota: Cuando se usa YOLOv8 con tracker integrado, el tracking
        se ejecuta directamente en model.track(). Este adaptador se usa
        para post-procesar y normalizar los resultados.
        """
        # La implementación completa se realiza en Fase 1
        # Ver: vision/services/video_processor.py
        return detection_result.detections

    def reset(self) -> None:
        self._track_history.clear()
