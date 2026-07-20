"""Optional validation of the real PaddleOCR backend on one local image.

Run explicitly with ``RUN_PADDLEOCR_REAL=1``.  Set ``PADDLEOCR_TEST_IMAGE``
to an authorized local image, or ``PADDLEOCR_SYNTHETIC_TEXT`` to generate a
temporary fictional plate that is deleted with pytest's temporary directory.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from pavement_intelligence.vision.plates.paddleocr_reader import PaddleOCRPlateReader

EXPECTED_ENV = "PADDLEOCR_EXPECTED_TEXT"
IMAGE_ENV = "PADDLEOCR_TEST_IMAGE"
RUN_ENV = "RUN_PADDLEOCR_REAL"
SYNTHETIC_ENV = "PADDLEOCR_SYNTHETIC_TEXT"


def _normalized(text: str) -> str:
    return PaddleOCRPlateReader._normalize_text(text)


def _build_fictional_plate(path: Path, text: str) -> tuple[int, int, int, int]:
    image = Image.new("RGB", (1280, 720), "#253342")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((220, 180, 1060, 610), radius=48, fill="#506070")
    plate_box = (390, 320, 890, 480)
    draw.rounded_rectangle(plate_box, radius=12, fill="white", outline="black", width=8)
    try:
        font = ImageFont.truetype("arialbd.ttf", 104)
    except OSError:
        font = ImageFont.load_default(size=104)
    text_box = draw.textbbox((0, 0), text, font=font)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    text_xy = (
        plate_box[0] + (plate_box[2] - plate_box[0] - text_width) // 2,
        plate_box[1] + (plate_box[3] - plate_box[1] - text_height) // 2 - text_box[1],
    )
    draw.text(text_xy, text, fill="black", font=font)
    image.save(path, format="PNG")
    return plate_box


def _authorized_image(tmp_path: Path) -> tuple[Path, tuple[int, int, int, int]]:
    configured = os.getenv(IMAGE_ENV)
    if configured:
        path = Path(configured).expanduser().resolve(strict=True)
        with Image.open(path) as image:
            return path, (0, 0, image.width, image.height)

    synthetic_text = os.getenv(SYNTHETIC_ENV)
    if not synthetic_text:
        pytest.skip(f"set {IMAGE_ENV} or {SYNTHETIC_ENV} for the optional real test")
    path = tmp_path / "fictional_plate.png"
    return path, _build_fictional_plate(path, synthetic_text)


def test_modern_result_parser_accepts_paddleocr_3_payload() -> None:
    results = [{"res": {"rec_texts": ["ABC-123"], "rec_scores": [0.92]}}]
    assert PaddleOCRPlateReader._modern_candidates(results) == [("ABC-123", 0.92)]


@pytest.mark.skipif(os.getenv(RUN_ENV) != "1", reason=f"requires explicit {RUN_ENV}=1")
def test_real_paddleocr_reader_on_authorized_local_image(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    pytest.importorskip("paddleocr")
    image_path, plate_box = _authorized_image(tmp_path)
    if not os.getenv(IMAGE_ENV):
        request.addfinalizer(lambda: image_path.unlink(missing_ok=True))
    with Image.open(image_path) as source:
        frame = np.asarray(source.convert("RGB"))[:, :, ::-1].copy()

    expected = _normalized(os.getenv(EXPECTED_ENV, os.getenv(SYNTHETIC_ENV, "")))
    px1, py1, px2, py2 = plate_box
    cases = {
        "full_image": (0, 0, frame.shape[1], frame.shape[0]),
        "manual_plate_crop": plate_box,
        "adjusted_roi": (max(0, px1 - 24), max(0, py1 - 20), px2 + 24, py2 + 20),
    }
    reader = PaddleOCRPlateReader(min_confidence=0.0, anonymize=False, lang="en")
    reader._load_model()
    crop = frame[py1:py2, px1:px2]
    raw_started = time.perf_counter()
    raw_results = reader._ocr.predict(
        crop,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    raw_elapsed = time.perf_counter() - raw_started
    raw_candidates = reader._modern_candidates(raw_results)
    print(
        f"PADDLEOCR_REAL raw_candidates={raw_candidates!r} "
        f"seconds={raw_elapsed:.6f}"
    )
    observations: dict[str, tuple[str | None, float | None, float]] = {}

    for name, roi in cases.items():
        started = time.perf_counter()
        result = reader.detect_and_read(frame, roi)
        elapsed = time.perf_counter() - started
        observations[name] = (
            result.text_raw if result else None,
            result.confidence if result else None,
            elapsed,
        )
        print(
            f"PADDLEOCR_REAL case={name} dimensions={frame.shape[1]}x{frame.shape[0]} "
            f"roi={roi} normalized={observations[name][0]!r} "
            f"confidence={observations[name][1]!r} seconds={elapsed:.6f}"
        )

    detected = observations["manual_plate_crop"][0]
    assert detected is not None
    if expected:
        assert detected == expected
    for _, confidence, _ in observations.values():
        if confidence is not None:
            assert 0.0 <= confidence <= 1.0

    repeated = reader.detect_and_read(frame, plate_box)
    assert repeated is not None
    assert repeated.text_raw == detected

    assert reader.detect_and_read(np.array([]), (0, 0, 1, 1)) is None
    assert reader.detect_and_read(frame, (0, 0, 0, 0)) is None
