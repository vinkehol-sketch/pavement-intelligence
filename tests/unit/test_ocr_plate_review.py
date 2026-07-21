from __future__ import annotations

import csv
import inspect
import io
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from pavement_intelligence.domain.traffic import ocr_presentation
from pavement_intelligence.domain.traffic.ocr_presentation import (
    OcrReviewPageState, PlateCorrectionRequest, PlateReviewStatus,
)
from pavement_intelligence.ui.utils.ocr_privacy import (
    OCR_SESSION_KEYS, PROTECTED_TRAFFIC_KEYS, confirm_correction, confirm_unchanged,
    export_reviewed_csv, initialize_ocr_session, load_demo_plate_readings,
    mark_status, mask_plate, render_plate_crop, save_review, select_reading,
    summarize_readings, toggle_plate_visibility,
)


@pytest.fixture
def readings():
    return load_demo_plate_readings()


def test_demo_data_loads_all_exclusive_statuses(readings):
    assert {item.status for item in readings} == set(PlateReviewStatus)
    assert all(item.data_origin == "synthetic_demo" for item in readings)


@pytest.mark.parametrize(("text", "expected"), [("DEMO-01", "***-?01"), ("FICT-?2", "***-??2"), ("", "***-???")])
def test_plate_anonymization(text, expected):
    assert mask_plate(text) == expected


def test_protected_crop_is_generated_and_differs_from_visible_crop():
    visible = Image.open(io.BytesIO(render_plate_crop("DEMO-01", protected=False)))
    protected = Image.open(io.BytesIO(render_plate_crop("DEMO-01", protected=True)))
    assert visible.size == protected.size
    assert ImageChops.difference(visible, protected).getbbox() is not None


def test_only_selected_reading_can_be_revealed_and_reveal_is_audited(readings):
    session = {}
    initialize_ocr_session(session, readings)
    now = datetime(2026, 7, 18, tzinfo=timezone.utc)
    assert toggle_plate_visibility(session, readings[0].reading_id, "jperez", now=now)
    assert session["ocr_visible_reading_id"] == readings[0].reading_id
    assert session["ocr_reveal_audit"][0].action == "REVEAL"
    with pytest.raises(ValueError):
        toggle_plate_visibility(session, readings[1].reading_id, "jperez")


def test_selecting_another_reading_hides_previous_one(readings):
    session = {}
    initialize_ocr_session(session, readings)
    toggle_plate_visibility(session, readings[0].reading_id, "jperez")
    select_reading(session, readings[1].reading_id)
    assert session["ocr_visible_reading_id"] is None
    assert session["ocr_selected_reading_id"] == readings[1].reading_id


def test_visibility_toggle_records_hide_action(readings):
    session = {}
    initialize_ocr_session(session, readings)
    toggle_plate_visibility(session, readings[0].reading_id, "jperez")
    assert not toggle_plate_visibility(session, readings[0].reading_id, "jperez")
    assert [item.action for item in session["ocr_reveal_audit"]] == ["REVEAL", "HIDE"]


def test_original_ocr_reading_is_immutable(readings):
    with pytest.raises(FrozenInstanceError):
        readings[0].original_text = "CHANGED"
    record = confirm_unchanged(readings[0], "jperez")
    assert record.original_text == readings[0].original_text


def test_correction_requires_reason_and_reviewer(readings):
    with pytest.raises(ValueError):
        PlateCorrectionRequest(readings[1].reading_id, "FICT-02", "", "", "jperez")
    with pytest.raises(ValueError):
        PlateCorrectionRequest(readings[1].reading_id, "FICT-02", "OCR", "", "")


def test_empty_text_cannot_be_confirmed_valid(readings):
    illegible = next(item for item in readings if item.status is PlateReviewStatus.ILLEGIBLE)
    with pytest.raises(ValueError):
        confirm_unchanged(illegible, "jperez")


def test_correction_preserves_original_and_sets_single_valid_status(readings):
    reading = readings[1]
    request = PlateCorrectionRequest(reading.reading_id, "FICT-02", "Carácter confundido", "", "jperez")
    review = confirm_correction(reading, request)
    assert review.original_text == "FICT-?2"
    assert review.corrected_text == "FICT-02"
    assert review.status is PlateReviewStatus.VALID


def test_illegible_review_has_no_valid_text(readings):
    review = mark_status(readings[1], PlateReviewStatus.ILLEGIBLE, "jperez")
    assert review.status is PlateReviewStatus.ILLEGIBLE
    assert review.corrected_text is None
    assert review.final_text is None


def test_saved_reviews_survive_selection_changes(readings):
    session = {}
    initialize_ocr_session(session, readings)
    review = confirm_unchanged(readings[0], "jperez")
    save_review(session, review)
    select_reading(session, readings[1].reading_id)
    assert session["ocr_review_records"][readings[0].reading_id] == review


def test_session_keys_are_isolated_from_official_traffic_state(readings):
    assert OCR_SESSION_KEYS.isdisjoint(PROTECTED_TRAFFIC_KEYS)
    session = {key: object() for key in PROTECTED_TRAFFIC_KEYS}
    protected_snapshot = dict(session)
    initialize_ocr_session(session, readings)
    toggle_plate_visibility(session, readings[0].reading_id, "jperez")
    assert all(session[key] is protected_snapshot[key] for key in PROTECTED_TRAFFIC_KEYS)


def test_safe_export_contains_only_reviewed_synthetic_text_data(readings):
    review = confirm_unchanged(readings[0], "jperez")
    payload = export_reviewed_csv(readings, {review.reading_id: review})
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["data_origin"] == "synthetic_demo"
    assert "image" not in " ".join(rows[0]).lower()
    assert readings[1].original_text not in payload.decode("utf-8-sig")


def test_page_state_rejects_visible_nonselected_reading(readings):
    with pytest.raises(ValueError):
        OcrReviewPageState(readings, selected_reading_id=readings[0].reading_id, visible_reading_id=readings[1].reading_id)


def test_summary_includes_illegible_readings(readings):
    summary = summarize_readings(readings)
    assert summary.detected == 4
    assert (summary.valid, summary.doubtful, summary.pending, summary.illegible) == (1, 1, 1, 1)


def test_ocr_models_have_no_streamlit_dependency():
    assert "streamlit" not in inspect.getsource(ocr_presentation)


def test_navigation_is_bidirectional_and_registered():
    root = Path(__file__).resolve().parents[2]
    app = (root / "src/pavement_intelligence/ui/app.py").read_text(encoding="utf-8")
    monitoring = (root / "src/pavement_intelligence/ui/pages/traffic_monitoring.py").read_text(encoding="utf-8")
    ocr_page = (root / "src/pavement_intelligence/ui/pages/ocr_plate_review.py").read_text(encoding="utf-8")
    assert 'st.Page("pages/ocr_plate_review.py"' in app
    assert 'st.switch_page("pages/ocr_plate_review.py")' in monitoring
    assert 'st.switch_page("pages/traffic_monitoring.py")' in ocr_page
