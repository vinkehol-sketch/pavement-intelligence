"""
Lector de placas usando PaddleOCR.
Privacy-by-design: el texto crudo se hashea antes de cualquier almacenamiento.
"""
from __future__ import annotations
import hashlib
from typing import Optional
import numpy as np

from .base import AbstractPlateReader, PlateResult


class PaddleOCRPlateReader(AbstractPlateReader):
    """
    Lector de placas usando PaddleOCR para la región del vehículo.
    IMPORTANTE: La placa cruda nunca se almacena; solo el hash truncado.
    """

    def __init__(
        self,
        min_confidence: float = 0.60,
        hash_length: int = 8,
        anonymize: bool = True,
        lang: str = "es",
    ):
        self._min_confidence = min_confidence
        self._hash_length = hash_length
        self._anonymize = anonymize
        self._lang = lang
        self._ocr = None

    def _load_model(self) -> None:
        from paddleocr import PaddleOCR
        self._ocr = PaddleOCR(use_angle_cls=True, lang=self._lang, show_log=False)

    def _hash_plate(self, text: str) -> str:
        """Genera un hash SHA-256 truncado de la placa."""
        return hashlib.sha256(text.upper().strip().encode()).hexdigest()[:self._hash_length]

    def detect_and_read(
        self,
        frame: np.ndarray,
        vehicle_bbox: tuple[float, float, float, float],
    ) -> Optional[PlateResult]:
        """
        Detecta y lee la placa en la región del vehículo.
        La región se obtiene del bounding box del vehículo.
        """
        if self._ocr is None:
            self._load_model()

        x1, y1, x2, y2 = [int(v) for v in vehicle_bbox]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame.shape[1], x2)
        y2 = min(frame.shape[0], y2)

        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return None

        try:
            results = self._ocr.ocr(roi, cls=True)
        except Exception:
            return None

        if not results or not results[0]:
            return None

        best_text = ""
        best_conf = 0.0

        for line in results[0]:
            if line and len(line) >= 2:
                text, conf = line[1]
                if conf > best_conf:
                    best_conf = float(conf)
                    best_text = str(text)

        if best_conf < self._min_confidence or not best_text:
            return None

        plate_hash = self._hash_plate(best_text)

        return PlateResult(
            text_raw=None if self._anonymize else best_text,
            text_hash=plate_hash,
            confidence=best_conf,
            bbox=None,  # bbox dentro del ROI
            is_anonymized=self._anonymize,
        )
