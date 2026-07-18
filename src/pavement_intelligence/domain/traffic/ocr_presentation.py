"""Modelos puros para la revisión experimental de lecturas OCR sintéticas."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class PlateReviewStatus(str, Enum):
    PENDING = "PENDING"
    VALID = "VALID"
    DOUBTFUL = "DOUBTFUL"
    ILLEGIBLE = "ILLEGIBLE"


@dataclass(frozen=True)
class PlateReadingPresentation:
    reading_id: str
    track_id: str
    event_id: str
    timestamp: datetime
    original_text: str
    masked_text: str
    confidence: float
    vehicle_category: str
    direction: str
    status: PlateReviewStatus
    crop_image_path: str
    frame_image_path: str
    suggested_alternatives: tuple[str, ...]
    data_origin: str

    def __post_init__(self) -> None:
        if self.data_origin != "SYNTHETIC_UI_DEMO":
            raise ValueError("Las lecturas de esta fase deben ser sintéticas.")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence debe estar entre 0 y 1.")
        if not self.reading_id or not self.track_id:
            raise ValueError("reading_id y track_id son obligatorios.")
        if self.status is PlateReviewStatus.VALID and not self.original_text.strip():
            raise ValueError("Una lectura válida no puede estar vacía.")


@dataclass(frozen=True)
class PlateCorrectionRequest:
    reading_id: str
    corrected_text: str
    reason: str
    notes: str
    reviewed_by: str

    def __post_init__(self) -> None:
        if not self.corrected_text.strip():
            raise ValueError("La lectura corregida no puede estar vacía.")
        if not self.reason.strip():
            raise ValueError("Una corrección requiere motivo.")
        if not self.reviewed_by.strip():
            raise ValueError("Una corrección requiere revisor.")


@dataclass(frozen=True)
class PlateReviewRecord:
    reading_id: str
    original_text: str
    corrected_text: str | None
    status: PlateReviewStatus
    reason: str
    notes: str
    reviewed_by: str
    reviewed_at: datetime
    data_origin: str = "SYNTHETIC_UI_DEMO"

    @property
    def final_text(self) -> str | None:
        if self.status is PlateReviewStatus.ILLEGIBLE:
            return None
        return self.corrected_text or self.original_text

    def __post_init__(self) -> None:
        if self.status is PlateReviewStatus.PENDING:
            raise ValueError("Un registro guardado no puede quedar pendiente.")
        if self.status is PlateReviewStatus.VALID and not (self.corrected_text or self.original_text).strip():
            raise ValueError("Una lectura válida no puede estar vacía.")
        if self.corrected_text is not None and self.corrected_text != self.original_text:
            if not self.reason.strip() or not self.reviewed_by.strip():
                raise ValueError("Una corrección requiere motivo y revisor.")
        if self.status is PlateReviewStatus.ILLEGIBLE and self.corrected_text is not None:
            raise ValueError("Una lectura ilegible no puede guardar texto corregido.")


@dataclass(frozen=True)
class PlateRevealAuditRecord:
    reading_id: str
    reviewed_by: str
    revealed_at: datetime
    action: str

    def __post_init__(self) -> None:
        if self.action not in {"REVEAL", "HIDE"}:
            raise ValueError("action debe ser REVEAL o HIDE.")


@dataclass(frozen=True)
class OcrReviewPageState:
    readings: tuple[PlateReadingPresentation, ...]
    reviews: tuple[PlateReviewRecord, ...] = ()
    selected_reading_id: str | None = None
    visible_reading_id: str | None = None
    reveal_audit: tuple[PlateRevealAuditRecord, ...] = ()

    def __post_init__(self) -> None:
        ids = {item.reading_id for item in self.readings}
        if len(ids) != len(self.readings):
            raise ValueError("reading_id debe ser único.")
        if self.selected_reading_id is not None and self.selected_reading_id not in ids:
            raise ValueError("La lectura seleccionada no existe.")
        if self.visible_reading_id is not None and self.visible_reading_id != self.selected_reading_id:
            raise ValueError("Solo la lectura seleccionada puede estar visible.")
