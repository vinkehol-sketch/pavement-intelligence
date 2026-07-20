"""Estado y limpieza aislados para la fuente OCR real de placas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import MutableMapping

from pavement_intelligence.ui.utils.uploaded_video import (
    UploadedVideoHandle,
    cleanup_uploaded_video,
)
from pavement_intelligence.vision.analysis.ocr_models import (
    PlateReadingCandidate,
    PlateReadingStatus,
)


PLATE_SESSION_DEFAULTS = {
    "plate_session_controller": None,
    "plate_session_source_id": None,
    "plate_session_batch_id": None,
    "plate_session_frame_result": None,
    "plate_session_batch_readings": (),
    "plate_session_last_processed_frame": None,
    "plate_session_error": "",
    "plate_session_uploaded_video": None,
    "plate_session_reveal_audit": (),
    "plate_session_reviews": {},
    "plate_session_visible_reading_id": None,
    "plate_session_active_source_token": None,
    "plate_session_uploaded_file_id": None,
    "plate_session_uploaded_hash": None,
    "plate_session_upload_status": None,
}


@dataclass(frozen=True)
class PlateRevealAudit:
    reading_id: str
    reviewer: str
    action: str
    occurred_at: datetime


@dataclass(frozen=True)
class PlateManualReview:
    reading_id: str
    status: PlateReadingStatus
    corrected_text: str | None
    reviewer: str
    reviewed_at: datetime
    reason: str

    def __post_init__(self) -> None:
        if self.status not in {
            PlateReadingStatus.REVIEWED,
            PlateReadingStatus.REJECTED,
        }:
            raise ValueError("La revisión manual debe aprobar/corregir o rechazar.")
        if not self.reviewer.strip():
            raise ValueError("La revisión requiere un revisor.")
        if self.status is PlateReadingStatus.REVIEWED and not (
            self.corrected_text or ""
        ).strip():
            raise ValueError("Una corrección revisada no puede estar vacía.")
        if self.status is PlateReadingStatus.REJECTED and self.corrected_text is not None:
            raise ValueError("Una lectura rechazada no conserva texto corregido.")


def initialize_plate_session(session: MutableMapping[str, object]) -> None:
    for key, default in PLATE_SESSION_DEFAULTS.items():
        if isinstance(default, dict):
            session.setdefault(key, {})
        else:
            session.setdefault(key, default)


def cleanup_plate_session(
    session: MutableMapping[str, object], *, clear_results: bool = True
) -> None:
    """Cierra primero la fuente y elimina después el upload temporal."""
    controller = session.get("plate_session_controller")
    if controller is not None:
        close = getattr(controller, "close", None)
        if callable(close):
            close()
    uploaded = session.get("plate_session_uploaded_video")
    if isinstance(uploaded, UploadedVideoHandle):
        cleanup_uploaded_video(uploaded)
    session["plate_session_controller"] = None
    session["plate_session_uploaded_video"] = None
    session["plate_session_frame_result"] = None
    session["plate_session_last_processed_frame"] = None
    session["plate_session_visible_reading_id"] = None
    if clear_results:
        session["plate_session_source_id"] = None
        session["plate_session_batch_id"] = None
        session["plate_session_batch_readings"] = ()
        session["plate_session_error"] = ""
        session["plate_session_reveal_audit"] = ()
        session["plate_session_reviews"] = {}
        session["plate_session_active_source_token"] = None
        session["plate_session_uploaded_file_id"] = None
        session["plate_session_uploaded_hash"] = None
        session["plate_session_upload_status"] = None


def mask_plate_text(text: str) -> str:
    normalized = text.strip().upper()
    if not normalized:
        return "***-???"
    suffix = normalized[-3:]
    return f"***-{suffix:?>3}"


def toggle_plate_reveal(
    session: MutableMapping[str, object],
    reading_id: str,
    reviewer: str,
    *,
    now: datetime | None = None,
) -> bool:
    if not reviewer.strip():
        raise ValueError("Seleccione un revisor.")
    readings = session.get("plate_session_batch_readings", ())
    if not any(
        isinstance(item, PlateReadingCandidate) and item.reading_id == reading_id
        for item in readings
    ):
        raise ValueError("La lectura OCR no existe en el lote activo.")
    visible = session.get("plate_session_visible_reading_id") == reading_id
    session["plate_session_visible_reading_id"] = None if visible else reading_id
    audit = tuple(session.get("plate_session_reveal_audit", ()))
    session["plate_session_reveal_audit"] = (
        *audit,
        PlateRevealAudit(
            reading_id=reading_id,
            reviewer=reviewer,
            action="HIDE" if visible else "REVEAL",
            occurred_at=now or datetime.now(timezone.utc),
        ),
    )
    return not visible


def correct_plate_reading(
    session: MutableMapping[str, object],
    reading_id: str,
    corrected_text: str,
    reviewer: str,
    *,
    reason: str = "Corrección manual",
    now: datetime | None = None,
) -> PlateManualReview:
    normalized = corrected_text.strip().upper()
    review = PlateManualReview(
        reading_id=reading_id,
        status=PlateReadingStatus.REVIEWED,
        corrected_text=normalized,
        reviewer=reviewer,
        reviewed_at=now or datetime.now(timezone.utc),
        reason=reason.strip() or "Corrección manual",
    )
    _save_review(session, review)
    return review


def reject_plate_reading(
    session: MutableMapping[str, object],
    reading_id: str,
    reviewer: str,
    *,
    reason: str = "Rechazo manual",
    now: datetime | None = None,
) -> PlateManualReview:
    review = PlateManualReview(
        reading_id=reading_id,
        status=PlateReadingStatus.REJECTED,
        corrected_text=None,
        reviewer=reviewer,
        reviewed_at=now or datetime.now(timezone.utc),
        reason=reason.strip() or "Rechazo manual",
    )
    _save_review(session, review)
    return review


def _save_review(
    session: MutableMapping[str, object], review: PlateManualReview
) -> None:
    reviews = dict(session.get("plate_session_reviews", {}))
    reviews[review.reading_id] = review
    session["plate_session_reviews"] = reviews
    session["plate_session_visible_reading_id"] = None


__all__ = [
    "PLATE_SESSION_DEFAULTS",
    "PlateManualReview",
    "PlateRevealAudit",
    "cleanup_plate_session",
    "correct_plate_reading",
    "initialize_plate_session",
    "mask_plate_text",
    "reject_plate_reading",
    "toggle_plate_reveal",
]
