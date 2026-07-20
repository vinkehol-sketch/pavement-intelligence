from __future__ import annotations

import numpy as np

from pavement_intelligence.ui.utils.plate_visualization import annotate_plate_frame
from pavement_intelligence.vision.analysis.ocr_models import PlateFrameDetection


def detection(*, with_geometry: bool = True) -> PlateFrameDetection:
    return PlateFrameDetection(
        normalized_text="ABC123",
        confidence=0.93,
        polygon=(
            ((20.0, 30.0), (80.0, 30.0), (80.0, 55.0), (20.0, 55.0))
            if with_geometry
            else None
        ),
    )


def test_private_annotation_masks_polygon_without_mutating_source():
    frame = np.full((100, 120, 3), 255, dtype=np.uint8)
    original = frame.copy()
    annotated = annotate_plate_frame(frame, (detection(),), protect_plate=True)
    assert np.array_equal(frame, original)
    assert np.all(annotated[42, 50] == 24)


def test_explicit_privacy_disable_keeps_polygon_interior_visible():
    frame = np.full((100, 120, 3), 255, dtype=np.uint8)
    annotated = annotate_plate_frame(frame, (detection(),), protect_plate=False)
    assert np.all(annotated[42, 50] == 255)


def test_annotation_never_invents_geometry():
    frame = np.full((100, 120, 3), 255, dtype=np.uint8)
    annotated = annotate_plate_frame(
        frame, (detection(with_geometry=False),), protect_plate=True
    )
    assert np.array_equal(annotated, frame)
