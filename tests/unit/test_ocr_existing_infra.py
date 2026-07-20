from __future__ import annotations

import builtins
import importlib
import sys

import numpy as np
import pytest

from pavement_intelligence.vision.plates.base import AbstractPlateReader, PlateResult
from pavement_intelligence.vision.plates.paddleocr_reader import PaddleOCRPlateReader


class FakeEngine:
    def __init__(self, results=None, error: Exception | None = None):
        self.results = results
        self.error = error
        self.calls = []

    def ocr(self, image, cls=True):
        self.calls.append((image.copy(), cls))
        if self.error:
            raise self.error
        return self.results


class FakeModernEngine:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def predict(self, image, **kwargs):
        self.calls.append((image.copy(), kwargs))
        return self.results


def candidate(text, confidence):
    return [None, (text, confidence)]


def reader_with(results, **kwargs):
    reader = PaddleOCRPlateReader(**kwargs)
    reader._ocr = FakeEngine(results)
    return reader


@pytest.fixture
def frame():
    return np.zeros((80, 120, 3), dtype=np.uint8)


def test_modules_import_without_paddleocr_installed(monkeypatch):
    monkeypatch.setitem(sys.modules, "paddleocr", None)
    module = importlib.import_module("pavement_intelligence.vision.plates.paddleocr_reader")
    assert module.PaddleOCRPlateReader()._ocr is None


def test_missing_optional_engine_returns_none(monkeypatch, frame):
    monkeypatch.setitem(sys.modules, "paddleocr", None)
    assert PaddleOCRPlateReader().detect_and_read(frame, (0, 0, 50, 50)) is None


def test_public_contract_and_simulated_engine_instantiation(frame):
    reader = reader_with([[candidate("ABC123", 0.9)]])
    assert isinstance(reader, AbstractPlateReader)
    result = reader.detect_and_read(frame, (1, 2, 40, 30))
    assert isinstance(result, PlateResult)
    assert result.text_raw is None
    assert result.is_anonymized is True


def test_valid_image_is_cropped_to_vehicle_bbox(frame):
    reader = reader_with([[candidate("ABC123", 0.9)]])
    reader.detect_and_read(frame, (10, 12, 70, 52))
    crop, cls = reader._ocr.calls[0]
    assert crop.shape == (40, 60, 3)
    assert cls is True


@pytest.mark.parametrize("invalid_frame", [None, np.array([]), np.zeros((20,), dtype=np.uint8)])
def test_null_or_invalid_image_returns_none(invalid_frame):
    reader = reader_with([[candidate("ABC123", 0.9)]])
    assert reader.detect_and_read(invalid_frame, (0, 0, 10, 10)) is None


@pytest.mark.parametrize("results", [None, [], [[]]])
def test_empty_ocr_result_returns_none(frame, results):
    assert reader_with(results).detect_and_read(frame, (0, 0, 30, 30)) is None


@pytest.mark.parametrize("results", [[{"unexpected": True}], [[None], ["bad", None], 7]])
def test_unexpected_result_structure_is_ignored(frame, results):
    assert reader_with(results).detect_and_read(frame, (0, 0, 30, 30)) is None


def test_null_text_is_ignored(frame):
    assert reader_with([[candidate(None, 0.99)]]).detect_and_read(frame, (0, 0, 30, 30)) is None


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("  abc123  ", "ABC123"),
        ("abc123", "ABC123"),
        ("ABC-123", "ABC123"),
        ("ABC 123./_", "ABC123"),
        ("ÁBÇ-12#3", "B123"),
    ],
)
def test_text_is_normalized_before_public_nonanonymous_result(frame, raw, normalized):
    result = reader_with([[candidate(raw, 0.9)]], anonymize=False).detect_and_read(frame, (0, 0, 30, 30))
    assert result.text_raw == normalized


def test_multiple_candidates_select_highest_confidence(frame):
    results = [[candidate("LOW111", 0.61), candidate("BEST22", 0.95), candidate("MID333", 0.8)]]
    result = reader_with(results, anonymize=False).detect_and_read(frame, (0, 0, 30, 30))
    assert result.text_raw == "BEST22"
    assert result.confidence == 0.95


def test_paddleocr_3_polygon_and_bbox_are_translated_from_roi(frame):
    payload = {
        "res": {
            "rec_texts": ["ABC-123"],
            "rec_scores": [0.94],
            "rec_polys": [[[2, 3], [22, 3], [22, 11], [2, 11]]],
            "rec_boxes": [[2, 3, 22, 11]],
        }
    }
    reader = PaddleOCRPlateReader(anonymize=False)
    reader._ocr = FakeModernEngine([payload])
    reader._paddleocr_major = 3
    result = reader.detect_and_read(frame, (10, 20, 70, 60))
    assert result.text_raw == "ABC123"
    assert result.polygon == (
        (12.0, 23.0),
        (32.0, 23.0),
        (32.0, 31.0),
        (12.0, 31.0),
    )
    assert result.bbox == (12.0, 23.0, 32.0, 31.0)


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_confidence_boundaries_are_valid_when_threshold_allows(frame, confidence):
    result = reader_with([[candidate("ABC123", confidence)]], min_confidence=0).detect_and_read(frame, (0, 0, 30, 30))
    assert result is not None
    assert result.confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("nan"), float("inf"), None, "high"])
def test_out_of_range_or_non_numeric_confidence_is_ignored(frame, confidence):
    assert reader_with([[candidate("ABC123", confidence)]], min_confidence=0).detect_and_read(frame, (0, 0, 30, 30)) is None


def test_engine_exception_returns_none(frame):
    reader = PaddleOCRPlateReader()
    reader._ocr = FakeEngine(error=RuntimeError("engine failure"))
    assert reader.detect_and_read(frame, (0, 0, 30, 30)) is None


def test_hash_is_stable_uppercase_and_eight_characters():
    reader = PaddleOCRPlateReader()
    first = reader._hash_plate(" abc-123 ")
    assert len(first) == 8
    assert first == first.upper() or first == first.lower()
    assert first == reader._hash_plate("ABC123")
    assert first == reader._hash_plate("abc 123")


def test_distinct_normalized_inputs_have_distinct_hashes_in_fixture():
    reader = PaddleOCRPlateReader()
    values = {reader._hash_plate(text) for text in ("ABC123", "XYZ987", "TEST42")}
    assert len(values) == 3


def test_anonymized_result_does_not_expose_raw_text_in_repr(frame):
    result = reader_with([[candidate("PRIVATE123", 0.9)]]).detect_and_read(frame, (0, 0, 30, 30))
    assert result.text_raw is None
    assert "PRIVATE123" not in repr(result)


def test_reader_has_no_streamlit_dependency():
    source = (importlib.import_module("pavement_intelligence.vision.plates.paddleocr_reader").__file__)
    assert "streamlit" not in open(source, encoding="utf-8").read().lower()


def test_detection_does_not_write_files(monkeypatch, frame):
    reader = reader_with([[candidate("ABC123", 0.9)]])
    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("file write")))
    assert reader.detect_and_read(frame, (0, 0, 30, 30)) is not None


def test_detection_does_not_modify_module_global_state(frame):
    module = importlib.import_module("pavement_intelligence.vision.plates.paddleocr_reader")
    before = {key: value for key, value in vars(module).items() if not key.startswith("__")}
    reader_with([[candidate("ABC123", 0.9)]]).detect_and_read(frame, (0, 0, 30, 30))
    after = {key: value for key, value in vars(module).items() if not key.startswith("__")}
    assert before == after
