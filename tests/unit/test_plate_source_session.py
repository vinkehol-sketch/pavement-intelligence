from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest

from pavement_intelligence.ui.utils import plate_session
from pavement_intelligence.ui.utils.plate_session import (
    PLATE_SESSION_DEFAULTS,
    PlateManualReview,
    cleanup_plate_session,
    correct_plate_reading,
    initialize_plate_session,
    mask_plate_text,
    reject_plate_reading,
    toggle_plate_reveal,
)
from pavement_intelligence.ui.utils.uploaded_video import store_uploaded_video
from pavement_intelligence.vision.analysis.ocr_models import (
    PlateReadingCandidate,
    PlateReadingOrigin,
    PlateReadingStatus,
)


class FakeController:
    def __init__(self, events: list[str] | None = None) -> None:
        self.closed = 0
        self.events = events

    def close(self) -> None:
        self.closed += 1
        if self.events is not None:
            self.events.append("controller")


class Upload:
    name = "plates.mp4"
    type = "video/mp4"
    data = b"authorized"
    size = len(data)

    def getvalue(self):
        return self.data


def reading(reading_id: str = "reading:1") -> PlateReadingCandidate:
    return PlateReadingCandidate(
        reading_id=reading_id,
        source_id="plate-source:1",
        frame_index=1,
        timestamp_seconds=1.0,
        raw_text="ABC-123",
        normalized_text="ABC123",
        confidence=0.9,
        crop_reference="roi:0,0,10,10",
        direction=None,
        lane=None,
        status=PlateReadingStatus.PENDING,
        origin=PlateReadingOrigin.OPERATIONAL_OCR,
    )


def test_session_initializes_all_exclusive_plate_keys():
    session = {}
    initialize_plate_session(session)
    assert set(PLATE_SESSION_DEFAULTS) <= set(session)
    assert all(key.startswith("plate_session_") for key in PLATE_SESSION_DEFAULTS)


def test_initialization_is_idempotent_and_preserves_values():
    session = {"plate_session_batch_id": "plate:existing"}
    initialize_plate_session(session)
    initialize_plate_session(session)
    assert session["plate_session_batch_id"] == "plate:existing"


def test_plate_session_does_not_modify_traffic_state():
    protected = {
        "traffic_analysis_controller": object(),
        "vision_events_raw": [object()],
        "traffic_review_approved": True,
        "tpda_input_from_review": object(),
    }
    session = dict(protected)
    initialize_plate_session(session)
    cleanup_plate_session(session)
    assert all(session[key] is value for key, value in protected.items())


def test_cleanup_closes_controller_and_clears_real_batch():
    controller = FakeController()
    session = {
        "plate_session_controller": controller,
        "plate_session_batch_id": "plate:1",
        "plate_session_batch_readings": (reading(),),
        "plate_session_error": "error",
    }
    cleanup_plate_session(session)
    assert controller.closed == 1
    assert session["plate_session_controller"] is None
    assert session["plate_session_batch_id"] is None
    assert session["plate_session_batch_readings"] == ()
    assert session["plate_session_error"] == ""


def test_cleanup_is_idempotent():
    session = {}
    initialize_plate_session(session)
    cleanup_plate_session(session)
    cleanup_plate_session(session)
    assert session["plate_session_controller"] is None


def test_uploaded_video_is_temporary_and_removed_after_controller_close(tmp_path):
    events: list[str] = []
    handle = store_uploaded_video(
        Upload(), temporary_parent=tmp_path, duration_reader=lambda _path: 2.0
    )
    original_cleanup = handle._temporary_directory.cleanup

    def recorded_cleanup():
        events.append("upload")
        original_cleanup()

    handle._temporary_directory.cleanup = recorded_cleanup
    session = {
        "plate_session_controller": FakeController(events),
        "plate_session_uploaded_video": handle,
    }
    cleanup_plate_session(session)
    assert events == ["controller", "upload"]
    assert not handle.temporary_path.exists()


@pytest.mark.parametrize(
    ("text", "masked"),
    [("ABC-123", "***-123"), ("XY9", "***-XY9"), ("", "***-???")],
)
def test_plate_is_masked_by_default(text, masked):
    assert mask_plate_text(text) == masked


def test_reveal_is_explicit_and_audited():
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    session = {"plate_session_batch_readings": (reading(),)}
    assert toggle_plate_reveal(session, "reading:1", "jperez", now=now)
    assert session["plate_session_visible_reading_id"] == "reading:1"
    audit = session["plate_session_reveal_audit"][0]
    assert (audit.action, audit.reviewer, audit.occurred_at) == (
        "REVEAL",
        "jperez",
        now,
    )


def test_second_toggle_hides_and_audits():
    session = {"plate_session_batch_readings": (reading(),)}
    toggle_plate_reveal(session, "reading:1", "jperez")
    assert not toggle_plate_reveal(session, "reading:1", "jperez")
    assert session["plate_session_visible_reading_id"] is None
    assert [item.action for item in session["plate_session_reveal_audit"]] == [
        "REVEAL",
        "HIDE",
    ]


@pytest.mark.parametrize(
    ("reading_id", "reviewer"), [("missing", "jperez"), ("reading:1", "")]
)
def test_reveal_requires_existing_reading_and_reviewer(reading_id, reviewer):
    session = {"plate_session_batch_readings": (reading(),)}
    with pytest.raises(ValueError):
        toggle_plate_reveal(session, reading_id, reviewer)


def test_manual_correction_is_separate_from_original_candidate():
    original = reading()
    session = {"plate_session_batch_readings": (original,)}
    review = correct_plate_reading(
        session, original.reading_id, "xyz-987", "jperez"
    )
    assert review.corrected_text == "XYZ-987"
    assert review.status is PlateReadingStatus.REVIEWED
    assert original.normalized_text == "ABC123"
    assert session["plate_session_visible_reading_id"] is None


def test_empty_correction_is_rejected():
    with pytest.raises(ValueError):
        correct_plate_reading({}, "reading:1", "", "jperez")


def test_manual_rejection_does_not_invent_text():
    review = reject_plate_reading({}, "reading:1", "jperez")
    assert review.status is PlateReadingStatus.REJECTED
    assert review.corrected_text is None


def test_review_requires_reviewer():
    with pytest.raises(ValueError):
        PlateManualReview(
            "reading:1",
            PlateReadingStatus.REJECTED,
            None,
            "",
            datetime.now(timezone.utc),
            "reason",
        )


def test_source_cleanup_clears_dedicated_review_and_reveal_state():
    session = {
        "plate_session_reviews": {"reading:1": object()},
        "plate_session_reveal_audit": (object(),),
        "plate_session_visible_reading_id": "reading:1",
        "plate_session_active_source_token": "local:first",
    }
    cleanup_plate_session(session)
    assert session["plate_session_reviews"] == {}
    assert session["plate_session_reveal_audit"] == ()
    assert session["plate_session_visible_reading_id"] is None
    assert session["plate_session_active_source_token"] is None


def test_session_helper_has_no_framework_or_tpda_dependency():
    source = inspect.getsource(plate_session).lower()
    assert "streamlit" not in source
    assert "tpda" not in source
