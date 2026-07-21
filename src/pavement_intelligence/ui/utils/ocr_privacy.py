"""Privacidad, estado y exportación para la demostración OCR."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import MutableMapping

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pavement_intelligence.domain.traffic.ocr_presentation import (
    PlateCorrectionRequest, PlateReadingPresentation, PlateRevealAuditRecord,
    PlateReviewRecord, PlateReviewStatus,
)
from pavement_intelligence.domain.traffic.presentation import OcrSummaryPresentation
from pavement_intelligence.ui.utils.demo_data import DEMO_DATA_DIR

OCR_SESSION_KEYS = frozenset({
    "ocr_readings_raw", "ocr_review_records", "ocr_selected_reading_id",
    "ocr_visible_reading_id", "ocr_reveal_audit", "ocr_filters",
})
PROTECTED_TRAFFIC_KEYS = frozenset({
    "traffic_review_events", "traffic_review_approval", "tpda_input_from_review", "vision_events_raw",
})


def mask_plate(text: str) -> str:
    compact = text.strip().upper()
    if not compact:
        return "***-???"
    suffix = compact.split("-", 1)[-1][-3:]
    return f"***-{suffix:?>3}"


def load_demo_plate_readings(path: Path | None = None) -> tuple[PlateReadingPresentation, ...]:
    if path is None:
        from pavement_intelligence.demo.case import build_demo_plate_readings

        return build_demo_plate_readings()
    target = path or DEMO_DATA_DIR / "plate_readings_demo.json"
    with target.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("data_origin") not in {"synthetic_demo", "SYNTHETIC_UI_DEMO"}:
        raise ValueError("El lote OCR debe ser sintético.")
    readings = []
    for item in payload["readings"]:
        record = dict(item)
        record["timestamp"] = datetime.fromisoformat(record["timestamp"])
        record["status"] = PlateReviewStatus(record["status"])
        record["suggested_alternatives"] = tuple(record["suggested_alternatives"])
        if record["masked_text"] != mask_plate(record["original_text"]):
            raise ValueError("masked_text no coincide con la anonimización calculada.")
        readings.append(PlateReadingPresentation(**record))
    return tuple(readings)


def summarize_readings(
    readings: tuple[PlateReadingPresentation, ...],
    reviews: dict[str, PlateReviewRecord] | None = None,
) -> OcrSummaryPresentation:
    counts = {status: 0 for status in PlateReviewStatus}
    for reading in readings:
        effective_status = (reviews or {}).get(reading.reading_id, reading).status
        counts[effective_status] += 1
    mean = sum(item.confidence for item in readings) / len(readings) * 100 if readings else 0
    return OcrSummaryPresentation(
        detected=len(readings), valid=counts[PlateReviewStatus.VALID],
        doubtful=counts[PlateReviewStatus.DOUBTFUL], pending=counts[PlateReviewStatus.PENDING],
        illegible=counts[PlateReviewStatus.ILLEGIBLE], average_confidence_percent=mean,
    )


def render_plate_crop(text: str, *, protected: bool, size: tuple[int, int] = (520, 150)) -> bytes:
    """Genera en backend una placa ficticia; la versión protegida queda realmente difuminada."""
    image = Image.new("RGB", size, "#e8e8ec")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, size[0] - 12, size[1] - 12), radius=12, fill="white", outline="#191B23", width=5)
    label = text.strip().upper() or "SIN LECTURA"
    font = ImageFont.load_default(size=42)
    box = draw.textbbox((0, 0), label, font=font)
    draw.text(((size[0] - (box[2] - box[0])) / 2, (size[1] - (box[3] - box[1])) / 2 - 5), label, font=font, fill="#191B23")
    if protected:
        image = image.filter(ImageFilter.GaussianBlur(radius=14))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def initialize_ocr_session(session: MutableMapping, readings: tuple[PlateReadingPresentation, ...]) -> None:
    session.setdefault("ocr_readings_raw", readings)
    session.setdefault("ocr_review_records", {})
    session.setdefault("ocr_selected_reading_id", readings[0].reading_id if readings else None)
    session.setdefault("ocr_visible_reading_id", None)
    session.setdefault("ocr_reveal_audit", [])
    session.setdefault("ocr_filters", {})


def select_reading(session: MutableMapping, reading_id: str) -> None:
    if session.get("ocr_selected_reading_id") != reading_id:
        session["ocr_visible_reading_id"] = None
    session["ocr_selected_reading_id"] = reading_id


def toggle_plate_visibility(session: MutableMapping, reading_id: str, reviewed_by: str, *, now: datetime | None = None) -> bool:
    if session.get("ocr_selected_reading_id") != reading_id:
        raise ValueError("Solo puede revelarse la lectura seleccionada.")
    visible = session.get("ocr_visible_reading_id") == reading_id
    action = "HIDE" if visible else "REVEAL"
    session["ocr_visible_reading_id"] = None if visible else reading_id
    record = PlateRevealAuditRecord(
        reading_id=reading_id, reviewed_by=reviewed_by,
        revealed_at=now or datetime.now(timezone.utc), action=action,
    )
    session.setdefault("ocr_reveal_audit", []).append(record)
    return not visible


def save_review(session: MutableMapping, record: PlateReviewRecord) -> None:
    reviews = session.setdefault("ocr_review_records", {})
    reviews[record.reading_id] = record


def confirm_unchanged(reading: PlateReadingPresentation, reviewer: str, notes: str = "", *, now: datetime | None = None) -> PlateReviewRecord:
    if not reading.original_text.strip():
        raise ValueError("No se puede confirmar una lectura vacía como válida.")
    if not reviewer.strip():
        raise ValueError("Seleccione un revisor.")
    return PlateReviewRecord(reading.reading_id, reading.original_text, reading.original_text, PlateReviewStatus.VALID, "Sin cambios", notes, reviewer, now or datetime.now(timezone.utc))


def confirm_correction(reading: PlateReadingPresentation, request: PlateCorrectionRequest, *, now: datetime | None = None) -> PlateReviewRecord:
    return PlateReviewRecord(reading.reading_id, reading.original_text, request.corrected_text.strip().upper(), PlateReviewStatus.VALID, request.reason, request.notes, request.reviewed_by, now or datetime.now(timezone.utc))


def mark_status(reading: PlateReadingPresentation, status: PlateReviewStatus, reviewer: str, notes: str = "", *, now: datetime | None = None) -> PlateReviewRecord:
    if status not in {PlateReviewStatus.DOUBTFUL, PlateReviewStatus.ILLEGIBLE}:
        raise ValueError("Esta acción solo admite DOUBTFUL o ILLEGIBLE.")
    corrected = None if status is PlateReviewStatus.ILLEGIBLE else reading.original_text
    return PlateReviewRecord(reading.reading_id, reading.original_text, corrected, status, status.value, notes, reviewer, now or datetime.now(timezone.utc))


def export_reviewed_csv(readings: tuple[PlateReadingPresentation, ...], reviews: dict[str, PlateReviewRecord]) -> bytes:
    by_id = {item.reading_id: item for item in readings}
    output = io.StringIO()
    fields = ["reading_id", "track_id", "original_text", "corrected_text", "status", "confidence", "reason", "reviewed_by", "reviewed_at", "data_origin"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for reading_id, review in reviews.items():
        reading = by_id[reading_id]
        writer.writerow({
            "reading_id": reading_id, "track_id": reading.track_id,
            "original_text": review.original_text, "corrected_text": review.corrected_text or "",
            "status": review.status.value, "confidence": reading.confidence,
            "reason": review.reason, "reviewed_by": review.reviewed_by,
            "reviewed_at": review.reviewed_at.isoformat(),
            "data_origin": reading.data_origin,
        })
    return output.getvalue().encode("utf-8-sig")
