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
        return [
            (text, score)
            for text, score, _polygon, _bbox in PaddleOCRPlateReader._modern_detections(
                results
            )
        ]

    @staticmethod
    def _modern_detections(
        results: object,
    ) -> list[
        tuple[
            object,
            object,
            tuple[tuple[float, float], ...] | None,
            tuple[float, float, float, float] | None,
        ]
    ]:
        """Extrae texto, confianza y geometrÃ­a real de PaddleOCR 3.x."""
        if not isinstance(results, (list, tuple)):
            return []

        detections = []
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
                pairs = list(zip(texts, scores, strict=False))
            except TypeError:
                continue
            polygons = data.get("rec_polys", ())
            boxes = data.get("rec_boxes", ())
            for index, (text, score) in enumerate(pairs):
                polygon = PaddleOCRPlateReader._coerce_polygon(
                    PaddleOCRPlateReader._item_at(polygons, index)
                )
                bbox = PaddleOCRPlateReader._coerce_bbox(
                    PaddleOCRPlateReader._item_at(boxes, index)
                )
                detections.append((text, score, polygon, bbox))
        return detections

    @staticmethod
    def _legacy_candidates(results: object) -> list[tuple[object, object]]:
        """Extract text/score pairs from PaddleOCR 2.x nested results."""
        return [
            (text, score)
            for text, score, _polygon, _bbox in PaddleOCRPlateReader._legacy_detections(
                results
            )
        ]

    @staticmethod
    def _legacy_detections(
        results: object,
    ) -> list[
        tuple[
            object,
            object,
            tuple[tuple[float, float], ...] | None,
            tuple[float, float, float, float] | None,
        ]
    ]:
        """Extrae texto, confianza y geometrÃ­a real de PaddleOCR 2.x."""
        if (
            not isinstance(results, (list, tuple))
            or not results
            or not isinstance(results[0], (list, tuple))
            or not results[0]
        ):
            return []

        detections = []
        for line in results[0]:
            if not isinstance(line, (list, tuple)) or len(line) < 2:
                continue
            candidate = line[1]
            if isinstance(candidate, (list, tuple)) and len(candidate) >= 2:
                polygon = PaddleOCRPlateReader._coerce_polygon(line[0])
                detections.append(
                    (
                        candidate[0],
                        candidate[1],
                        polygon,
                        PaddleOCRPlateReader._bbox_from_polygon(polygon),
                    )
                )
        return detections

    @staticmethod
    def _item_at(values: object, index: int) -> object:
        try:
            return values[index]  # type: ignore[index]
        except (IndexError, KeyError, TypeError):
            return None

    @staticmethod
    def _coerce_polygon(
        value: object,
    ) -> tuple[tuple[float, float], ...] | None:
        try:
            points = []
            for point in value:  # type: ignore[union-attr]
                x, y = float(point[0]), float(point[1])
                if not math.isfinite(x) or not math.isfinite(y):
                    return None
                points.append((x, y))
        except (IndexError, TypeError, ValueError):
            return None
        return tuple(points) if len(points) >= 3 else None

    @staticmethod
    def _coerce_bbox(value: object) -> tuple[float, float, float, float] | None:
        try:
            x1, y1, x2, y2 = [float(item) for item in value]  # type: ignore[union-attr]
        except (TypeError, ValueError):
            return None
        values = (x1, y1, x2, y2)
        if not all(math.isfinite(item) for item in values) or x1 >= x2 or y1 >= y2:
            return None
        return values

    @staticmethod
    def _bbox_from_polygon(
        polygon: tuple[tuple[float, float], ...] | None,
    ) -> tuple[float, float, float, float] | None:
        if polygon is None:
            return None
        xs = [point[0] for point in polygon]
        ys = [point[1] for point in polygon]
        return min(xs), min(ys), max(xs), max(ys)

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
                detections = self._modern_detections(results)
            else:
                results = self._ocr.ocr(roi, cls=True)
                detections = self._legacy_detections(results)
        except Exception:
            return None

        best_text = ""
        best_conf = -1.0
        best_polygon = None
        best_bbox = None

        for text, conf, polygon, bbox in detections:
            normalized_text = self._normalize_text(text)
            if not normalized_text or not isinstance(conf, Real) or isinstance(conf, bool):
                continue
            numeric_conf = float(conf)
            if not math.isfinite(numeric_conf) or not 0.0 <= numeric_conf <= 1.0:
                continue
            if numeric_conf > best_conf:
                best_conf = numeric_conf
                best_text = normalized_text
                best_polygon = polygon
                best_bbox = bbox

        if best_conf < self._min_confidence or not best_text:
            return None

        plate_hash = self._hash_plate(best_text)
        translated_polygon = (
            tuple((px + x1, py + y1) for px, py in best_polygon)
            if best_polygon is not None
            else None
        )
        translated_bbox = (
            (
                best_bbox[0] + x1,
                best_bbox[1] + y1,
                best_bbox[2] + x1,
                best_bbox[3] + y1,
            )
            if best_bbox is not None
            else self._bbox_from_polygon(translated_polygon)
        )

        return PlateResult(
            text_raw=None if self._anonymize else best_text,
            text_hash=plate_hash,
            confidence=best_conf,
            bbox=translated_bbox,
            is_anonymized=self._anonymize,
            polygon=translated_polygon,
        )
