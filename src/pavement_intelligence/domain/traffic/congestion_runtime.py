"""Coordinación neutral entre resultados de frame y estimación de congestión."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from pavement_intelligence.domain.traffic.congestion import (
    CongestionAlert,
    CongestionAssessment,
    CongestionEngine,
    CongestionEvidence,
    CongestionLevel,
)
from pavement_intelligence.domain.traffic.congestion_aggregation import (
    CongestionIntervalAggregator,
)


class FrameAnalysisResultLike(Protocol):
    """Parte del contrato de FrameAnalysisResult que consume este adaptador."""

    timestamp_seconds: float
    source_type: str
    crossing_events: tuple[Any, ...]
    direction_counts: Mapping[Any, int]
    vehicles_in_scene: int
    warnings: tuple[str, ...]
    end_of_source: bool


class CongestionRuntimeState(str, Enum):
    IDLE = "IDLE"
    WARMING_UP = "WARMING_UP"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class TrafficCongestionSnapshot:
    """Vista inmutable y libre de UI de la estimación operativa actual."""

    timestamp_seconds: float
    source_id: str
    state: CongestionRuntimeState
    level: CongestionLevel
    previous_level: CongestionLevel
    vehicles_per_minute: float
    vehicles_in_scene: int
    accumulation_delta: float
    direction_counts: Mapping[int | str, int]
    observation_duration_seconds: float
    sample_count: int
    candidate_level: CongestionLevel | None
    candidate_elapsed_seconds: float
    alert: CongestionAlert | None
    evidence: CongestionEvidence | None
    warnings: tuple[str, ...]
    is_paused: bool
    is_final: bool
    origin: str = "OPERATIONAL_ESTIMATE"
    normative: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "direction_counts", MappingProxyType(dict(self.direction_counts))
        )
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True)
class _PausedFrame:
    timestamp_seconds: float
    source_type: str
    crossing_events: tuple[Any, ...]
    direction_counts: Mapping[int | str, int]
    vehicles_in_scene: int
    warnings: tuple[str, ...] = ()
    end_of_source: bool = False


class TrafficCongestionCoordinator:
    """Coordina un agregador y un motor inyectados, sin UI ni persistencia."""

    def __init__(
        self,
        aggregator: CongestionIntervalAggregator,
        engine: CongestionEngine,
        *,
        monitoring_point_id: str | None = None,
    ) -> None:
        if aggregator is None or not callable(getattr(aggregator, "add", None)):
            raise TypeError("aggregator debe implementar add() y reset().")
        if not callable(getattr(aggregator, "reset", None)):
            raise TypeError("aggregator debe implementar add() y reset().")
        if engine is None or not callable(getattr(engine, "evaluate", None)):
            raise TypeError("engine debe implementar evaluate() y reset().")
        if not callable(getattr(engine, "reset", None)):
            raise TypeError("engine debe implementar evaluate() y reset().")
        if monitoring_point_id is not None:
            if (
                not isinstance(monitoring_point_id, str)
                or not monitoring_point_id.strip()
            ):
                raise ValueError("monitoring_point_id no puede estar vacío.")
            monitoring_point_id = monitoring_point_id.strip()
        self._aggregator = aggregator
        self._engine = engine
        self._monitoring_point_id = monitoring_point_id
        self._state = CongestionRuntimeState.IDLE
        self._source_id: str | None = None
        self._source_type = "unknown"
        self._last_snapshot: TrafficCongestionSnapshot | None = None
        self._error_message = ""

    @property
    def state(self) -> CongestionRuntimeState:
        return self._state

    @property
    def source_id(self) -> str | None:
        return self._source_id

    @property
    def last_snapshot(self) -> TrafficCongestionSnapshot | None:
        return self._last_snapshot

    @property
    def error_message(self) -> str:
        return self._error_message

    def set_source(self, source_id: str) -> None:
        source_id = self._validate_source_id(source_id)
        if self._source_id == source_id:
            return
        if self._source_id is not None or self._last_snapshot is not None:
            raise RuntimeError(
                "La fuente cambió; invoque reset() antes de iniciar otro lote."
            )
        if self._state is not CongestionRuntimeState.IDLE:
            raise RuntimeError("Solo se puede establecer una fuente en estado IDLE.")
        self._source_id = source_id

    def process_frame_result(
        self, result: FrameAnalysisResultLike
    ) -> TrafficCongestionSnapshot:
        if self._state is CongestionRuntimeState.ERROR:
            raise RuntimeError("El coordinador está en ERROR; invoque reset().")
        if self._state is CongestionRuntimeState.FINISHED:
            raise RuntimeError("El lote ya finalizó; invoque reset().")
        if self._source_id is None:
            raise RuntimeError("Debe establecer source_id antes de procesar.")
        if self._state is CongestionRuntimeState.PAUSED:
            return self.process_paused_state(result)

        try:
            self._validate_result(result)
            self._source_type = result.source_type
            sample = self._aggregator.add(
                result,
                source_id=self._source_id,
                monitoring_point_id=self._monitoring_point_id,
            )
            if result.end_of_source:
                return self._finish_from_result(result)
            if sample is None:
                raise RuntimeError(
                    "El agregador no produjo una muestra para un resultado válido."
                )
            assessment = self._engine.evaluate(sample)
            next_state = (
                CongestionRuntimeState.WARMING_UP
                if assessment.level is CongestionLevel.INSUFFICIENT_DATA
                else CongestionRuntimeState.ACTIVE
            )
            snapshot = self._snapshot(sample, assessment, result.warnings, next_state)
            self._state = next_state
            self._last_snapshot = snapshot
            self._error_message = ""
            return snapshot
        except Exception as exc:
            self._fail(exc)
            raise

    def pause(
        self, timestamp_seconds: float | None = None
    ) -> TrafficCongestionSnapshot:
        if self._state is CongestionRuntimeState.PAUSED:
            assert self._last_snapshot is not None
            return self._last_snapshot
        if self._state not in (
            CongestionRuntimeState.WARMING_UP,
            CongestionRuntimeState.ACTIVE,
        ):
            raise RuntimeError("Solo se puede pausar un lote iniciado.")
        if timestamp_seconds is not None:
            self._touch_paused_timestamp(timestamp_seconds)
        assert self._last_snapshot is not None
        self._state = CongestionRuntimeState.PAUSED
        self._last_snapshot = replace(
            self._last_snapshot,
            state=CongestionRuntimeState.PAUSED,
            is_paused=True,
        )
        return self._last_snapshot

    def process_paused_state(
        self, result: FrameAnalysisResultLike | None = None
    ) -> TrafficCongestionSnapshot:
        if (
            self._state is not CongestionRuntimeState.PAUSED
            or self._last_snapshot is None
        ):
            raise RuntimeError("El coordinador no está pausado.")
        if result is not None:
            try:
                self._validate_result(result)
                if result.end_of_source:
                    return self._finish_from_result(result)
                self._source_type = result.source_type
                assert self._source_id is not None
                self._aggregator.add(
                    result,
                    source_id=self._source_id,
                    monitoring_point_id=self._monitoring_point_id,
                    is_paused=True,
                )
            except Exception as exc:
                self._fail(exc)
                raise
        return self._last_snapshot

    def resume(
        self, timestamp_seconds: float | None = None
    ) -> TrafficCongestionSnapshot:
        if (
            self._state
            in (
                CongestionRuntimeState.WARMING_UP,
                CongestionRuntimeState.ACTIVE,
            )
            and self._last_snapshot is not None
        ):
            return self._last_snapshot
        if (
            self._state is not CongestionRuntimeState.PAUSED
            or self._last_snapshot is None
        ):
            raise RuntimeError("Solo se puede continuar un lote pausado.")
        if timestamp_seconds is not None:
            self._touch_paused_timestamp(timestamp_seconds)
        resumed_state = (
            CongestionRuntimeState.WARMING_UP
            if self._last_snapshot.level is CongestionLevel.INSUFFICIENT_DATA
            else CongestionRuntimeState.ACTIVE
        )
        self._state = resumed_state
        self._last_snapshot = replace(
            self._last_snapshot,
            state=resumed_state,
            is_paused=False,
        )
        return self._last_snapshot

    def finish(
        self, timestamp_seconds: float | None = None
    ) -> TrafficCongestionSnapshot:
        if self._state is CongestionRuntimeState.ERROR:
            raise RuntimeError("El coordinador está en ERROR; invoque reset().")
        if (
            self._state is CongestionRuntimeState.FINISHED
            and self._last_snapshot is not None
        ):
            return self._last_snapshot
        if self._source_id is None:
            raise RuntimeError("No existe una fuente que finalizar.")
        if timestamp_seconds is not None:
            self._validate_timestamp(timestamp_seconds)
        if self._last_snapshot is None:
            timestamp = float(timestamp_seconds or 0.0)
            snapshot = TrafficCongestionSnapshot(
                timestamp_seconds=timestamp,
                source_id=self._source_id,
                state=CongestionRuntimeState.FINISHED,
                level=CongestionLevel.INSUFFICIENT_DATA,
                previous_level=CongestionLevel.INSUFFICIENT_DATA,
                vehicles_per_minute=0.0,
                vehicles_in_scene=0,
                accumulation_delta=0.0,
                direction_counts={},
                observation_duration_seconds=0.0,
                sample_count=0,
                candidate_level=None,
                candidate_elapsed_seconds=0.0,
                alert=None,
                evidence=None,
                warnings=("Fin de la fuente sin muestras válidas.",),
                is_paused=False,
                is_final=True,
            )
        else:
            snapshot = replace(
                self._last_snapshot,
                state=CongestionRuntimeState.FINISHED,
                is_paused=False,
                is_final=True,
            )
        self._state = CongestionRuntimeState.FINISHED
        self._last_snapshot = snapshot
        return snapshot

    def reset(self) -> None:
        self._aggregator.reset()
        self._engine.reset()
        self._state = CongestionRuntimeState.IDLE
        self._source_id = None
        self._source_type = "unknown"
        self._last_snapshot = None
        self._error_message = ""

    def _snapshot(
        self,
        sample: Any,
        assessment: CongestionAssessment,
        result_warnings: tuple[str, ...],
        state: CongestionRuntimeState,
    ) -> TrafficCongestionSnapshot:
        evidence = assessment.evidence
        warnings = tuple(result_warnings) + tuple(evidence.warnings)
        candidate = CongestionLevel.HIGH if evidence.high_candidate_pending else None
        assert self._source_id is not None
        return TrafficCongestionSnapshot(
            timestamp_seconds=sample.timestamp_seconds,
            source_id=self._source_id,
            state=state,
            level=assessment.level,
            previous_level=assessment.previous_level,
            vehicles_per_minute=sample.vehicles_per_minute,
            vehicles_in_scene=sample.vehicles_in_scene,
            accumulation_delta=sample.accumulation_delta,
            direction_counts=sample.direction_counts,
            observation_duration_seconds=sample.observation_duration_seconds,
            sample_count=sample.sample_count,
            candidate_level=candidate,
            candidate_elapsed_seconds=evidence.candidate_elapsed_seconds,
            alert=assessment.alert,
            evidence=evidence,
            warnings=warnings,
            is_paused=False,
            is_final=False,
        )

    def _touch_paused_timestamp(self, timestamp_seconds: float) -> None:
        timestamp = self._validate_timestamp(timestamp_seconds)
        assert self._last_snapshot is not None and self._source_id is not None
        paused = _PausedFrame(
            timestamp_seconds=timestamp,
            source_type=self._source_type,
            crossing_events=(),
            direction_counts=self._last_snapshot.direction_counts,
            vehicles_in_scene=self._last_snapshot.vehicles_in_scene,
        )
        self._aggregator.add(
            paused,
            source_id=self._source_id,
            monitoring_point_id=self._monitoring_point_id,
            is_paused=True,
        )

    def _finish_from_result(
        self, result: FrameAnalysisResultLike
    ) -> TrafficCongestionSnapshot:
        final = self.finish(timestamp_seconds=float(result.timestamp_seconds))
        terminal_warnings = tuple(result.warnings)
        if terminal_warnings:
            final = replace(
                final,
                warnings=tuple(final.warnings) + terminal_warnings,
            )
            self._last_snapshot = final
        return final

    @staticmethod
    def _validate_source_id(source_id: str) -> str:
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id debe ser una cadena no vacía.")
        return source_id.strip()

    @classmethod
    def _validate_result(cls, result: FrameAnalysisResultLike) -> None:
        if result is None:
            raise ValueError("result no puede ser nulo.")
        required = (
            "timestamp_seconds",
            "source_type",
            "crossing_events",
            "direction_counts",
            "vehicles_in_scene",
            "warnings",
            "end_of_source",
        )
        if any(not hasattr(result, field) for field in required):
            raise TypeError("result no cumple el contrato FrameAnalysisResult.")
        cls._validate_timestamp(result.timestamp_seconds)
        if not isinstance(result.source_type, str) or not result.source_type.strip():
            raise ValueError("source_type debe ser una cadena no vacía.")
        if not isinstance(result.crossing_events, tuple):
            raise TypeError("crossing_events debe ser una tupla.")
        if not isinstance(result.direction_counts, Mapping):
            raise TypeError("direction_counts debe ser un mapping.")
        if not isinstance(result.warnings, tuple) or any(
            not isinstance(item, str) for item in result.warnings
        ):
            raise TypeError("warnings debe ser una tupla de cadenas.")
        if not isinstance(result.end_of_source, bool):
            raise TypeError("end_of_source debe ser booleano.")

    @staticmethod
    def _validate_timestamp(timestamp_seconds: float) -> float:
        if isinstance(timestamp_seconds, bool) or not isinstance(
            timestamp_seconds, (int, float)
        ):
            raise TypeError("timestamp_seconds debe ser numérico.")
        if not isfinite(float(timestamp_seconds)) or timestamp_seconds < 0:
            raise ValueError("timestamp_seconds debe ser finito y no negativo.")
        return float(timestamp_seconds)

    def _fail(self, exc: Exception) -> None:
        self._state = CongestionRuntimeState.ERROR
        self._error_message = str(exc) or exc.__class__.__name__


__all__ = [
    "CongestionRuntimeState",
    "TrafficCongestionCoordinator",
    "TrafficCongestionSnapshot",
]
