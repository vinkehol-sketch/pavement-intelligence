"""Flujo auditable Fase 3A -> 3B para proyección temporal de ESAL."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from typing import Any, MutableMapping

from .workflow import (
    DesignReadiness,
    ESALWorkflowResult,
    ESALWorkflowStatus,
)


PROJECTION_METHOD = "PROYECCION_GEOMETRICA_POR_CATEGORIA_V1"
PROJECTION_METHOD_LABEL = "Proyección temporal de ESAL — uso demostrativo/académico"
PROJECTION_WARNING = (
    "Los factores temporales, FDD, FDC, días de operación y tasas de crecimiento "
    "son calculados o ingresados bajo supuestos declarados; este resultado no es "
    "un ESAL oficial de diseño."
)
CONTRACT_VERSION = "1.0"
RESULT_VERSION = "1.0"


class TemporalFactorSource(str, Enum):
    CALCULATED_DURATION = "CALCULADO_DESDE_DURACION"
    MANUAL = "INGRESADO_MANUALMENTE"
    TPDA = "REFERENCIA_TPDA"
    DEMONSTRATION = "DEMOSTRATIVO_SIN_DURACION_CONFIRMADA"


class ProjectionStatus(str, Enum):
    VALID_TO_CONTINUE = "VALIDO_PARA_CONTINUAR"
    VALID_FOR_DEMONSTRATION = "VALIDO_PARA_DEMOSTRACION"
    BLOCKED_UNKNOWN_DURATION = "BLOQUEADO_POR_DURACION_DESCONOCIDA"
    BLOCKED_SYNTHETIC = "BLOQUEADO_POR_DATOS_SINTETICOS"
    STALE = "DESACTUALIZADO_REQUIERE_RECALCULO"


@dataclass(frozen=True)
class ESALObservationContribution:
    observation_id: str
    category: str
    load_source: str
    observed_esal: float


@dataclass(frozen=True)
class ESALProjectionTransfer:
    transfer_id: str
    version: str
    transferred_at: str
    source_esal_result_id: str
    source_esal_fingerprint: str
    source_equivalence_method: str
    source_equivalence_method_label: str
    source_methodological_status: str
    source_design_readiness: str
    source_created_at: str
    observed_batch_esal: float
    valid_vehicle_count: int
    categories: tuple[str, ...]
    observed_esal_by_category: dict[str, float]
    observed_esal_by_load_source: dict[str, float]
    contributions: tuple[ESALObservationContribution, ...]
    rejected_vehicle_ids: tuple[str, ...]
    pending_vehicle_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    source_reference_year: int | None
    source_reference_period_years: int
    is_synthetic: bool
    reviewer: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TemporalObservationBase:
    start_at: str | None
    end_at: str | None
    observed_hours: float | None
    observed_days: float | None
    expansion_factor_to_daily: float | None
    factor_source: str
    source_reference: str
    responsible: str
    justification: str
    notes: str = ""


@dataclass(frozen=True)
class CategoryGrowthRate:
    category: str
    annual_rate_percent: float
    source: str
    condition: str


@dataclass(frozen=True)
class ProjectionWorkflowInput:
    transfer: ESALProjectionTransfer
    temporal_base: TemporalObservationBase
    base_year: int
    projection_years: int
    directional_distribution_factor: float
    lane_distribution_factor: float
    operating_days_per_year: int = 365
    growth_rates: tuple[CategoryGrowthRate, ...] = ()
    growth_policy: str = "POR_CATEGORIA_EXPLICITA"
    method: str = PROJECTION_METHOD
    reviewer: str = ""
    synthetic_acknowledged: bool = False
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class CategoryProjection:
    category: str
    observed_batch_esal: float
    average_esal_per_vehicle: float
    observed_vehicle_count: int
    base_daily_esal: float
    distributed_daily_esal: float
    base_annual_esal: float
    accumulated_esal: float
    annual_rate_percent: float
    growth_source: str
    growth_condition: str
    total_percent: float


@dataclass(frozen=True)
class AnnualProjection:
    year_index: int
    calendar_year: int
    annual_projected_esal: float
    accumulated_esal: float


@dataclass(frozen=True)
class CategoryAnnualProjection:
    category: str
    year_index: int
    calendar_year: int
    growth_multiplier: float
    annual_projected_esal: float


@dataclass(frozen=True)
class SourceProjection:
    load_source: str
    observed_batch_esal: float
    accumulated_esal: float
    total_percent: float


@dataclass(frozen=True)
class ProjectionWorkflowResult:
    result_id: str
    version: str
    created_at: str
    source_transfer_id: str
    source_esal_result_id: str
    source_esal_fingerprint: str
    input_fingerprint: str
    method: str
    method_label: str
    method_warning: str
    temporal_base: TemporalObservationBase
    base_year: int
    projection_years: int
    directional_distribution_factor: float
    lane_distribution_factor: float
    operating_days_per_year: int
    observed_batch_esal: float
    average_esal_per_vehicle: float
    base_daily_esal: float
    distributed_daily_esal: float
    base_annual_esal: float
    accumulated_esal: float
    categories: tuple[CategoryProjection, ...]
    annual_series: tuple[AnnualProjection, ...]
    category_annual_series: tuple[CategoryAnnualProjection, ...]
    source_breakdown: tuple[SourceProjection, ...]
    excluded_rejected_vehicle_ids: tuple[str, ...]
    excluded_pending_vehicle_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    methodological_status: str
    reviewer: str
    is_synthetic: bool
    is_stale: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fingerprint(value: Any) -> str:
    canonical = json.dumps(asdict(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_projection_transfer(
    result: ESALWorkflowResult,
    *,
    allow_demonstration: bool = False,
    transferred_at: str | None = None,
) -> ESALProjectionTransfer:
    """Crea el contrato solo mediante una transferencia manual explícita."""
    productive = (
        not result.is_stale
        and result.methodological_status == ESALWorkflowStatus.VALID_TO_CONTINUE.value
        and result.design_readiness == DesignReadiness.FIT.value
        and not result.is_synthetic
    )
    demonstration = (
        allow_demonstration
        and not result.is_stale
        and result.methodological_status == ESALWorkflowStatus.VALID_FOR_DEMONSTRATION.value
        and result.design_readiness == DesignReadiness.DEMONSTRATION_ONLY.value
        and result.is_synthetic
    )
    if not (productive or demonstration):
        raise ValueError("El resultado 3A no está vigente y habilitado para transferencia 3B.")
    included = tuple(item for item in result.vehicle_factors if item.included)
    if not included or result.analyzed_batch_vehicle_count != len(included):
        raise ValueError("El lote ESAL 3A está vacío o es inconsistente.")
    if result.rejected_vehicle_ids or result.pending_vehicle_ids:
        raise ValueError("3A contiene vehículos rechazados o pendientes y no puede habilitar 3B.")
    contributions = tuple(
        ESALObservationContribution(
            observation_id=item.observation_id,
            category=item.category,
            load_source=item.load_source,
            observed_esal=item.vehicle_factor,
        )
        for item in included
    )
    if not math.isclose(sum(x.observed_esal for x in contributions), result.analyzed_batch_esal, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("El desglose de vehículos 3A no coincide con el ESAL observado.")
    timestamp = transferred_at or datetime.now(timezone.utc).isoformat()
    seed = f"{result.result_id}:{result.input_fingerprint}:{timestamp}"
    reference_year = result.annual_esal[0].calendar_year if result.annual_esal else None
    return ESALProjectionTransfer(
        transfer_id="esal-projection-" + hashlib.sha256(seed.encode()).hexdigest()[:16],
        version=CONTRACT_VERSION,
        transferred_at=timestamp,
        source_esal_result_id=result.result_id,
        source_esal_fingerprint=result.input_fingerprint,
        source_equivalence_method=result.equivalence_method,
        source_equivalence_method_label=result.equivalence_method_label,
        source_methodological_status=result.methodological_status,
        source_design_readiness=result.design_readiness,
        source_created_at=result.created_at,
        observed_batch_esal=result.analyzed_batch_esal,
        valid_vehicle_count=result.analyzed_batch_vehicle_count,
        categories=tuple(sorted(result.batch_esal_by_category)),
        observed_esal_by_category=dict(result.batch_esal_by_category),
        observed_esal_by_load_source=dict(result.batch_esal_by_load_source),
        contributions=contributions,
        rejected_vehicle_ids=result.rejected_vehicle_ids,
        pending_vehicle_ids=result.pending_vehicle_ids,
        warnings=result.warnings,
        source_reference_year=reference_year,
        source_reference_period_years=len(result.annual_esal),
        is_synthetic=result.is_synthetic,
        reviewer=result.reviewer,
    )


def build_temporal_base(
    *, start_at: str | None, end_at: str | None, observed_hours: float | None,
    observed_days: float | None, factor_source: TemporalFactorSource,
    source_reference: str, responsible: str, justification: str,
    manual_factor: float | None = None, notes: str = "",
) -> TemporalObservationBase:
    if not source_reference.strip() or not responsible.strip() or not justification.strip():
        raise ValueError("La base temporal exige fuente, responsable y justificación.")
    if (start_at is None) != (end_at is None):
        raise ValueError("Inicio y fin deben declararse juntos.")
    if start_at and end_at:
        try:
            start = datetime.fromisoformat(start_at)
            end = datetime.fromisoformat(end_at)
        except ValueError as exc:
            raise ValueError("Las fechas temporales deben usar formato ISO válido.") from exc
        if end <= start:
            raise ValueError("El fin temporal debe ser posterior al inicio.")
        derived_hours = (end - start).total_seconds() / 3600
        if observed_hours is not None and not math.isclose(observed_hours, derived_hours, rel_tol=0, abs_tol=0.01):
            raise ValueError("Las horas observadas no coinciden con las fechas.")
        observed_hours = derived_hours
    for name, value in (("horas", observed_hours), ("días", observed_days)):
        if value is not None and (not math.isfinite(value) or value <= 0):
            raise ValueError(f"Las {name} observados deben ser finitos y mayores que cero.")
    factor: float | None
    if factor_source == TemporalFactorSource.CALCULATED_DURATION:
        if observed_hours is None:
            raise ValueError("El factor calculado requiere duración observada.")
        factor = 24.0 / observed_hours
    elif factor_source == TemporalFactorSource.DEMONSTRATION:
        if observed_hours is not None:
            raise ValueError("La condición demostrativa se reserva para duración desconocida.")
        factor = None
    else:
        if manual_factor is None or not math.isfinite(manual_factor) or manual_factor <= 0:
            raise ValueError("El factor manual o TPDA debe ser finito y mayor que cero.")
        factor = float(manual_factor)
    return TemporalObservationBase(
        start_at=start_at, end_at=end_at, observed_hours=observed_hours,
        observed_days=observed_days, expansion_factor_to_daily=factor,
        factor_source=factor_source.value, source_reference=source_reference.strip(),
        responsible=responsible.strip(), justification=justification.strip(), notes=notes.strip(),
    )


def projection_input_fingerprint(workflow_input: ProjectionWorkflowInput) -> str:
    return _fingerprint(workflow_input)


def projection_transfer_is_current(
    transfer: ESALProjectionTransfer, current_result: ESALWorkflowResult | None
) -> bool:
    return bool(current_result and not current_result.is_stale
        and transfer.source_esal_result_id == current_result.result_id
        and transfer.source_esal_fingerprint == current_result.input_fingerprint)


def projection_result_is_stale(
    result: ProjectionWorkflowResult, current_input: ProjectionWorkflowInput,
    current_esal: ESALWorkflowResult | None,
) -> bool:
    return (result.input_fingerprint != projection_input_fingerprint(current_input)
        or not projection_transfer_is_current(current_input.transfer, current_esal))


def store_projection_transfer(
    session: MutableMapping[str, Any], transfer: ESALProjectionTransfer, *, decision: str
) -> bool:
    previous = session.get("esal_projection_transfer") or session.get("esal_projection_result")
    if previous and decision not in {"replace", "keep", "cancel"}:
        raise ValueError("Se requiere decisión explícita para reemplazar el estado 3B.")
    if previous and decision in {"keep", "cancel"}:
        return False
    if previous:
        session.setdefault("esal_projection_history", []).append({
            "replaced_at": datetime.now(timezone.utc).isoformat(),
            "transfer": session.get("esal_projection_transfer"),
            "input": session.get("esal_projection_input"),
            "result": session.get("esal_projection_result"),
        })
    session["esal_projection_transfer"] = transfer
    session["esal_projection_input"] = None
    session["esal_projection_result"] = None
    return True


def _validate_input(data: ProjectionWorkflowInput) -> dict[str, CategoryGrowthRate]:
    if data.method != PROJECTION_METHOD:
        raise ValueError("Método de proyección 3B no admitido.")
    if not data.reviewer.strip():
        raise ValueError("El revisor 3B es obligatorio.")
    if isinstance(data.base_year, bool) or not isinstance(data.base_year, int):
        raise TypeError("El año base debe ser entero.")
    if isinstance(data.projection_years, bool) or not isinstance(data.projection_years, int) or data.projection_years <= 0:
        raise ValueError("El periodo debe ser un entero mayor que cero.")
    if (isinstance(data.operating_days_per_year, bool) or not isinstance(data.operating_days_per_year, int)
            or not 1 <= data.operating_days_per_year <= 366):
        raise ValueError("Los días de operación deben ser un entero entre 1 y 366.")
    for label, value in (("FDD", data.directional_distribution_factor), ("FDC", data.lane_distribution_factor)):
        if not math.isfinite(value) or not 0 < value <= 1:
            raise ValueError(f"{label} debe ser finito y estar en (0, 1].")
    if data.growth_policy != "POR_CATEGORIA_EXPLICITA":
        raise ValueError("La política de crecimiento debe ser explícita por categoría.")
    rates: dict[str, CategoryGrowthRate] = {}
    for rate in data.growth_rates:
        if rate.category in rates:
            raise ValueError(f"Tasa duplicada para {rate.category}.")
        if rate.category not in data.transfer.categories:
            raise ValueError(f"Tasa declarada para categoría ajena: {rate.category}.")
        if not math.isfinite(rate.annual_rate_percent) or rate.annual_rate_percent <= -100:
            raise ValueError(f"Tasa inválida para {rate.category}; debe ser finita y mayor a -100 %.")
        if not rate.source.strip() or not rate.condition.strip():
            raise ValueError(f"La tasa de {rate.category} exige fuente y condición.")
        rates[rate.category] = rate
    missing = set(data.transfer.categories) - set(rates)
    if missing:
        raise ValueError("Faltan tasas explícitas para: " + ", ".join(sorted(missing)) + ".")
    return rates


def calculate_projection_workflow(data: ProjectionWorkflowInput) -> ProjectionWorkflowResult:
    rates = _validate_input(data)
    transfer = data.transfer
    warnings = [PROJECTION_WARNING]
    temporal_factor = data.temporal_base.expansion_factor_to_daily
    blocked_duration = temporal_factor is None
    if blocked_duration:
        warnings.append("La duración observada es desconocida; no se produce ESAL diario definitivo.")
    if transfer.is_synthetic and not data.synthetic_acknowledged:
        status = ProjectionStatus.BLOCKED_SYNTHETIC
    elif blocked_duration:
        status = ProjectionStatus.BLOCKED_UNKNOWN_DURATION
    elif transfer.is_synthetic:
        status = ProjectionStatus.VALID_FOR_DEMONSTRATION
    else:
        status = ProjectionStatus.VALID_TO_CONTINUE

    factor = temporal_factor or 0.0
    distribution = data.directional_distribution_factor * data.lane_distribution_factor
    category_rows: list[CategoryProjection] = []
    category_years: list[CategoryAnnualProjection] = []
    category_accumulated: dict[str, float] = {}
    counts = {category: 0 for category in transfer.categories}
    for contribution in transfer.contributions:
        counts[contribution.category] += 1
    for category in transfer.categories:
        observed = transfer.observed_esal_by_category[category]
        base_daily = observed * factor
        distributed_daily = base_daily * distribution
        base_annual = distributed_daily * data.operating_days_per_year
        rate = rates[category]
        accumulated = 0.0
        for n in range(data.projection_years):
            multiplier = (1.0 + rate.annual_rate_percent / 100.0) ** n
            annual = base_annual * multiplier
            if not math.isfinite(annual):
                raise OverflowError("La serie anual excede el rango numérico finito.")
            accumulated += annual
            category_years.append(CategoryAnnualProjection(
                category, n, data.base_year + n, multiplier, annual
            ))
        closed = (base_annual * data.projection_years if rate.annual_rate_percent == 0 else
            base_annual * (((1 + rate.annual_rate_percent / 100) ** data.projection_years - 1)
                           / (rate.annual_rate_percent / 100)))
        if not math.isclose(accumulated, closed, rel_tol=1e-9, abs_tol=1e-8):
            raise ArithmeticError("La suma anual no coincide con la forma cerrada.")
        category_accumulated[category] = accumulated
        category_rows.append(CategoryProjection(
            category, observed, observed / counts[category], counts[category], base_daily,
            distributed_daily, base_annual, accumulated, rate.annual_rate_percent,
            rate.source, rate.condition, 0.0,
        ))
    accumulated_total = sum(category_accumulated.values())
    category_rows = [CategoryProjection(**{**asdict(row), "total_percent":
        (100 * row.accumulated_esal / accumulated_total if accumulated_total else 0.0)})
        for row in category_rows]
    annual_rows: list[AnnualProjection] = []
    running = 0.0
    for n in range(data.projection_years):
        annual = sum(x.annual_projected_esal for x in category_years if x.year_index == n)
        running += annual
        annual_rows.append(AnnualProjection(n, data.base_year + n, annual, running))
    source_values: dict[str, tuple[float, float]] = {}
    for item in transfer.contributions:
        share_acc = 0.0
        rate = rates[item.category].annual_rate_percent / 100
        annual_base = item.observed_esal * factor * distribution * data.operating_days_per_year
        for n in range(data.projection_years):
            share_acc += annual_base * ((1 + rate) ** n)
        observed, accumulated = source_values.get(item.load_source, (0.0, 0.0))
        source_values[item.load_source] = (observed + item.observed_esal, accumulated + share_acc)
    source_rows = tuple(SourceProjection(source, observed, accumulated,
        100 * accumulated / accumulated_total if accumulated_total else 0.0)
        for source, (observed, accumulated) in sorted(source_values.items()))
    if not math.isclose(running, accumulated_total, rel_tol=1e-9, abs_tol=1e-8):
        raise ArithmeticError("El total anual no coincide con el desglose por categoría.")
    if not math.isclose(sum(x.accumulated_esal for x in source_rows), accumulated_total, rel_tol=1e-9, abs_tol=1e-8):
        raise ArithmeticError("El total no coincide con el desglose por fuente.")
    fingerprint = projection_input_fingerprint(data)
    created_at = datetime.now(timezone.utc).isoformat()
    result_id = "esal-3b-" + hashlib.sha256(f"{fingerprint}:{created_at}".encode()).hexdigest()[:16]
    return ProjectionWorkflowResult(
        result_id=result_id, version=RESULT_VERSION, created_at=created_at,
        source_transfer_id=transfer.transfer_id, source_esal_result_id=transfer.source_esal_result_id,
        source_esal_fingerprint=transfer.source_esal_fingerprint, input_fingerprint=fingerprint,
        method=data.method, method_label=PROJECTION_METHOD_LABEL, method_warning=PROJECTION_WARNING,
        temporal_base=data.temporal_base, base_year=data.base_year,
        projection_years=data.projection_years,
        directional_distribution_factor=data.directional_distribution_factor,
        lane_distribution_factor=data.lane_distribution_factor,
        operating_days_per_year=data.operating_days_per_year,
        observed_batch_esal=transfer.observed_batch_esal,
        average_esal_per_vehicle=transfer.observed_batch_esal / transfer.valid_vehicle_count,
        base_daily_esal=transfer.observed_batch_esal * factor,
        distributed_daily_esal=transfer.observed_batch_esal * factor * distribution,
        base_annual_esal=sum(x.base_annual_esal for x in category_rows),
        accumulated_esal=accumulated_total, categories=tuple(category_rows),
        annual_series=tuple(annual_rows), category_annual_series=tuple(category_years),
        source_breakdown=source_rows,
        excluded_rejected_vehicle_ids=transfer.rejected_vehicle_ids,
        excluded_pending_vehicle_ids=transfer.pending_vehicle_ids,
        assumptions=data.assumptions, warnings=tuple(dict.fromkeys(warnings)),
        methodological_status=status.value, reviewer=data.reviewer,
        is_synthetic=transfer.is_synthetic,
    )
