"""Agregación temporal neutral de resultados de análisis para congestión."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from math import isfinite
from typing import Any, Mapping, Protocol

from pavement_intelligence.domain.traffic.congestion import CongestionInput


class FrameAnalysisLike(Protocol):
    timestamp_seconds: float
    source_type: str
    crossing_events: tuple[Any, ...]
    direction_counts: Mapping[Any, int]
    vehicles_in_scene: int
    end_of_source: bool


@dataclass(frozen=True)
class CongestionAggregationConfig:
    window_seconds: float = 60.0
    scene_noise_deadband: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.window_seconds, (int, float)) or isinstance(self.window_seconds, bool):
            raise TypeError("window_seconds debe ser numérico.")
        if not isfinite(float(self.window_seconds)) or self.window_seconds <= 0:
            raise ValueError("window_seconds debe ser finito y mayor que cero.")
        if (
            isinstance(self.scene_noise_deadband, bool)
            or not isinstance(self.scene_noise_deadband, int)
            or self.scene_noise_deadband < 0
        ):
            raise ValueError("scene_noise_deadband debe ser un entero no negativo.")


class CongestionIntervalAggregator:
    """Ventana deslizante determinista, sin reloj, UI, visión ni escritura."""

    def __init__(self, config: CongestionAggregationConfig | None = None):
        self.config = config or CongestionAggregationConfig()
        self.reset()

    def reset(self) -> None:
        self._events: deque[tuple[float, str, int | str]] = deque()
        self._seen_events: dict[str, float] = {}
        self._source_id: str | None = None
        self._monitoring_point_id: str | None = None
        self._last_seen_timestamp: float | None = None
        self._last_valid_timestamp: float | None = None
        self._last_scene: int | None = None
        self._observation_duration = 0.0
        self._sample_count = 0
        self._last_output: CongestionInput | None = None

    @property
    def last_output(self) -> CongestionInput | None:
        return self._last_output

    @property
    def retained_event_count(self) -> int:
        return len(self._events)

    @property
    def deduplication_size(self) -> int:
        return len(self._seen_events)

    def add(
        self,
        result: FrameAnalysisLike,
        *,
        source_id: str,
        monitoring_point_id: str | None = None,
        is_paused: bool = False,
    ) -> CongestionInput | None:
        timestamp = self._validate_result(result, source_id, monitoring_point_id, is_paused)
        self._bind_source(source_id, monitoring_point_id)

        if self._last_seen_timestamp is not None and timestamp < self._last_seen_timestamp:
            raise ValueError("timestamp_seconds no puede retroceder; use reset().")

        if is_paused:
            self._last_seen_timestamp = timestamp
            return replace(self._last_output, is_paused=True) if self._last_output is not None else None

        if result.end_of_source:
            self._last_seen_timestamp = timestamp
            return self._last_output

        delta_seconds = 0.0 if self._last_seen_timestamp is None else timestamp - self._last_seen_timestamp
        self._observation_duration += delta_seconds
        self._sample_count += 1

        accumulation = self._accumulation(result.vehicles_in_scene, timestamp)
        self._prune(timestamp)
        self._add_events(result.crossing_events, timestamp)
        self._prune(timestamp)

        effective_window = min(self.config.window_seconds, self._observation_duration)
        flow = len(self._events) * 60.0 / effective_window if effective_window > 0 else 0.0
        directions: dict[int | str, int] = {}
        for _, _, direction in self._events:
            directions[direction] = directions.get(direction, 0) + 1

        output = CongestionInput(
            timestamp_seconds=timestamp,
            observation_duration_seconds=self._observation_duration,
            sample_count=self._sample_count,
            vehicles_in_scene=result.vehicles_in_scene,
            vehicles_per_minute=flow,
            accumulation_delta=accumulation,
            direction_counts=directions,
            is_paused=False,
            monitoring_point_id=monitoring_point_id,
        )
        self._last_seen_timestamp = timestamp
        self._last_valid_timestamp = timestamp
        self._last_scene = result.vehicles_in_scene
        self._last_output = output
        return output

    def _bind_source(self, source_id: str, monitoring_point_id: str | None) -> None:
        if self._source_id is None:
            self._source_id = source_id
            self._monitoring_point_id = monitoring_point_id
            return
        if source_id != self._source_id or monitoring_point_id != self._monitoring_point_id:
            raise ValueError("La fuente o el punto cambió; invoque reset() antes de mezclar secuencias.")

    def _validate_result(
        self,
        result: FrameAnalysisLike,
        source_id: str,
        monitoring_point_id: str | None,
        is_paused: bool,
    ) -> float:
        if result is None or not hasattr(result, "timestamp_seconds"):
            raise ValueError("El resultado requiere timestamp_seconds.")
        timestamp = result.timestamp_seconds
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            raise TypeError("timestamp_seconds debe ser numérico.")
        if not isfinite(float(timestamp)) or timestamp < 0:
            raise ValueError("timestamp_seconds debe ser finito y no negativo.")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id debe ser una cadena no vacía.")
        if monitoring_point_id is not None and not monitoring_point_id.strip():
            raise ValueError("monitoring_point_id no puede estar vacío.")
        if not isinstance(is_paused, bool):
            raise TypeError("is_paused debe ser booleano.")
        scene = result.vehicles_in_scene
        if isinstance(scene, bool) or not isinstance(scene, int) or scene < 0:
            raise ValueError("vehicles_in_scene debe ser un entero no negativo.")
        counts = dict(result.direction_counts)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values()):
            raise ValueError("direction_counts no admite conteos negativos o no enteros.")
        return float(timestamp)

    def _event_key_and_direction(self, event: Any) -> tuple[str, int | str]:
        event_id = event.get("event_id") if isinstance(event, Mapping) else getattr(event, "event_id", None)
        direction = event.get("direction") if isinstance(event, Mapping) else getattr(event, "direction", None)
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("Cada evento de cruce requiere event_id estable.")
        if direction is None or isinstance(direction, str) and not direction.strip():
            raise ValueError("Cada evento de cruce requiere una dirección no vacía.")
        if isinstance(direction, bool) or not isinstance(direction, (int, str)):
            raise TypeError("La dirección debe ser un entero o nombre neutral.")
        return event_id.strip(), direction

    def _add_events(self, events: tuple[Any, ...], timestamp: float) -> None:
        pending = []
        for event in events:
            key, direction = self._event_key_and_direction(event)
            if key not in self._seen_events:
                pending.append((timestamp, key, direction))
                self._seen_events[key] = timestamp
        self._events.extend(pending)

    def _prune(self, timestamp: float) -> None:
        cutoff = timestamp - self.config.window_seconds
        while self._events and self._events[0][0] < cutoff:
            _, key, _ = self._events.popleft()
            self._seen_events.pop(key, None)

    def _accumulation(self, scene: int, timestamp: float) -> float:
        if self._last_scene is None or self._last_valid_timestamp is None:
            return 0.0
        delta_seconds = timestamp - self._last_valid_timestamp
        scene_change = scene - self._last_scene
        if delta_seconds <= 0 or abs(scene_change) <= self.config.scene_noise_deadband:
            return 0.0
        return scene_change * 60.0 / delta_seconds
