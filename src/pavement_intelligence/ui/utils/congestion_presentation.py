"""Presentación pura de snapshots de congestión, sin dependencias de Streamlit."""

from __future__ import annotations

from dataclasses import dataclass

from pavement_intelligence.domain.traffic.congestion import (
    CongestionAlert,
    CongestionLevel,
)
from pavement_intelligence.domain.traffic.congestion_runtime import (
    TrafficCongestionSnapshot,
)


_LEVEL_PRESENTATION = {
    CongestionLevel.INSUFFICIENT_DATA: ("Datos insuficientes", "info"),
    CongestionLevel.NORMAL: ("Tránsito normal", "success"),
    CongestionLevel.MODERATE: ("Congestión moderada", "warning"),
    CongestionLevel.HIGH: ("Congestión alta", "error"),
}

_RULE_LABELS = {
    "INSUFFICIENT_DATA": "Calentamiento incompleto",
    "MODERATE_SCENE": "Ocupación visual elevada",
    "MODERATE_FLOW_HIGH_BUT_NOT_HIGH_ALONE": "Flujo alto como señal de apoyo",
    "MODERATE_ACCUMULATION": "Acumulación positiva",
    "HIGH_SCENE_ACCUMULATION": "Escena alta con acumulación",
    "HIGH_ACCUMULATION_WITH_OCCUPANCY": "Acumulación alta con ocupación",
    "HIGH_FLOW_SUPPORTING_ONLY": "Flujo alto sin confirmación HIGH por sí solo",
}


@dataclass(frozen=True)
class CongestionPresentationState:
    level_label: str
    level_code: str
    badge_variant: str
    headline: str
    summary: str
    vehicles_per_minute_text: str
    vehicles_in_scene_text: str
    accumulation_text: str
    observation_time_text: str
    candidate_text: str
    alert_text: str
    evidence_lines: tuple[str, ...]
    warning_lines: tuple[str, ...]
    is_paused: bool
    is_final: bool
    data_sufficient: bool
    normative: bool = False
    origin_label: str = "Estimación operativa"


@dataclass(frozen=True)
class CongestionAlertPresentation:
    alert_id: str
    time_text: str
    alert_type: str
    level: str
    status: str
    description: str
    origin: str = "OPERATIONAL_ESTIMATE"
    normative: bool = False


def present_congestion_snapshot(
    snapshot: TrafficCongestionSnapshot,
) -> CongestionPresentationState:
    """Convierte tipos y formatos sin recalcular la estimación del motor."""
    if not isinstance(snapshot, TrafficCongestionSnapshot):
        raise TypeError("snapshot debe ser TrafficCongestionSnapshot.")
    if snapshot.normative:
        raise ValueError("La presentación solo admite estimaciones no normativas.")

    level_label, badge_variant = _LEVEL_PRESENTATION[snapshot.level]
    evidence = snapshot.evidence
    summary = (
        evidence.summary if evidence is not None else "Aún no existen muestras válidas."
    )
    evidence_lines = _present_evidence(snapshot)
    candidate_text = _present_candidate(snapshot)
    alert_text = _present_alert_text(snapshot.alert)

    headline = level_label
    if snapshot.is_paused:
        headline = f"Análisis pausado · {level_label}"
    elif snapshot.is_final:
        headline = f"Análisis finalizado · {level_label}"

    return CongestionPresentationState(
        level_label=level_label,
        level_code=snapshot.level.value,
        badge_variant=badge_variant,
        headline=headline,
        summary=summary,
        vehicles_per_minute_text=f"{snapshot.vehicles_per_minute:.1f} veh/min",
        vehicles_in_scene_text=f"{snapshot.vehicles_in_scene} vehículos",
        accumulation_text=f"{snapshot.accumulation_delta:+.1f} veh/min",
        observation_time_text=f"{snapshot.observation_duration_seconds:.1f} segundos",
        candidate_text=candidate_text,
        alert_text=alert_text,
        evidence_lines=evidence_lines,
        warning_lines=tuple(snapshot.warnings),
        is_paused=snapshot.is_paused,
        is_final=snapshot.is_final,
        data_sufficient=bool(evidence and evidence.sufficient_data),
    )


def present_congestion_alert(alert: CongestionAlert) -> CongestionAlertPresentation:
    if not isinstance(alert, CongestionAlert):
        raise TypeError("alert debe ser CongestionAlert.")
    return CongestionAlertPresentation(
        alert_id=alert.alert_id,
        time_text=f"{alert.confirmed_at_seconds:.1f} s",
        alert_type="Congestión alta operativa",
        level=alert.level.value,
        status="Activa" if alert.active else "Cerrada",
        description=alert.message,
        origin=alert.origin,
        normative=alert.normative,
    )


def _present_candidate(snapshot: TrafficCongestionSnapshot) -> str:
    if snapshot.candidate_level is not CongestionLevel.HIGH:
        return ""
    thresholds = (
        dict(snapshot.evidence.compared_thresholds)
        if snapshot.evidence is not None
        else {}
    )
    required = thresholds.get("high_confirmation_seconds")
    progress = f"{snapshot.candidate_elapsed_seconds:.1f} segundos válidos"
    if required is not None:
        progress = f"{snapshot.candidate_elapsed_seconds:.1f} de {float(required):.1f} segundos válidos"
    return f"Congestión alta pendiente de confirmación · {progress}."


def _present_alert_text(alert: CongestionAlert | None) -> str:
    if alert is None:
        return ""
    status = "Alerta activa" if alert.active else "Alerta cerrada"
    return f"{status}: {alert.message} No representa un Nivel de Servicio normativo."


def _present_evidence(snapshot: TrafficCongestionSnapshot) -> tuple[str, ...]:
    evidence = snapshot.evidence
    if evidence is None:
        return ()
    lines = [evidence.summary]
    lines.extend(
        _RULE_LABELS.get(rule, rule.replace("_", " ").title())
        for rule in evidence.active_rules
    )
    return tuple(dict.fromkeys(lines))


__all__ = [
    "CongestionAlertPresentation",
    "CongestionPresentationState",
    "present_congestion_alert",
    "present_congestion_snapshot",
]
