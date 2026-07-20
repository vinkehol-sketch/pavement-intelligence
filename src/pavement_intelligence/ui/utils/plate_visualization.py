"""Anotaciones efímeras y respetuosas de privacidad para el visor OCR."""

from __future__ import annotations

import cv2
import numpy as np

from pavement_intelligence.ui.utils.plate_session import mask_plate_text
from pavement_intelligence.vision.analysis.ocr_models import PlateFrameDetection


def annotate_plate_frame(
    frame: np.ndarray,
    detections: tuple[PlateFrameDetection, ...],
    *,
    protect_plate: bool = True,
) -> np.ndarray:
    """Dibuja solamente geometría entregada por OCR y no modifica el original."""
    annotated = frame.copy()
    height, width = annotated.shape[:2]
    for detection in detections:
        polygon = _visible_polygon(detection, width=width, height=height)
        if polygon is None:
            continue

        if protect_plate:
            cv2.fillPoly(annotated, [polygon], color=(24, 24, 24))
        cv2.polylines(
            annotated,
            [polygon],
            isClosed=True,
            color=(50, 205, 50),
            thickness=2,
            lineType=cv2.LINE_AA,
        )

        shown_text = (
            mask_plate_text(detection.normalized_text)
            if protect_plate
            else detection.normalized_text
        )
        label = f"{shown_text} {detection.confidence:.0%}"
        anchor_x = int(polygon[:, 0].min())
        anchor_y = max(18, int(polygon[:, 1].min()) - 7)
        cv2.putText(
            annotated,
            label,
            (anchor_x, anchor_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (50, 205, 50),
            2,
            cv2.LINE_AA,
        )
    return annotated


def _visible_polygon(
    detection: PlateFrameDetection, *, width: int, height: int
) -> np.ndarray | None:
    points: tuple[tuple[float, float], ...] | None = detection.polygon
    if points is None and detection.bbox is not None:
        x1, y1, x2, y2 = detection.bbox
        points = ((x1, y1), (x2, y1), (x2, y2), (x1, y2))
    if points is None or len(points) < 3 or width <= 0 or height <= 0:
        return None
    polygon = np.rint(np.asarray(points, dtype=np.float64)).astype(np.int32)
    polygon[:, 0] = np.clip(polygon[:, 0], 0, width - 1)
    polygon[:, 1] = np.clip(polygon[:, 1], 0, height - 1)
    if cv2.contourArea(polygon) <= 0:
        return None
    return polygon


__all__ = ["annotate_plate_frame"]
