"""
Lector de placas usando PaddleOCR.
Privacy-by-design: el texto crudo se hashea antes de cualquier almacenamiento.
"""
from __future__ import annotations
import hashlib
import math
import re
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from numbers import Real
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
        self._paddleocr_major = 2

    def _load_model(self) -> None:
        from paddleocr import PaddleOCR

        try:
            self._paddleocr_major = int(version("paddleocr").split(".", maxsplit=1)[0])
        except (PackageNotFoundError, ValueError):
            self._paddleocr_major = 2

        if self._paddleocr_major >= 3:
            self._ocr = PaddleOCR(
                lang=self._lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
            )
        else:
            self._ocr = PaddleOCR(use_angle_cls=True, lang=self._lang, show_log=False)

    @staticmethod
    def _modern_candidates(results: object) -> list[tuple[object, object]]:
        """Extract text/score pairs from PaddleOCR 3.x result objects."""
        if not isinstance(results, (list, tuple)):
            return []

        candidates: list[tuple[object, object]] = []
        for item in results:
            payload = getattr(item, "json", item)
            if callable(payload):
                payload = payload()
            if not isinstance(payload, Mapping):
                continue
            data = payload.get("res", payload)
            if not isinstance(data, Mapping):
                continue
            texts = data.get("rec_texts", ())
            scores = data.get("rec_scores", ())
            try:
                candidates.extend(zip(texts, scores, strict=False))
            except TypeError:
                continue
        return candidates

    @staticmethod
    def _legacy_candidates(results: object) -> list[tuple[object, object]]:
        """Extract text/score pairs from PaddleOCR 2.x nested results."""
        if (
            not isinstance(results, (list, tuple))
            or not results
            or not isinstance(results[0], (list, tuple))
            or not results[0]
        ):
            return []

        candidates: list[tuple[object, object]] = []
        for line in results[0]:
            if not isinstance(line, (list, tuple)) or len(line) < 2:
                continue
            candidate = line[1]
            if isinstance(candidate, (list, tuple)) and len(candidate) >= 2:
                candidates.append((candidate[0], candidate[1]))
        return candidates

    def _hash_plate(self, text: str) -> str:
        """Genera un hash SHA-256 truncado de la placa."""
        normalized = self._normalize_text(text)
        return hashlib.sha256(normalized.encode()).hexdigest()[:self._hash_length]

    @staticmethod
    def _normalize_text(text: object) -> str:
        """Normaliza a mayúsculas ASCII alfanuméricas para comparar y hashear."""
        if not isinstance(text, str):
            return ""
        return re.sub(r"[^A-Z0-9]", "", text.upper())

    def detect_and_read(
        self,
        frame: np.ndarray,
        vehicle_bbox: tuple[float, float, float, float],
    ) -> Optional[PlateResult]:
        """
        Detecta y lee la placa en la región del vehículo.
        La región se obtiene del bounding box del vehículo.
        """
        if not isinstance(frame, np.ndarray) or frame.ndim < 2 or frame.size == 0:
            return None

        try:
            x1, y1, x2, y2 = [int(v) for v in vehicle_bbox]
        except (TypeError, ValueError):
            return None
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame.shape[1], x2)
        y2 = min(frame.shape[0], y2)

        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return None

        if self._ocr is None:
            try:
                self._load_model()
            except Exception:
                return None

        try:
            if self._paddleocr_major >= 3:
                results = self._ocr.predict(
                    roi,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )
                candidates = self._modern_candidates(results)
            else:
                results = self._ocr.ocr(roi, cls=True)
                candidates = self._legacy_candidates(results)
        except Exception:
            return None

        best_text = ""
        best_conf = -1.0

        for text, conf in candidates:
            normalized_text = self._normalize_text(text)
            if not normalized_text or not isinstance(conf, Real) or isinstance(conf, bool):
                continue
            numeric_conf = float(conf)
            if not math.isfinite(numeric_conf) or not 0.0 <= numeric_conf <= 1.0:
                continue
            if numeric_conf > best_conf:
                best_conf = numeric_conf
                best_text = normalized_text

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
