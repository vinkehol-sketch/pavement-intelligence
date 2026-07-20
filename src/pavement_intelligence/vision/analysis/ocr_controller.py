"""Coordinador neutral para OCR limitado sobre una fuente visual independiente."""

from __future__ import annotations

import math
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

import numpy as np

from pavement_intelligence.vision.analysis.ocr_models import (
    PlateAnalysisState,
    PlateBatchResult,
    PlateFrameResult,
    PlateReadingCandidate,
    PlateReadingOrigin,
    PlateReadingStatus,
)
from pavement_intelligence.vision.capture import FrameSource, SourceInfo
from pavement_intelligence.vision.plates.base import AbstractPlateReader, PlateResult


@dataclass(frozen=True)
class PlateAnalysisConfig:
    every_n_frames: int = 5
    dedup_window_seconds: float = 5.0
    max_dedup_entries: int = 256
    max_batch_readings: int = 1_000
    monitoring_point_id: str | None = None
    source_id: str | None = None
    origin: PlateReadingOrigin = PlateReadingOrigin.OPERATIONAL_OCR

    def __post_init__(self) -> None:
        if self.every_n_frames <= 0:
            raise ValueError("every_n_frames debe ser positivo.")
        if self.dedup_window_seconds < 0:
            raise ValueError("dedup_window_seconds no puede ser negativo.")
        if self.max_dedup_entries <= 0 or self.max_batch_readings <= 0:
            raise ValueError("Los límites de memoria deben ser positivos.")


@dataclass(frozen=True)
class NormalizedPlateRoi:
    x1: float = 0.10
    y1: float = 0.25
    x2: float = 0.90
    y2: float = 0.90

    def __post_init__(self) -> None:
        values = (self.x1, self.y1, self.x2, self.y2)
        if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values):
            raise ValueError("La ROI normalizada debe estar entre 0 y 1.")
        if self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError("La ROI debe tener un área positiva.")


@dataclass(frozen=True)
class PlateRegion:
    bbox: tuple[int, int, int, int]
    reference: str
    direction: str | None = None
    lane: str | None = None


class PlateCandidateExtractor(Protocol):
    def extract(self, frame: np.ndarray) -> tuple[PlateRegion, ...]: ...


class NormalizedRoiExtractor:
    """Selecciona una ROI fija; no realiza detección automática de placas."""

    def __init__(self, roi: NormalizedPlateRoi = NormalizedPlateRoi()):
        self.roi = roi

    def extract(self, frame: np.ndarray) -> tuple[PlateRegion, ...]:
        if not isinstance(frame, np.ndarray) or frame.ndim < 2 or frame.size == 0:
            return ()
        height, width = frame.shape[:2]
        bbox = (
            int(round(self.roi.x1 * width)),
            int(round(self.roi.y1 * height)),
            int(round(self.roi.x2 * width)),
            int(round(self.roi.y2 * height)),
        )
        reference = "roi:" + ",".join(str(value) for value in bbox)
        return (PlateRegion(bbox=bbox, reference=reference),)


@dataclass(frozen=True)
class _DedupEntry:
    timestamp_seconds: float
    reading_id: str


class PlateAnalysisController:
    """Lee una fuente OCR neutral sin persistencia ni estado del aforo."""

    def __init__(
        self,
        source: FrameSource,
        reader: AbstractPlateReader,
        extractor: PlateCandidateExtractor,
        config: PlateAnalysisConfig = PlateAnalysisConfig(),
    ) -> None:
        self.source = source
        self.reader = reader
        self.extractor = extractor
        self.config = config
        self.state = PlateAnalysisState.IDLE
        self.last_result: PlateFrameResult | None = None
        self.error = ""
        self._plate_batch_id = ""
        self._source_id = source.source_id
        self._readings: list[PlateReadingCandidate] = []
        self._warnings: list[str] = []
        self._dedup: OrderedDict[str, _DedupEntry] = OrderedDict()
        self._last_timestamp_seconds = 0.0

    @property
    def readings(self) -> tuple[PlateReadingCandidate, ...]:
        return tuple(self._readings)

    @property
    def plate_batch_id(self) -> str:
        return self._plate_batch_id

    @property
    def dedup_entry_count(self) -> int:
        return len(self._dedup)

    def start(self) -> SourceInfo:
        if self.state is not PlateAnalysisState.IDLE:
            raise RuntimeError("La sesión OCR debe estar en IDLE para iniciar.")
        try:
            if not self.source.is_open():
                self.source.open()
            info = self.source.source_info()
            self._source_id = self.config.source_id or info.source_id
            self._plate_batch_id = f"plate:{uuid4().hex}"
            self.state = PlateAnalysisState.RUNNING
            self.error = ""
            return info
        except Exception as exc:
            self._fail(exc)
            raise

    def pause(self) -> None:
        if self.state is PlateAnalysisState.RUNNING:
            self.state = PlateAnalysisState.PAUSED

    def resume(self) -> None:
        if self.state is PlateAnalysisState.PAUSED:
            self.state = PlateAnalysisState.RUNNING

    def process_next(self) -> PlateFrameResult | None:
        if self.state is PlateAnalysisState.PAUSED:
            return self.last_result
        if self.state is not PlateAnalysisState.RUNNING:
            return None
        try:
            frame_result = self.source.read()
            if not frame_result.success or frame_result.frame is None:
                self.source.close()
                self.state = PlateAnalysisState.FINISHED
                self.last_result = PlateFrameResult(
                    source_id=self._source_id,
                    frame_index=max(0, frame_result.frame_number),
                    timestamp_seconds=max(
                        self._last_timestamp_seconds, frame_result.timestamp_ms / 1000.0
                    ),
                    candidate_count=0,
                    readings=(),
                    warnings=("Fin de la fuente OCR.",),
                    end_of_source=True,
                )
                return self.last_result

            frame_index = max(0, frame_result.frame_number)
            timestamp_seconds = max(
                self._last_timestamp_seconds,
                0.0,
                frame_result.timestamp_ms / 1000.0,
            )
            self._last_timestamp_seconds = max(
                self._last_timestamp_seconds, timestamp_seconds
            )
            regions: tuple[PlateRegion, ...] = ()
            emitted: list[PlateReadingCandidate] = []
            if (frame_index - 1) % self.config.every_n_frames == 0:
                regions = self.extractor.extract(frame_result.frame)
                for region in regions:
                    result = self.reader.detect_and_read(frame_result.frame, region.bbox)
                    candidate = self._normalize_result(
                        result,
                        frame_index=frame_index,
                        timestamp_seconds=timestamp_seconds,
                        region=region,
                    )
                    if candidate is None:
                        continue
                    accepted = self._deduplicate(candidate)
                    if accepted is not None:
                        emitted.append(accepted)
            roi_bbox = regions[0].bbox if regions else None
            self.last_result = PlateFrameResult(
                source_id=self._source_id,
                frame_index=frame_index,
                timestamp_seconds=timestamp_seconds,
                candidate_count=len(regions),
                readings=tuple(emitted),
                warnings=(),
                end_of_source=False,
                frame=frame_result.frame.copy(),
                roi_bbox=roi_bbox,
            )
            return self.last_result
        except Exception as exc:
            self._fail(exc)
            self.last_result = PlateFrameResult(
                source_id=self._source_id,
                frame_index=self.last_result.frame_index if self.last_result else 0,
                timestamp_seconds=self._last_timestamp_seconds,
                candidate_count=0,
                readings=(),
                warnings=(self.error,),
                end_of_source=True,
            )
            return self.last_result

    def finish(self) -> PlateBatchResult:
        self.source.close()
        if self.state is not PlateAnalysisState.ERROR:
            self.state = PlateAnalysisState.FINISHED
        return self.batch_result()

    def reset(self) -> None:
        self.source.close()
        self._clear_runtime_state()
        self.state = PlateAnalysisState.IDLE

    def change_source(self, source: FrameSource) -> None:
        self.source.close()
        self.source = source
        self._source_id = source.source_id
        self._clear_runtime_state()
        self.state = PlateAnalysisState.IDLE

    def close(self) -> None:
        self.source.close()
        if self.state not in {PlateAnalysisState.IDLE, PlateAnalysisState.ERROR}:
            self.state = PlateAnalysisState.FINISHED

    def batch_result(self) -> PlateBatchResult:
        batch_id = self._plate_batch_id or f"plate:{uuid4().hex}"
        return PlateBatchResult(
            plate_batch_id=batch_id,
            monitoring_point_id=self.config.monitoring_point_id,
            source_id=self._source_id,
            started_at_source_seconds=0.0,
            ended_at_source_seconds=self._last_timestamp_seconds,
            readings=self.readings,
            warnings=tuple(self._warnings),
            state=self.state,
        )

    def _normalize_result(
        self,
        result: PlateResult | None,
        *,
        frame_index: int,
        timestamp_seconds: float,
        region: PlateRegion,
    ) -> PlateReadingCandidate | None:
        if result is None:
            return None
        raw_text = result.text_raw.strip() if isinstance(result.text_raw, str) else ""
        normalized_text = re.sub(r"[^A-Z0-9]", "", raw_text.upper())
        if not normalized_text:
            return None
        try:
            confidence = float(result.confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        if not math.isfinite(confidence):
            confidence = 0.0
        confidence = min(1.0, max(0.0, confidence))
        return PlateReadingCandidate(
            reading_id=f"plate-reading:{uuid4().hex}",
            source_id=self._source_id,
            frame_index=frame_index,
            timestamp_seconds=timestamp_seconds,
            raw_text=raw_text,
            normalized_text=normalized_text,
            confidence=confidence,
            crop_reference=region.reference,
            direction=region.direction,
            lane=region.lane,
            status=PlateReadingStatus.PENDING,
            origin=self.config.origin,
        )

    def _deduplicate(
        self, candidate: PlateReadingCandidate
    ) -> PlateReadingCandidate | None:
        region = candidate.crop_reference or "no-region"
        key = f"{candidate.source_id}|{candidate.normalized_text}|{region}"
        previous = self._dedup.get(key)
        if (
            previous is not None
            and candidate.timestamp_seconds - previous.timestamp_seconds
            <= self.config.dedup_window_seconds
        ):
            self._dedup[key] = _DedupEntry(
                candidate.timestamp_seconds, previous.reading_id
            )
            self._dedup.move_to_end(key)
            existing_index = next(
                (
                    index
                    for index, reading in enumerate(self._readings)
                    if reading.reading_id == previous.reading_id
                ),
                None,
            )
            if existing_index is None:
                return None
            existing = self._readings[existing_index]
            if candidate.confidence <= existing.confidence:
                return None
            replacement = PlateReadingCandidate(
                reading_id=existing.reading_id,
                source_id=candidate.source_id,
                frame_index=candidate.frame_index,
                timestamp_seconds=candidate.timestamp_seconds,
                raw_text=candidate.raw_text,
                normalized_text=candidate.normalized_text,
                confidence=candidate.confidence,
                crop_reference=candidate.crop_reference,
                direction=candidate.direction,
                lane=candidate.lane,
                status=candidate.status,
                origin=candidate.origin,
                reviewed=candidate.reviewed,
            )
            self._readings[existing_index] = replacement
            return replacement

        if len(self._readings) >= self.config.max_batch_readings:
            warning = "Se alcanzó el límite de lecturas del lote OCR."
            if warning not in self._warnings:
                self._warnings.append(warning)
            return None
        self._readings.append(candidate)
        self._dedup[key] = _DedupEntry(
            candidate.timestamp_seconds, candidate.reading_id
        )
        self._dedup.move_to_end(key)
        while len(self._dedup) > self.config.max_dedup_entries:
            self._dedup.popitem(last=False)
        return candidate

    def _fail(self, exc: Exception) -> None:
        self.error = str(exc) or exc.__class__.__name__
        self._warnings.append(self.error)
        self.source.close()
        self.state = PlateAnalysisState.ERROR

    def _clear_runtime_state(self) -> None:
        self.last_result = None
        self.error = ""
        self._plate_batch_id = ""
        self._readings.clear()
        self._warnings.clear()
        self._dedup.clear()
        self._last_timestamp_seconds = 0.0


__all__ = [
    "NormalizedPlateRoi",
    "NormalizedRoiExtractor",
    "PlateAnalysisConfig",
    "PlateAnalysisController",
    "PlateCandidateExtractor",
    "PlateRegion",
]
