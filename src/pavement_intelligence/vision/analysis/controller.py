"""Controlador de un frame por iteración sobre el VisionPipeline existente."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Callable, Mapping, Sequence

import numpy as np

from pavement_intelligence.vision.capture import FrameSource, SourceInfo
from pavement_intelligence.vision.pipeline import TrafficEvent, VisionPipeline


class AnalysisState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class CongestionThresholds:
    minimum_seconds: float = 5.0
    moderate_flow_veh_min: float = 20.0
    high_flow_veh_min: float = 40.0
    moderate_vehicles_in_scene: int = 8
    high_vehicles_in_scene: int = 16


def classify_congestion(
    flow_veh_min: float,
    vehicles_in_scene: int,
    elapsed_seconds: float,
    config: CongestionThresholds = CongestionThresholds(),
) -> str:
    """Estimación operativa; no representa un nivel de servicio normativo."""
    if elapsed_seconds < config.minimum_seconds:
        return "INSUFFICIENT_DATA"
    if flow_veh_min >= config.high_flow_veh_min or vehicles_in_scene >= config.high_vehicles_in_scene:
        return "HIGH"
    if flow_veh_min >= config.moderate_flow_veh_min or vehicles_in_scene >= config.moderate_vehicles_in_scene:
        return "MODERATE"
    return "NORMAL"


@dataclass(frozen=True)
class FrameAnalysisResult:
    frame_index: int
    timestamp_seconds: float
    source_type: str
    annotated_frame: np.ndarray | None
    detections: tuple[Mapping[str, object], ...]
    active_tracks: tuple[int, ...]
    crossing_events: tuple[TrafficEvent, ...]
    category_counts: Mapping[str, int]
    direction_counts: Mapping[int, int]
    vehicles_in_scene: int
    total_crossings: int
    processing_fps: float
    warnings: tuple[str, ...]
    end_of_source: bool
    congestion: str


class TrafficAnalysisController:
    """Coordina fuente y pipeline sin estado de UI ni persistencia en disco."""

    def __init__(self, source: FrameSource, pipeline_factory: Callable[[], VisionPipeline]):
        self.source = source
        self._pipeline_factory = pipeline_factory
        self.pipeline: VisionPipeline | None = None
        self.state = AnalysisState.IDLE
        self.last_result: FrameAnalysisResult | None = None
        self.error = ""

    @property
    def events(self) -> tuple[TrafficEvent, ...]:
        return tuple(self.pipeline.events) if self.pipeline is not None else ()

    def start(self) -> SourceInfo:
        try:
            if not self.source.is_open():
                self.source.open()
            if self.pipeline is None:
                self.pipeline = self._pipeline_factory()
            self.state = AnalysisState.RUNNING
            self.error = ""
            return self.source.source_info()
        except Exception as exc:
            self.error = str(exc)
            self.state = AnalysisState.ERROR
            self.source.close()
            raise

    def pause(self) -> None:
        if self.state is AnalysisState.RUNNING:
            self.state = AnalysisState.PAUSED

    def resume(self) -> None:
        if self.state is AnalysisState.PAUSED:
            self.state = AnalysisState.RUNNING

    def reset(self) -> SourceInfo:
        self.source.close()
        self.pipeline = None
        self.last_result = None
        self.error = ""
        return self.start()

    def process_next(self) -> FrameAnalysisResult | None:
        if self.state is AnalysisState.PAUSED:
            return self.last_result
        if self.state is not AnalysisState.RUNNING:
            return None
        started = perf_counter()
        try:
            frame_result = self.source.read()
            info = self.source.source_info()
            assert self.pipeline is not None
            if not frame_result.success or frame_result.frame is None:
                self.state = AnalysisState.FINISHED
                self.source.close()
                self.last_result = self._result(None, (), (), 0.0, True, ("Fin de la fuente.",), info)
                return self.last_result
            diagnostics_start = len(self.pipeline.diagnostics)
            annotated, new_events = self.pipeline.process_frame(
                frame_result.frame,
                frame_result.frame_number,
                info.fps,
                frame_result.source_id,
            )
            elapsed = max(perf_counter() - started, 1e-9)
            diagnostics = tuple(self.pipeline.diagnostics[diagnostics_start:])
            self.last_result = self._result(
                annotated, diagnostics, tuple(new_events), 1.0 / elapsed, False, (), info,
                frame_result.timestamp_ms / 1000.0,
            )
            return self.last_result
        except Exception as exc:
            self.error = str(exc)
            self.state = AnalysisState.ERROR
            self.source.close()
            info = self.source.source_info()
            self.last_result = self._result(None, (), (), 0.0, True, (self.error,), info)
            return self.last_result

    def _result(
        self,
        frame: np.ndarray | None,
        detections: Sequence[Mapping[str, object]],
        new_events: tuple[TrafficEvent, ...],
        processing_fps: float,
        end_of_source: bool,
        warnings: tuple[str, ...],
        info: SourceInfo,
        timestamp_seconds: float | None = None,
    ) -> FrameAnalysisResult:
        assert self.pipeline is not None
        categories = Counter(event.category for event in self.pipeline.events)
        directions = Counter(event.direction for event in self.pipeline.events)
        active_tracks = tuple(sorted({
            int(item["track_id"]) for item in detections
            if isinstance(item.get("track_id"), int) and int(item["track_id"]) >= 0
        }))
        timestamp = timestamp_seconds if timestamp_seconds is not None else (
            info.position / info.fps if info.fps > 0 else 0.0
        )
        flow = len(self.pipeline.events) / timestamp * 60 if timestamp > 0 else 0.0
        return FrameAnalysisResult(
            frame_index=info.position,
            timestamp_seconds=timestamp,
            source_type=info.source_type,
            annotated_frame=frame,
            detections=tuple(detections),
            active_tracks=active_tracks,
            crossing_events=new_events,
            category_counts=dict(categories),
            direction_counts=dict(directions),
            vehicles_in_scene=len(active_tracks),
            total_crossings=len(self.pipeline.events),
            processing_fps=processing_fps,
            warnings=warnings,
            end_of_source=end_of_source,
            congestion=classify_congestion(flow, len(active_tracks), timestamp),
        )

    def finish(self) -> tuple[TrafficEvent, ...]:
        try:
            return self.events
        finally:
            self.source.close()
            if self.state is not AnalysisState.ERROR:
                self.state = AnalysisState.FINISHED

    def close(self) -> None:
        self.finish()
