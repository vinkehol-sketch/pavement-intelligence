"""Contratos neutrales e inmutables para análisis OCR de una fuente cercana."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class PlateAnalysisState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


class PlateReadingStatus(str, Enum):
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"
    REJECTED = "REJECTED"


class PlateReadingOrigin(str, Enum):
    OPERATIONAL_OCR = "OPERATIONAL_OCR"


@dataclass(frozen=True)
class PlateReadingCandidate:
    reading_id: str
    source_id: str
    frame_index: int
    timestamp_seconds: float
    raw_text: str = field(repr=False)
    normalized_text: str = field(repr=False)
    confidence: float
    crop_reference: str | None
    direction: str | None
    lane: str | None
    status: PlateReadingStatus
    origin: PlateReadingOrigin
    reviewed: bool = False

    def __post_init__(self) -> None:
        if not self.reading_id or not self.source_id:
            raise ValueError("reading_id y source_id son obligatorios.")
        if self.frame_index < 0 or self.timestamp_seconds < 0:
            raise ValueError("El frame y el timestamp no pueden ser negativos.")
        if not self.normalized_text:
            raise ValueError("Una lectura candidata necesita texto normalizado.")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence debe estar entre 0 y 1.")
        if self.reviewed != (self.status is not PlateReadingStatus.PENDING):
            raise ValueError("reviewed y status deben ser coherentes.")


@dataclass(frozen=True)
class PlateFrameResult:
    source_id: str
    frame_index: int
    timestamp_seconds: float
    candidate_count: int
    readings: tuple[PlateReadingCandidate, ...]
    warnings: tuple[str, ...]
    end_of_source: bool
    frame: np.ndarray | None = field(default=None, repr=False, compare=False)
    roi_bbox: tuple[int, int, int, int] | None = None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id es obligatorio.")
        if self.frame_index < 0 or self.timestamp_seconds < 0:
            raise ValueError("El frame y el timestamp no pueden ser negativos.")
        if self.candidate_count < 0:
            raise ValueError("candidate_count no puede ser negativo.")


@dataclass(frozen=True)
class PlateBatchResult:
    plate_batch_id: str
    monitoring_point_id: str | None
    source_id: str
    started_at_source_seconds: float
    ended_at_source_seconds: float
    readings: tuple[PlateReadingCandidate, ...]
    warnings: tuple[str, ...]
    state: PlateAnalysisState
    normative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not self.plate_batch_id or not self.source_id:
            raise ValueError("plate_batch_id y source_id son obligatorios.")
        if self.started_at_source_seconds < 0:
            raise ValueError("El inicio del lote no puede ser negativo.")
        if self.ended_at_source_seconds < self.started_at_source_seconds:
            raise ValueError("El fin del lote no puede preceder al inicio.")


__all__ = [
    "PlateAnalysisState",
    "PlateBatchResult",
    "PlateFrameResult",
    "PlateReadingCandidate",
    "PlateReadingOrigin",
    "PlateReadingStatus",
]
