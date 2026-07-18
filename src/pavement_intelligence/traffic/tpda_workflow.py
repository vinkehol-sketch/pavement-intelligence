"""Flujo metodológico auditable de Aforo a TPDA.

No contiene integración con Pesaje ni ESAL. Centraliza clasificación,
expansión, proyección, distribución y aptitud para una fase posterior.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping

from .projection import project_traffic_exponential, project_traffic_linear
from .tpda import calculate_tpda


OFFICIAL_TPDA_CATEGORIES = (
    "MOTO", "AUTO", "CAMIONETA", "MINIBUS", "BUS",
    "C2", "C3", "TRACTOCAMION", "ARTICULADO", "OTRO_PESADO",
)
PENDING_TRUCK_CATEGORY = "CAMION_NO_CONFIRMADO"


class ExpansionMethod(str, Enum):
    UNIFORM_24_OVER_HOURS = "UNIFORME_24_SOBRE_HORAS"
    DOCUMENTED_TEMPORAL_FACTOR = "FACTOR_TEMPORAL_DOCUMENTADO"
    NONE_24H = "SIN_EXPANSION_24H"


class ProjectionMethod(str, Enum):
    EXPONENTIAL = "EXPONENCIAL"
    LINEAR_B_ACADEMIC = "LINEAL_B_ACADEMICA"


class MethodologicalStatus(str, Enum):
    VALID_FOR_DEMONSTRATION = "VALIDO_PARA_DEMOSTRACION"
    VALID_TO_CONTINUE = "VALIDO_PARA_CONTINUAR"
    BLOCKED_BY_CLASSIFICATION = "BLOQUEADO_POR_CLASIFICACION"
    BLOCKED_BY_EXPANSION = "BLOQUEADO_POR_EXPANSION"
    BLOCKED_BY_SYNTHETIC_DATA = "BLOQUEADO_POR_DATOS_SINTETICOS"
    BLOCKED_BY_EMPTY_COUNTS = "BLOQUEADO_POR_CONTEOS"
    STALE = "DESACTUALIZADO_REQUIERE_RECALCULO"


@dataclass(frozen=True)
class FactorTrace:
    symbol: str
    name: str
    value: float
    function: str
    source: str
    applicability: str
    status: str = "DEFINIDO_POR_USUARIO_NO_OFICIAL"


@dataclass(frozen=True)
class TruckReclassification:
    original_category: str
    corrected_category: str
    reason: str
    reviewer: str
    corrected_at: str
    data_origin: str


@dataclass(frozen=True)
class TemporalCoverage:
    declared_hours: float
    verified_hours: float | None
    duration_source: str
    operator_confirmed: bool

    @property
    def is_confirmed(self) -> bool:
        if self.verified_hours is not None:
            return math.isclose(self.verified_hours, self.declared_hours, rel_tol=0, abs_tol=0.01)
        return self.operator_confirmed


@dataclass(frozen=True)
class TPDAWorkflowInput:
    batch_id: str
    source: str
    data_origin: str
    automatic_counts: dict[str, int | float]
    corrected_counts: dict[str, int | float]
    pending_categories: dict[str, int | float]
    temporal_coverage: TemporalCoverage
    expansion_method: ExpansionMethod
    temporal_factor: FactorTrace | None
    seasonal_factor: FactorTrace
    projection_method: ProjectionMethod
    growth_rate_percent: float
    design_period_years: int
    base_year: int
    directional_factor: float
    lane_distribution_factor: float
    reviewer: str
    reclassifications: tuple[TruckReclassification, ...] = ()
    warnings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    is_synthetic: bool = False
    synthetic_acknowledged: bool = False


@dataclass(frozen=True)
class TPDAWorkflowResult:
    schema_version: str
    calculation_id: str
    batch_id: str
    calculated_at: str
    input_fingerprint: str
    source: str
    data_origin: str
    automatic_counts: dict[str, float]
    corrected_counts: dict[str, float]
    pending_categories: dict[str, float]
    declared_duration_hours: float
    verified_duration_hours: float | None
    duration_source: str
    temporal_coverage_confirmed: bool
    expansion_method: str
    temporal_expansion_factor: float
    seasonal_factor: float
    final_expansion_factor: float
    tpda_base_total: float
    tpda_by_category: dict[str, float]
    projection_method: str
    growth_rate_percent: float
    design_period_years: int
    base_year: int
    design_year: int
    projected_traffic_total: float
    projected_traffic_by_category: dict[str, float]
    directional_factor: float
    lane_distribution_factor: float
    projected_directional_traffic: float
    projected_design_lane_traffic: float
    factor_traces: tuple[FactorTrace, ...]
    reclassifications: tuple[TruckReclassification, ...]
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]
    reviewer: str
    is_synthetic: bool
    synthetic_acknowledged: bool
    methodological_status: str
    methodologically_fit_for_next_phase: bool
    is_stale: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def inspect_csv_temporal_coverage(columns: list[str] | tuple[str, ...]) -> bool:
    """Indica si el esquema aporta evidencia temporal interna verificable."""
    normalized = {str(column).strip().lower() for column in columns}
    timestamp = bool(normalized & {"timestamp", "datetime", "fecha_hora"})
    date_and_time = bool(normalized & {"date", "fecha"}) and bool(
        normalized & {"hour", "hora", "time", "interval_start", "inicio_intervalo"}
    )
    explicit_interval = {"interval_start", "interval_end"}.issubset(normalized)
    metadata_duration = bool(normalized & {"duration_hours", "duracion_horas"})
    return timestamp or date_and_time or explicit_interval or metadata_duration


def classify_visual_events(events: list[Mapping[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    """Mapea solo clases visuales inequívocas; camión queda pendiente."""
    counts = {category: 0 for category in OFFICIAL_TPDA_CATEGORIES}
    pending = {PENDING_TRUCK_CATEGORY: 0}
    mapping = {
        "AUTO": "AUTO", "CAR": "AUTO",
        "MOTO": "MOTO", "MOTORCYCLE": "MOTO",
        "BUS": "BUS",
    }
    for event in events:
        raw = str(event.get("corrected_category") or event.get("category") or "").upper()
        if raw in OFFICIAL_TPDA_CATEGORIES:
            counts[raw] += 1
        elif raw in {"CAMION", "TRUCK", PENDING_TRUCK_CATEGORY}:
            pending[PENDING_TRUCK_CATEGORY] += 1
    return counts, pending


def reclassify_pending_trucks(
    counts: Mapping[str, int | float],
    pending_count: int,
    target_category: str,
    reason: str,
    reviewer: str,
    *,
    corrected_at: str | None = None,
    data_origin: str = "MANUAL_REVIEW",
) -> tuple[dict[str, int | float], dict[str, int], TruckReclassification]:
    if target_category not in OFFICIAL_TPDA_CATEGORIES:
        raise ValueError("La categoría corregida no pertenece al catálogo TPDA.")
    if pending_count <= 0:
        raise ValueError("No existen camiones pendientes para reclasificar.")
    if not reason.strip() or not reviewer.strip():
        raise ValueError("La reclasificación exige motivo y revisor.")
    updated = dict(counts)
    updated[target_category] = updated.get(target_category, 0) + pending_count
    trace = TruckReclassification(
        original_category=PENDING_TRUCK_CATEGORY,
        corrected_category=target_category,
        reason=reason.strip(),
        reviewer=reviewer.strip(),
        corrected_at=corrected_at or datetime.now(timezone.utc).isoformat(),
        data_origin=data_origin,
    )
    return updated, {PENDING_TRUCK_CATEGORY: 0}, trace


def workflow_input_fingerprint(workflow_input: TPDAWorkflowInput) -> str:
    payload = asdict(workflow_input)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def result_is_stale(result: TPDAWorkflowResult, current_input: TPDAWorkflowInput) -> bool:
    return result.input_fingerprint != workflow_input_fingerprint(current_input)


def _validated_counts(values: Mapping[str, int | float], *, allow_pending: bool = False) -> dict[str, float]:
    allowed = set(OFFICIAL_TPDA_CATEGORIES)
    if allow_pending:
        allowed.add(PENDING_TRUCK_CATEGORY)
    result: dict[str, float] = {}
    for category, raw in values.items():
        if category not in allowed:
            raise ValueError(f"Categoría no admitida: {category}.")
        value = float(raw)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Conteo inválido para {category}.")
        result[category] = value
    return result


def calculate_tpda_workflow(workflow_input: TPDAWorkflowInput) -> TPDAWorkflowResult:
    """Calcula una salida formal y determina su aptitud metodológica."""
    if not workflow_input.batch_id.strip() or not workflow_input.source.strip():
        raise ValueError("El lote y la fuente son obligatorios.")
    if not workflow_input.reviewer.strip():
        raise ValueError("El revisor es obligatorio.")

    automatic = _validated_counts(workflow_input.automatic_counts)
    corrected = _validated_counts(workflow_input.corrected_counts)
    pending = _validated_counts(workflow_input.pending_categories, allow_pending=True)
    warnings = list(workflow_input.warnings)
    assumptions = list(workflow_input.assumptions)
    coverage = workflow_input.temporal_coverage
    for name, value in {
        "directional_factor": workflow_input.directional_factor,
        "lane_distribution_factor": workflow_input.lane_distribution_factor,
    }.items():
        if not math.isfinite(value) or not 0 < value <= 1:
            raise ValueError(f"{name} debe estar en el intervalo (0, 1].")

    temporal_factor_value: float | None = None
    if coverage.declared_hours < 24:
        if workflow_input.expansion_method == ExpansionMethod.UNIFORM_24_OVER_HOURS:
            temporal_factor_value = None
            assumptions.append("Expansión uniforme 24/duración seleccionada por el operador.")
        elif workflow_input.expansion_method == ExpansionMethod.DOCUMENTED_TEMPORAL_FACTOR:
            if workflow_input.temporal_factor is None:
                raise ValueError("El método documentado requiere un factor temporal.")
            temporal_factor_value = workflow_input.temporal_factor.value
        else:
            raise ValueError("Un aforo parcial requiere un método de expansión.")
    else:
        if workflow_input.expansion_method != ExpansionMethod.NONE_24H:
            raise ValueError("Un aforo de 24 horas o más no admite expansión horaria adicional.")
        temporal_factor_value = None

    if coverage.declared_hours >= 24 and coverage.verified_hours is None:
        warnings.append(
            "El archivo o registro fue declarado como aforo completo, pero su cobertura "
            "temporal no puede verificarse automáticamente."
        )

    factor_trace_complete = True
    if (
        workflow_input.expansion_method == ExpansionMethod.DOCUMENTED_TEMPORAL_FACTOR
        and workflow_input.temporal_factor is not None
        and workflow_input.temporal_factor.source == "SIN_FUENTE_DECLARADA"
    ):
        factor_trace_complete = False
        warnings.append("El factor temporal definido por el usuario no tiene fuente declarada.")
    if (
        not math.isclose(workflow_input.seasonal_factor.value, 1.0)
        and workflow_input.seasonal_factor.source == "SIN_FUENTE_DECLARADA"
    ):
        factor_trace_complete = False
        warnings.append("El factor estacional distinto de 1,0 no tiene fuente declarada.")

    tpda = calculate_tpda(
        corrected,
        coverage.declared_hours,
        fdd=1.0,
        lane_distribution_factor=1.0,
        nocturnity_factor=temporal_factor_value,
        seasonal_factor=workflow_input.seasonal_factor.value,
    )

    projected_by_category: dict[str, float] = {}
    for category, base in tpda.tpda_by_category.items():
        if workflow_input.projection_method == ProjectionMethod.EXPONENTIAL:
            projection = project_traffic_exponential(
                base, workflow_input.growth_rate_percent, workflow_input.design_period_years
            )
        elif workflow_input.projection_method == ProjectionMethod.LINEAR_B_ACADEMIC:
            projection = project_traffic_linear(
                base,
                workflow_input.growth_rate_percent,
                workflow_input.design_period_years,
                variant="B",
            )
        else:
            raise ValueError("Método de proyección no permitido para el flujo productivo.")
        projected_by_category[category] = projection["v_f"]

    projected_total = sum(projected_by_category.values())
    pending_total = sum(pending.values())
    if pending_total > 0:
        status = MethodologicalStatus.BLOCKED_BY_CLASSIFICATION
        warnings.append("Existen camiones sin clasificación de ejes confirmada.")
    elif sum(corrected.values()) <= 0:
        status = MethodologicalStatus.BLOCKED_BY_EMPTY_COUNTS
    elif not coverage.is_confirmed or not factor_trace_complete:
        status = MethodologicalStatus.BLOCKED_BY_EXPANSION
    elif workflow_input.is_synthetic and not workflow_input.synthetic_acknowledged:
        status = MethodologicalStatus.BLOCKED_BY_SYNTHETIC_DATA
    elif workflow_input.is_synthetic:
        status = MethodologicalStatus.VALID_FOR_DEMONSTRATION
    else:
        status = MethodologicalStatus.VALID_TO_CONTINUE

    fit = status == MethodologicalStatus.VALID_TO_CONTINUE
    traces = tuple(
        trace
        for trace in (workflow_input.temporal_factor, workflow_input.seasonal_factor)
        if trace is not None
    )
    fingerprint = workflow_input_fingerprint(workflow_input)
    calculated_at = datetime.now(timezone.utc).isoformat()
    calculation_id = "tpda-" + hashlib.sha256(
        f"{workflow_input.batch_id}:{calculated_at}:{fingerprint}".encode("utf-8")
    ).hexdigest()[:16]

    return TPDAWorkflowResult(
        schema_version="1.0",
        calculation_id=calculation_id,
        batch_id=workflow_input.batch_id,
        calculated_at=calculated_at,
        input_fingerprint=fingerprint,
        source=workflow_input.source,
        data_origin=workflow_input.data_origin,
        automatic_counts=automatic,
        corrected_counts=corrected,
        pending_categories=pending,
        declared_duration_hours=coverage.declared_hours,
        verified_duration_hours=coverage.verified_hours,
        duration_source=coverage.duration_source,
        temporal_coverage_confirmed=coverage.is_confirmed,
        expansion_method=workflow_input.expansion_method.value,
        temporal_expansion_factor=tpda.temporal_expansion_factor,
        seasonal_factor=tpda.seasonal_factor,
        final_expansion_factor=tpda.temporal_expansion_factor * tpda.seasonal_factor,
        tpda_base_total=tpda.tpda_total,
        tpda_by_category=tpda.tpda_by_category,
        projection_method=workflow_input.projection_method.value,
        growth_rate_percent=workflow_input.growth_rate_percent,
        design_period_years=workflow_input.design_period_years,
        base_year=workflow_input.base_year,
        design_year=workflow_input.base_year + workflow_input.design_period_years,
        projected_traffic_total=projected_total,
        projected_traffic_by_category=projected_by_category,
        directional_factor=workflow_input.directional_factor,
        lane_distribution_factor=workflow_input.lane_distribution_factor,
        projected_directional_traffic=projected_total * workflow_input.directional_factor,
        projected_design_lane_traffic=(
            projected_total
            * workflow_input.directional_factor
            * workflow_input.lane_distribution_factor
        ),
        factor_traces=traces,
        reclassifications=workflow_input.reclassifications,
        warnings=tuple(dict.fromkeys(warnings)),
        assumptions=tuple(dict.fromkeys(assumptions)),
        reviewer=workflow_input.reviewer,
        is_synthetic=workflow_input.is_synthetic,
        synthetic_acknowledged=workflow_input.synthetic_acknowledged,
        methodological_status=status.value,
        methodologically_fit_for_next_phase=fit,
    )
