"""Dominio neutral para estimación operativa, no normativa, de congestión."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite
from types import MappingProxyType
from typing import Mapping


DEMONSTRATIVE_CONFIGURATION_NOTICE = (
    "Configuración demostrativa inicial, pendiente de calibración por punto de monitoreo"
)


class CongestionLevel(str, Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NORMAL = "NORMAL"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


def _finite_non_negative(value: float | int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} debe ser numérico.")
    if not isfinite(float(value)) or value < 0:
        raise ValueError(f"{name} debe ser finito y no negativo.")


@dataclass(frozen=True)
class CongestionInput:
    timestamp_seconds: float
    observation_duration_seconds: float
    sample_count: int
    vehicles_in_scene: int
    vehicles_per_minute: float
    accumulation_delta: float
    direction_counts: Mapping[int | str, int]
    is_paused: bool = False
    monitoring_point_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("timestamp_seconds", "observation_duration_seconds", "vehicles_per_minute"):
            _finite_non_negative(getattr(self, name), name)
        for name in ("sample_count", "vehicles_in_scene"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} debe ser un entero no negativo.")
        if not isinstance(self.accumulation_delta, (int, float)) or isinstance(self.accumulation_delta, bool):
            raise TypeError("accumulation_delta debe ser numérico.")
        if not isfinite(float(self.accumulation_delta)):
            raise ValueError("accumulation_delta debe ser finito.")
        if self.observation_duration_seconds > self.timestamp_seconds:
            raise ValueError("La duración observada no puede superar el timestamp de la fuente.")
        if not isinstance(self.is_paused, bool):
            raise TypeError("is_paused debe ser booleano.")
        if self.monitoring_point_id is not None and not self.monitoring_point_id.strip():
            raise ValueError("monitoring_point_id no puede estar vacío.")
        counts = dict(self.direction_counts)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values()):
            raise ValueError("direction_counts solo admite enteros no negativos.")
        object.__setattr__(self, "direction_counts", MappingProxyType(counts))


@dataclass(frozen=True)
class CongestionThresholds:
    minimum_observation_seconds: float = 10.0
    minimum_sample_count: int = 3
    moderate_scene_enter: int = 8
    moderate_scene_exit: int = 5
    high_scene_enter: int = 16
    high_scene_exit: int = 12
    moderate_flow_enter: float = 40.0
    moderate_flow_exit: float = 30.0
    high_flow_enter: float = 60.0
    high_flow_exit: float = 45.0
    moderate_accumulation_enter: float = 2.0
    moderate_accumulation_exit: float = 1.0
    high_accumulation_enter: float = 5.0
    high_accumulation_exit: float = 2.0
    high_confirmation_seconds: float = 15.0
    recovery_confirmation_seconds: float = 5.0
    configuration_notice: str = DEMONSTRATIVE_CONFIGURATION_NOTICE

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if name == "configuration_notice":
                if not value.strip():
                    raise ValueError("configuration_notice no puede estar vacío.")
            else:
                _finite_non_negative(value, name)
        if self.minimum_sample_count < 1:
            raise ValueError("minimum_sample_count debe ser al menos 1.")
        pairs = (
            (self.moderate_scene_exit, self.moderate_scene_enter, "scene moderate"),
            (self.high_scene_exit, self.high_scene_enter, "scene high"),
            (self.moderate_flow_exit, self.moderate_flow_enter, "flow moderate"),
            (self.high_flow_exit, self.high_flow_enter, "flow high"),
            (self.moderate_accumulation_exit, self.moderate_accumulation_enter, "accumulation moderate"),
            (self.high_accumulation_exit, self.high_accumulation_enter, "accumulation high"),
        )
        if any(exit_value > enter_value for exit_value, enter_value, _ in pairs):
            raise ValueError("Cada umbral de salida debe ser menor o igual al de entrada.")
        if self.high_scene_enter <= self.moderate_scene_enter:
            raise ValueError("high_scene_enter debe superar moderate_scene_enter.")
        if self.high_flow_enter <= self.moderate_flow_enter:
            raise ValueError("high_flow_enter debe superar moderate_flow_enter.")
        if self.high_accumulation_enter <= self.moderate_accumulation_enter:
            raise ValueError("high_accumulation_enter debe superar moderate_accumulation_enter.")


@dataclass(frozen=True)
class CongestionEvidence:
    previous_level: CongestionLevel
    resulting_level: CongestionLevel
    high_candidate_pending: bool
    candidate_elapsed_seconds: float
    observed_metrics: tuple[tuple[str, float | int], ...]
    active_rules: tuple[str, ...]
    compared_thresholds: tuple[tuple[str, float | int], ...]
    warnings: tuple[str, ...]
    sufficient_data: bool
    summary: str


@dataclass(frozen=True)
class CongestionAlert:
    alert_id: str
    level: CongestionLevel
    started_at_seconds: float
    confirmed_at_seconds: float
    monitoring_point_id: str | None
    message: str
    evidence: CongestionEvidence
    active: bool
    origin: str = "OPERATIONAL_ESTIMATE"
    normative: bool = False


@dataclass(frozen=True)
class CongestionAssessment:
    timestamp_seconds: float
    previous_level: CongestionLevel
    level: CongestionLevel
    evidence: CongestionEvidence
    alert: CongestionAlert | None = None
    alert_emitted: bool = False


class CongestionEngine:
    """Máquina determinista con histeresis y confirmación por tiempo observado."""

    def __init__(self, thresholds: CongestionThresholds | None = None):
        self.thresholds = thresholds or CongestionThresholds()
        self.reset()

    def reset(self) -> None:
        self._level = CongestionLevel.INSUFFICIENT_DATA
        self._last_timestamp: float | None = None
        self._last_observation_duration: float | None = None
        self._candidate_started_at: float | None = None
        self._candidate_elapsed = 0.0
        self._recovery_elapsed = 0.0
        self._active_alert: CongestionAlert | None = None
        self._last_evidence: CongestionEvidence | None = None

    @property
    def level(self) -> CongestionLevel:
        return self._level

    def evaluate(self, sample: CongestionInput) -> CongestionAssessment:
        self._validate_sequence(sample)
        previous = self._level
        observation_delta = self._observation_delta(sample)

        if sample.is_paused:
            evidence = self._evidence(
                sample, previous, (), ("PAUSED_NO_TIME_ADVANCE",),
                self._candidate_started_at is not None, self._candidate_elapsed,
                previous is not CongestionLevel.INSUFFICIENT_DATA,
                "Evaluación pausada; estado y temporizadores sin cambios.",
            )
            self._remember_time(sample)
            self._last_evidence = evidence
            return CongestionAssessment(sample.timestamp_seconds, previous, previous, evidence, self._active_alert)

        sufficient = (
            sample.observation_duration_seconds >= self.thresholds.minimum_observation_seconds
            and sample.sample_count >= self.thresholds.minimum_sample_count
        )
        if not sufficient:
            self._cancel_candidate()
            self._level = CongestionLevel.INSUFFICIENT_DATA
            reasons = []
            if sample.observation_duration_seconds < self.thresholds.minimum_observation_seconds:
                reasons.append(
                    f"{sample.observation_duration_seconds:.1f} de "
                    f"{self.thresholds.minimum_observation_seconds:.1f} segundos observados"
                )
            if sample.sample_count < self.thresholds.minimum_sample_count:
                reasons.append(f"{sample.sample_count} de {self.thresholds.minimum_sample_count} muestras")
            summary = "Datos insuficientes: " + "; ".join(reasons) + "."
            evidence = self._evidence(sample, previous, ("INSUFFICIENT_DATA",), (), False, 0.0, False, summary)
            self._remember_time(sample)
            self._last_evidence = evidence
            return CongestionAssessment(sample.timestamp_seconds, previous, self._level, evidence)

        rules = self._active_rules(sample)
        high_condition = "HIGH_SCENE_ACCUMULATION" in rules or "HIGH_ACCUMULATION_WITH_OCCUPANCY" in rules
        moderate_condition = any(rule.startswith("MODERATE_") for rule in rules) or high_condition
        alert: CongestionAlert | None = self._active_alert
        emitted = False

        if self._level is CongestionLevel.HIGH:
            recovered = self._high_exit(sample)
            self._recovery_elapsed = self._recovery_elapsed + observation_delta if recovered else 0.0
            if recovered and self._recovery_elapsed >= self.thresholds.recovery_confirmation_seconds:
                self._level = CongestionLevel.MODERATE
                self._recovery_elapsed = 0.0
                self._cancel_candidate()
                if self._active_alert is not None:
                    alert = CongestionAlert(**{**vars(self._active_alert), "active": False})
                    self._active_alert = None
        else:
            if high_condition:
                if self._candidate_started_at is None:
                    self._candidate_started_at = sample.timestamp_seconds
                    self._candidate_elapsed = 0.0
                else:
                    self._candidate_elapsed += observation_delta
                self._level = CongestionLevel.MODERATE
                if self._candidate_elapsed >= self.thresholds.high_confirmation_seconds:
                    self._level = CongestionLevel.HIGH
            else:
                self._cancel_candidate()
                if self._level in (CongestionLevel.INSUFFICIENT_DATA, CongestionLevel.NORMAL):
                    self._level = CongestionLevel.MODERATE if moderate_condition else CongestionLevel.NORMAL
                elif self._level is CongestionLevel.MODERATE and self._moderate_exit(sample):
                    self._level = CongestionLevel.NORMAL

        pending = self._candidate_started_at is not None and self._level is not CongestionLevel.HIGH
        summary = self._summary(sample, rules, pending)
        evidence = self._evidence(sample, previous, rules, (), pending, self._candidate_elapsed, True, summary)

        if self._level is CongestionLevel.HIGH and self._active_alert is None:
            alert_id = sha256(
                f"{sample.monitoring_point_id or 'unassigned'}:{self._candidate_started_at:.6f}".encode()
            ).hexdigest()[:16]
            alert = CongestionAlert(
                alert_id=alert_id,
                level=CongestionLevel.HIGH,
                started_at_seconds=float(self._candidate_started_at),
                confirmed_at_seconds=sample.timestamp_seconds,
                monitoring_point_id=sample.monitoring_point_id,
                message="Congestión alta confirmada; estimación operativa no normativa.",
                evidence=evidence,
                active=True,
            )
            self._active_alert = alert
            emitted = True

        self._remember_time(sample)
        self._last_evidence = evidence
        return CongestionAssessment(sample.timestamp_seconds, previous, self._level, evidence, alert, emitted)

    def _validate_sequence(self, sample: CongestionInput) -> None:
        if self._last_timestamp is not None and sample.timestamp_seconds < self._last_timestamp:
            raise ValueError("timestamp_seconds no puede retroceder.")
        if (
            self._last_observation_duration is not None
            and sample.observation_duration_seconds < self._last_observation_duration
        ):
            raise ValueError("observation_duration_seconds no puede retroceder; use reset().")
        if sample.is_paused and self._last_observation_duration is not None:
            if sample.observation_duration_seconds != self._last_observation_duration:
                raise ValueError("Una pausa no puede incrementar el tiempo válido de observación.")

    def _observation_delta(self, sample: CongestionInput) -> float:
        if self._last_observation_duration is None:
            return 0.0
        return sample.observation_duration_seconds - self._last_observation_duration

    def _remember_time(self, sample: CongestionInput) -> None:
        self._last_timestamp = sample.timestamp_seconds
        self._last_observation_duration = sample.observation_duration_seconds

    def _cancel_candidate(self) -> None:
        self._candidate_started_at = None
        self._candidate_elapsed = 0.0

    def _active_rules(self, sample: CongestionInput) -> tuple[str, ...]:
        t = self.thresholds
        rules = []
        if sample.vehicles_in_scene >= t.moderate_scene_enter:
            rules.append("MODERATE_SCENE")
        if sample.vehicles_per_minute >= t.moderate_flow_enter:
            rules.append("MODERATE_FLOW_HIGH_BUT_NOT_HIGH_ALONE")
        if sample.accumulation_delta >= t.moderate_accumulation_enter:
            rules.append("MODERATE_ACCUMULATION")
        if sample.vehicles_in_scene >= t.high_scene_enter and sample.accumulation_delta >= t.moderate_accumulation_enter:
            rules.append("HIGH_SCENE_ACCUMULATION")
        if sample.accumulation_delta >= t.high_accumulation_enter and sample.vehicles_in_scene >= t.moderate_scene_enter:
            rules.append("HIGH_ACCUMULATION_WITH_OCCUPANCY")
        if sample.vehicles_per_minute >= t.high_flow_enter:
            rules.append("HIGH_FLOW_SUPPORTING_ONLY")
        return tuple(rules)

    def _moderate_exit(self, sample: CongestionInput) -> bool:
        t = self.thresholds
        return (
            sample.vehicles_in_scene <= t.moderate_scene_exit
            and sample.vehicles_per_minute <= t.moderate_flow_exit
            and sample.accumulation_delta <= t.moderate_accumulation_exit
        )

    def _high_exit(self, sample: CongestionInput) -> bool:
        t = self.thresholds
        return (
            sample.vehicles_in_scene <= t.high_scene_exit
            and sample.vehicles_per_minute <= t.high_flow_exit
            and sample.accumulation_delta <= t.high_accumulation_exit
        )

    def _summary(self, sample: CongestionInput, rules: tuple[str, ...], pending: bool) -> str:
        if pending:
            return (
                "Congestión alta pendiente de confirmación: "
                f"{self._candidate_elapsed:.1f} de {self.thresholds.high_confirmation_seconds:.1f} segundos."
            )
        if self._level is CongestionLevel.HIGH:
            return "Congestión alta confirmada; estimación operativa no normativa."
        if self._level is CongestionLevel.MODERATE:
            causes = []
            if "MODERATE_SCENE" in rules:
                causes.append("ocupación visual elevada")
            if "MODERATE_ACCUMULATION" in rules:
                causes.append("acumulación positiva")
            if "MODERATE_FLOW_HIGH_BUT_NOT_HIGH_ALONE" in rules:
                causes.append("flujo alto")
            return "Estado moderado por " + (" y ".join(causes) or "histeresis operativa") + "."
        return "Condiciones operativas dentro de los umbrales demostrativos normales."

    def _evidence(
        self,
        sample: CongestionInput,
        previous: CongestionLevel,
        rules: tuple[str, ...],
        warnings: tuple[str, ...],
        pending: bool,
        elapsed: float,
        sufficient: bool,
        summary: str,
    ) -> CongestionEvidence:
        t = self.thresholds
        return CongestionEvidence(
            previous_level=previous,
            resulting_level=self._level,
            high_candidate_pending=pending,
            candidate_elapsed_seconds=elapsed,
            observed_metrics=(
                ("observation_duration_seconds", sample.observation_duration_seconds),
                ("sample_count", sample.sample_count),
                ("vehicles_in_scene", sample.vehicles_in_scene),
                ("vehicles_per_minute", sample.vehicles_per_minute),
                ("accumulation_delta", sample.accumulation_delta),
            ),
            active_rules=rules,
            compared_thresholds=(
                ("moderate_scene_enter", t.moderate_scene_enter),
                ("high_scene_enter", t.high_scene_enter),
                ("moderate_flow_enter", t.moderate_flow_enter),
                ("high_flow_enter", t.high_flow_enter),
                ("moderate_accumulation_enter", t.moderate_accumulation_enter),
                ("high_accumulation_enter", t.high_accumulation_enter),
                ("high_confirmation_seconds", t.high_confirmation_seconds),
            ),
            warnings=warnings,
            sufficient_data=sufficient,
            summary=summary,
        )
