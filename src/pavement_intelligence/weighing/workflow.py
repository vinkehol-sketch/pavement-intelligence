"""Contrato y flujo metodológico de Pesaje (Fase 2).

Este módulo prepara resultados para una auditoría posterior. No calcula ESAL ni
publica datos en claves consumidas por ESAL.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, MutableMapping, TextIO

from pavement_intelligence.traffic.tpda_workflow import (
    MethodologicalStatus,
    OFFICIAL_TPDA_CATEGORIES,
    PENDING_TRUCK_CATEGORY,
    ProjectionMethod,
    TPDAWorkflowResult,
)


CANONICAL_WEIGHT_UNIT = "kN"
HEAVY_CATEGORIES = {
    "BUS", "C2", "C3", "TRACTOCAMION", "ARTICULADO", "OTRO_PESADO",
}
ALLOWED_AXLE_TYPES = {"simple_single", "simple_dual", "tandem", "tridem"}
AXLE_MULTIPLICITY = {
    "simple_single": 1,
    "simple_dual": 1,
    "tandem": 2,
    "tridem": 3,
}


class WeighingCondition(str, Enum):
    MEASURED = "MEDIDO"
    IMPORTED = "IMPORTADO"
    ASSUMED = "ASUMIDO_POR_USUARIO"
    SYNTHETIC = "SINTETICO_DEMOSTRATIVO"


class WeighingSourceType(str, Enum):
    WIM = "WIM"
    STATIC_SCALE = "PESAJE_ESTATICO"
    CSV = "ARCHIVO_CSV"
    MANUAL = "INGRESO_MANUAL"
    DEMONSTRATION_LIBRARY = "BIBLIOTECA_DEMOSTRATIVA"


class WeighingStatus(str, Enum):
    VALID_TO_CONTINUE = "VALIDO_PARA_CONTINUAR"
    VALID_FOR_DEMONSTRATION = "VALIDO_PARA_DEMOSTRACION"
    BLOCKED_BY_TPDA = "BLOQUEADO_POR_TPDA"
    BLOCKED_BY_CLASSIFICATION = "BLOQUEADO_POR_CLASIFICACION"
    BLOCKED_BY_AXLE_CONFIGURATION = "BLOQUEADO_POR_CONFIGURACION_DE_EJES"
    BLOCKED_BY_LOADS = "BLOQUEADO_POR_CARGAS"
    BLOCKED_BY_UNITS = "BLOQUEADO_POR_UNIDADES"
    BLOCKED_BY_SYNTHETIC_DATA = "BLOQUEADO_POR_DATOS_SINTETICOS"
    BLOCKED_BY_EMPTY_SAMPLE = "BLOQUEADO_POR_MUESTRA_VACIA"
    STALE = "DESACTUALIZADO_REQUIERE_RECALCULO"


class ESALReadiness(str, Enum):
    FIT = "APTO_PARA_ESAL"
    DEMONSTRATION_ONLY = "APTO_SOLO_DEMOSTRACION"
    NOT_FIT = "NO_APTO_PARA_ESAL"


@dataclass(frozen=True)
class TrafficCategoryTransfer:
    category: str
    base_tpda: float
    projected_traffic: float
    requires_load_configuration: bool
    classification_status: str
    provenance: str


@dataclass(frozen=True)
class WeighingInputFromTPDA:
    contract_version: str
    transfer_id: str
    transferred_at: str
    source_tpda_result_id: str
    source_tpda_fingerprint: str
    tpda_methodological_status: str
    base_tpda_by_category: dict[str, float]
    projected_traffic_by_category: dict[str, float]
    design_period_years: int
    growth_rate_percent: float
    projection_method: str
    base_year: int
    directional_factor: float
    lane_distribution_factor: float
    projected_design_lane_traffic: float
    categories: tuple[TrafficCategoryTransfer, ...]
    is_synthetic: bool
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]
    reviewer: str
    demonstration_mode: bool


@dataclass(frozen=True)
class AxleGroupLoad:
    position: int
    axle_type: str
    load_kn: float
    origin: str

    @property
    def physical_axle_count(self) -> int:
        return AXLE_MULTIPLICITY.get(self.axle_type, 0)


@dataclass(frozen=True)
class WeighingObservation:
    record_id: str
    timestamp: str
    category: str
    gross_weight_kn: float
    axle_groups: tuple[AxleGroupLoad, ...]
    source_type: str
    source_reference: str
    condition: str
    reviewer: str
    notes: str = ""

    @property
    def axle_load_sum_kn(self) -> float:
        return sum(group.load_kn for group in self.axle_groups)

    @property
    def physical_axle_count(self) -> int:
        return sum(group.physical_axle_count for group in self.axle_groups)


@dataclass(frozen=True)
class CategoryLoadStatistics:
    category: str
    observations: int
    gross_weight_mean_kn: float
    gross_weight_min_kn: float
    gross_weight_max_kn: float
    axle_group_load_mean_kn: float


@dataclass(frozen=True)
class WeighingWorkflowInput:
    tpda_transfer: WeighingInputFromTPDA
    observations: tuple[WeighingObservation, ...]
    source_type: WeighingSourceType
    source_reference: str
    source_date: str
    reviewer: str
    validation_state: str
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    gross_axle_tolerance_percent: float = 5.0
    outlier_treatment: str = "MARCAR_SIN_EXCLUIR"
    synthetic_acknowledged: bool = False


@dataclass(frozen=True)
class WeighingWorkflowResult:
    result_id: str
    version: str
    created_at: str
    source_tpda_result_id: str
    source_tpda_fingerprint: str
    input_fingerprint: str
    base_tpda_by_category: dict[str, float]
    projected_traffic_by_category: dict[str, float]
    design_period_years: int
    growth_rate_percent: float
    projection_method: str
    base_year: int
    directional_factor: float
    lane_distribution_factor: float
    projected_design_lane_traffic: float
    weighing_source_type: str
    source_reference: str
    source_date: str
    categories: tuple[str, ...]
    axle_configurations: dict[str, tuple[str, ...]]
    observation_count: int
    observations: tuple[WeighingObservation, ...]
    axle_loads_kn: tuple[float, ...]
    gross_weights_kn: tuple[float, ...]
    category_statistics: tuple[CategoryLoadStatistics, ...]
    outlier_record_ids: tuple[str, ...]
    outlier_treatment: str
    gross_axle_tolerance_percent: float
    canonical_weight_unit: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    is_synthetic: bool
    methodological_status: str
    esal_readiness: str
    reviewer: str
    validation_state: str
    is_stale: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite_positive(value: Any, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field_name} debe ser mayor que cero y finito.")
    return number


def convert_to_kn(value: Any, unit: str) -> float:
    """Convierte fuerza a kN; ``lb`` se interpreta como ``lbf``, no libra-masa."""
    number = _finite_positive(value, "carga")
    normalized = unit.strip().lower()
    factors = {
        "kn": 1.0,
        "kg": 0.00980665,
        "kgf": 0.00980665,
        "t": 9.80665,
        "ton": 9.80665,
        "tonelada": 9.80665,
        "toneladas": 9.80665,
        "lb": 0.0044482216152605,
        "lbs": 0.0044482216152605,
        "lbf": 0.0044482216152605,
        "kip": 4.4482216152605,
    }
    if normalized not in factors:
        raise ValueError(f"Unidad de carga no reconocida: {unit}.")
    return number * factors[normalized]


def build_weighing_input_from_tpda(
    result: TPDAWorkflowResult,
    *,
    allow_demonstration: bool = False,
    transferred_at: str | None = None,
) -> WeighingInputFromTPDA:
    """Valida y copia un resultado TPDA sin modificarlo."""
    if result.is_stale:
        raise ValueError("El resultado TPDA está desactualizado.")
    valid_productive = (
        result.methodological_status == MethodologicalStatus.VALID_TO_CONTINUE.value
        and result.methodologically_fit_for_next_phase
        and not result.is_synthetic
    )
    valid_demo = (
        allow_demonstration
        and result.methodological_status == MethodologicalStatus.VALID_FOR_DEMONSTRATION.value
        and result.is_synthetic
        and result.synthetic_acknowledged
    )
    if not (valid_productive or valid_demo):
        raise ValueError("El resultado TPDA no está habilitado para transferencia.")
    if not result.temporal_coverage_confirmed:
        raise ValueError("La duración del TPDA no está confirmada.")
    if result.projection_method not in {
        ProjectionMethod.EXPONENTIAL.value,
        ProjectionMethod.LINEAR_B_ACADEMIC.value,
    }:
        raise ValueError("El método de proyección no está permitido.")
    if not result.tpda_by_category or sum(result.tpda_by_category.values()) <= 0:
        raise ValueError("El TPDA por categoría está vacío.")
    if any(value > 0 for value in result.pending_categories.values()):
        raise ValueError("Existen categorías pendientes de clasificación.")
    if PENDING_TRUCK_CATEGORY in result.tpda_by_category:
        raise ValueError("CAMION_NO_CONFIRMADO no puede transferirse a Pesaje.")
    if not result.calculation_id or not result.input_fingerprint or not result.reviewer:
        raise ValueError("La trazabilidad TPDA está incompleta.")

    categories = tuple(
        TrafficCategoryTransfer(
            category=category,
            base_tpda=float(base),
            projected_traffic=float(result.projected_traffic_by_category.get(category, 0)),
            requires_load_configuration=category in HEAVY_CATEGORIES,
            classification_status="CONFIRMADA",
            provenance=result.data_origin,
        )
        for category, base in result.tpda_by_category.items()
    )
    timestamp = transferred_at or datetime.now(timezone.utc).isoformat()
    transfer_seed = (
        f"{result.calculation_id}:{result.input_fingerprint}:{timestamp}:"
        f"{allow_demonstration}"
    )
    return WeighingInputFromTPDA(
        contract_version="1.0",
        transfer_id="tpda-weighing-" + hashlib.sha256(transfer_seed.encode()).hexdigest()[:16],
        transferred_at=timestamp,
        source_tpda_result_id=result.calculation_id,
        source_tpda_fingerprint=result.input_fingerprint,
        tpda_methodological_status=result.methodological_status,
        base_tpda_by_category=dict(result.tpda_by_category),
        projected_traffic_by_category=dict(result.projected_traffic_by_category),
        design_period_years=result.design_period_years,
        growth_rate_percent=result.growth_rate_percent,
        projection_method=result.projection_method,
        base_year=result.base_year,
        directional_factor=result.directional_factor,
        lane_distribution_factor=result.lane_distribution_factor,
        projected_design_lane_traffic=result.projected_design_lane_traffic,
        categories=categories,
        is_synthetic=result.is_synthetic,
        warnings=result.warnings,
        assumptions=result.assumptions,
        reviewer=result.reviewer,
        demonstration_mode=valid_demo,
    )


def store_weighing_transfer(
    session: MutableMapping[str, Any],
    transfer: WeighingInputFromTPDA,
    *,
    decision: str,
) -> bool:
    """Guarda manualmente sin sobrescribir estado existente en silencio."""
    current = session.get("weighing_input_from_tpda")
    has_weighing_state = any(
        session.get(key) is not None
        for key in (
            "weighing_input_from_tpda",
            "weighing_records_current",
            "weighing_phase2_result",
            "pesaje_df",
        )
    )
    if has_weighing_state and decision not in {"replace", "keep", "cancel"}:
        raise ValueError("Se requiere una decisión explícita sobre los datos de Pesaje existentes.")
    if has_weighing_state and decision in {"keep", "cancel"}:
        return False
    if has_weighing_state and decision == "replace":
        history = session.setdefault("weighing_history", [])
        history.append(
            {
                "replaced_at": datetime.now(timezone.utc).isoformat(),
                "input": current,
                "records": session.get("weighing_records_current"),
                "result": session.get("weighing_phase2_result"),
                "legacy_pesaje_df": session.get("pesaje_df"),
            }
        )
    session["weighing_input_from_tpda"] = transfer
    session["weighing_records_current"] = None
    session["weighing_phase2_result"] = None
    if "pesaje_df" in session:
        session["pesaje_df"] = None
    return True


def _row_fingerprint(row: Mapping[str, Any], source_reference: str) -> str:
    canonical = json.dumps(
        {"source": source_reference, "row": dict(row)},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return "weight-" + hashlib.sha256(canonical.encode()).hexdigest()[:20]


def parse_weighing_csv(
    data: str | Path | TextIO,
    *,
    source_reference: str,
    source_type: WeighingSourceType = WeighingSourceType.CSV,
    condition: WeighingCondition = WeighingCondition.IMPORTED,
    reviewer: str,
    default_unit: str = "kN",
) -> tuple[WeighingObservation, ...]:
    """Importa CSV estrictamente; no omite filas inválidas."""
    is_path_string = isinstance(data, str) and "\n" not in data and "\r" not in data
    if isinstance(data, Path) or (is_path_string and Path(data).exists()):
        stream: TextIO = Path(data).open(encoding="utf-8-sig", newline="")
        should_close = True
    elif isinstance(data, str):
        stream = io.StringIO(data)
        should_close = True
    else:
        stream = data
        should_close = False
    try:
        rows = list(csv.DictReader(stream))
    finally:
        if should_close:
            stream.close()
    if not rows:
        return ()

    observations: list[WeighingObservation] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        category = str(row.get("category_id", "")).strip().upper()
        if category not in OFFICIAL_TPDA_CATEGORIES:
            raise ValueError(f"Fila {index}: categoría no admitida: {category}.")
        if category == PENDING_TRUCK_CATEGORY:
            raise ValueError(f"Fila {index}: camión sin clasificación estructural.")
        timestamp = str(row.get("timestamp", "")).strip()
        if not timestamp:
            raise ValueError(f"Fila {index}: timestamp requerido.")
        unit = str(row.get("unit", default_unit)).strip() or default_unit
        gross_raw = row.get("gross_weight") or row.get("gross_weight_kn")
        gross_kn = convert_to_kn(gross_raw, unit)

        axle_groups: list[AxleGroupLoad] = []
        axle_number = 1
        while (
            f"axle{axle_number}_load" in row
            or f"axle{axle_number}_load_kn" in row
            or f"axle{axle_number}_type" in row
        ):
            load_raw = row.get(f"axle{axle_number}_load")
            if load_raw in (None, ""):
                load_raw = row.get(f"axle{axle_number}_load_kn")
            axle_type = str(row.get(f"axle{axle_number}_type", "")).strip()
            if load_raw in (None, "") and not axle_type:
                axle_number += 1
                continue
            if not axle_type or axle_type not in ALLOWED_AXLE_TYPES:
                raise ValueError(f"Fila {index}: tipo de eje {axle_number} inválido.")
            axle_groups.append(
                AxleGroupLoad(
                    position=axle_number,
                    axle_type=axle_type,
                    load_kn=convert_to_kn(load_raw, unit),
                    origin=condition.value,
                )
            )
            axle_number += 1
        if not axle_groups:
            raise ValueError(f"Fila {index}: configuración de ejes vacía.")

        signature = json.dumps(
            {
                "timestamp": timestamp,
                "category": category,
                "gross": gross_kn,
                "axles": [(group.axle_type, group.load_kn) for group in axle_groups],
            },
            sort_keys=True,
        )
        if signature in seen:
            raise ValueError(f"Fila {index}: registro duplicado.")
        seen.add(signature)
        observations.append(
            WeighingObservation(
                record_id=_row_fingerprint(row, source_reference),
                timestamp=timestamp,
                category=category,
                gross_weight_kn=gross_kn,
                axle_groups=tuple(axle_groups),
                source_type=source_type.value,
                source_reference=source_reference,
                condition=condition.value,
                reviewer=reviewer,
                notes=str(row.get("notes", "")),
            )
        )
    return tuple(observations)


def build_manual_observation(
    *,
    category: str,
    gross_weight: float,
    axle_groups: tuple[tuple[str, float], ...],
    unit: str,
    source_type: WeighingSourceType,
    source_reference: str,
    condition: WeighingCondition,
    reviewer: str,
    timestamp: str,
    notes: str = "",
) -> WeighingObservation:
    if category not in OFFICIAL_TPDA_CATEGORIES or category == PENDING_TRUCK_CATEGORY:
        raise ValueError("Categoría estructural no admitida.")
    if not reviewer.strip() or not timestamp.strip() or not source_reference.strip():
        raise ValueError("Revisor, fecha y referencia son obligatorios.")
    groups: list[AxleGroupLoad] = []
    for position, (axle_type, load) in enumerate(axle_groups, start=1):
        if axle_type not in ALLOWED_AXLE_TYPES:
            raise ValueError(f"Tipo de eje no admitido: {axle_type}.")
        groups.append(
            AxleGroupLoad(
                position=position,
                axle_type=axle_type,
                load_kn=convert_to_kn(load, unit),
                origin=condition.value,
            )
        )
    if not groups:
        raise ValueError("Debe registrar al menos un eje o grupo.")
    gross_kn = convert_to_kn(gross_weight, unit)
    payload = {
        "category": category,
        "gross_weight_kn": gross_kn,
        "axles": [(item.axle_type, item.load_kn) for item in groups],
        "source": source_reference,
        "timestamp": timestamp,
    }
    record_id = "weight-" + hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()[:20]
    return WeighingObservation(
        record_id=record_id,
        timestamp=timestamp,
        category=category,
        gross_weight_kn=gross_kn,
        axle_groups=tuple(groups),
        source_type=source_type.value,
        source_reference=source_reference,
        condition=condition.value,
        reviewer=reviewer,
        notes=notes,
    )


def tpda_transfer_is_current(
    transfer: WeighingInputFromTPDA,
    current_tpda_result: TPDAWorkflowResult | None,
) -> bool:
    return bool(
        current_tpda_result is not None
        and not current_tpda_result.is_stale
        and transfer.source_tpda_result_id == current_tpda_result.calculation_id
        and transfer.source_tpda_fingerprint == current_tpda_result.input_fingerprint
    )


def weighing_input_fingerprint(workflow_input: WeighingWorkflowInput) -> str:
    canonical = json.dumps(
        asdict(workflow_input), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _outlier_ids(observations: Iterable[WeighingObservation]) -> tuple[str, ...]:
    grouped: dict[str, list[WeighingObservation]] = {}
    for observation in observations:
        grouped.setdefault(observation.category, []).append(observation)
    outliers: list[str] = []
    for values in grouped.values():
        if len(values) < 4:
            continue
        ordered = sorted(item.gross_weight_kn for item in values)
        midpoint = len(ordered) // 2
        lower = ordered[:midpoint]
        upper = ordered[-midpoint:]
        q1 = (lower[(len(lower) - 1) // 2] + lower[len(lower) // 2]) / 2
        q3 = (upper[(len(upper) - 1) // 2] + upper[len(upper) // 2]) / 2
        iqr = q3 - q1
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers.extend(
            item.record_id for item in values if not low <= item.gross_weight_kn <= high
        )
    return tuple(sorted(outliers))


def calculate_weighing_workflow(workflow_input: WeighingWorkflowInput) -> WeighingWorkflowResult:
    transfer = workflow_input.tpda_transfer
    warnings = list(workflow_input.warnings) + list(transfer.warnings)
    observations = workflow_input.observations
    transferred_categories = {item.category for item in transfer.categories}
    status: WeighingStatus | None = None

    if transfer.tpda_methodological_status not in {
        MethodologicalStatus.VALID_TO_CONTINUE.value,
        MethodologicalStatus.VALID_FOR_DEMONSTRATION.value,
    }:
        status = WeighingStatus.BLOCKED_BY_TPDA
    elif not observations:
        status = WeighingStatus.BLOCKED_BY_EMPTY_SAMPLE

    duplicate_ids = len({item.record_id for item in observations}) != len(observations)
    if duplicate_ids:
        status = status or WeighingStatus.BLOCKED_BY_LOADS
        warnings.append("La muestra contiene identificadores duplicados.")

    axis_invalid = False
    loads_invalid = False
    classification_invalid = False
    configurations: dict[str, set[str]] = {}
    for observation in observations:
        if observation.category not in transferred_categories:
            classification_invalid = True
        if (
            not observation.axle_groups
            or observation.physical_axle_count <= 0
            or any(group.axle_type not in ALLOWED_AXLE_TYPES for group in observation.axle_groups)
        ):
            axis_invalid = True
        if observation.gross_weight_kn <= 0 or any(
            group.load_kn <= 0 for group in observation.axle_groups
        ):
            loads_invalid = True
        if observation.gross_weight_kn > 0:
            discrepancy = abs(observation.axle_load_sum_kn - observation.gross_weight_kn)
            discrepancy_percent = discrepancy / observation.gross_weight_kn * 100
            if discrepancy_percent > workflow_input.gross_axle_tolerance_percent:
                loads_invalid = True
                warnings.append(
                    f"{observation.record_id}: suma de ejes difiere del peso bruto "
                    f"{discrepancy_percent:.2f}%."
                )
        configurations.setdefault(observation.category, set()).update(
            group.axle_type for group in observation.axle_groups
        )

    if classification_invalid:
        status = status or WeighingStatus.BLOCKED_BY_CLASSIFICATION
    elif axis_invalid:
        status = status or WeighingStatus.BLOCKED_BY_AXLE_CONFIGURATION
    elif loads_invalid:
        status = status or WeighingStatus.BLOCKED_BY_LOADS

    is_synthetic = transfer.is_synthetic or any(
        item.condition == WeighingCondition.SYNTHETIC.value for item in observations
    )
    if status is None:
        if is_synthetic and not workflow_input.synthetic_acknowledged:
            status = WeighingStatus.BLOCKED_BY_SYNTHETIC_DATA
        elif is_synthetic:
            status = WeighingStatus.VALID_FOR_DEMONSTRATION
        else:
            status = WeighingStatus.VALID_TO_CONTINUE

    grouped: dict[str, list[WeighingObservation]] = {}
    for item in observations:
        grouped.setdefault(item.category, []).append(item)
    statistics = tuple(
        CategoryLoadStatistics(
            category=category,
            observations=len(values),
            gross_weight_mean_kn=mean(item.gross_weight_kn for item in values),
            gross_weight_min_kn=min(item.gross_weight_kn for item in values),
            gross_weight_max_kn=max(item.gross_weight_kn for item in values),
            axle_group_load_mean_kn=mean(
                group.load_kn for item in values for group in item.axle_groups
            ),
        )
        for category, values in sorted(grouped.items())
    )
    outliers = _outlier_ids(observations)
    if outliers:
        warnings.append(
            f"Se identificaron {len(outliers)} valores atípicos; tratamiento: "
            f"{workflow_input.outlier_treatment}."
        )

    fingerprint = weighing_input_fingerprint(workflow_input)
    created_at = datetime.now(timezone.utc).isoformat()
    result_id = "weighing-" + hashlib.sha256(
        f"{transfer.source_tpda_result_id}:{fingerprint}:{created_at}".encode()
    ).hexdigest()[:16]
    if status == WeighingStatus.VALID_TO_CONTINUE:
        readiness = ESALReadiness.FIT
    elif status == WeighingStatus.VALID_FOR_DEMONSTRATION:
        readiness = ESALReadiness.DEMONSTRATION_ONLY
    else:
        readiness = ESALReadiness.NOT_FIT

    return WeighingWorkflowResult(
        result_id=result_id,
        version="1.0",
        created_at=created_at,
        source_tpda_result_id=transfer.source_tpda_result_id,
        source_tpda_fingerprint=transfer.source_tpda_fingerprint,
        input_fingerprint=fingerprint,
        base_tpda_by_category=dict(transfer.base_tpda_by_category),
        projected_traffic_by_category=dict(transfer.projected_traffic_by_category),
        design_period_years=transfer.design_period_years,
        growth_rate_percent=transfer.growth_rate_percent,
        projection_method=transfer.projection_method,
        base_year=transfer.base_year,
        directional_factor=transfer.directional_factor,
        lane_distribution_factor=transfer.lane_distribution_factor,
        projected_design_lane_traffic=transfer.projected_design_lane_traffic,
        weighing_source_type=workflow_input.source_type.value,
        source_reference=workflow_input.source_reference,
        source_date=workflow_input.source_date,
        categories=tuple(sorted(grouped)),
        axle_configurations={
            category: tuple(sorted(types)) for category, types in sorted(configurations.items())
        },
        observation_count=len(observations),
        observations=observations,
        axle_loads_kn=tuple(
            group.load_kn for item in observations for group in item.axle_groups
        ),
        gross_weights_kn=tuple(item.gross_weight_kn for item in observations),
        category_statistics=statistics,
        outlier_record_ids=outliers,
        outlier_treatment=workflow_input.outlier_treatment,
        gross_axle_tolerance_percent=workflow_input.gross_axle_tolerance_percent,
        canonical_weight_unit=CANONICAL_WEIGHT_UNIT,
        assumptions=workflow_input.assumptions,
        warnings=tuple(dict.fromkeys(warnings)),
        is_synthetic=is_synthetic,
        methodological_status=status.value,
        esal_readiness=readiness.value,
        reviewer=workflow_input.reviewer,
        validation_state=workflow_input.validation_state,
    )


def weighing_result_is_stale(
    result: WeighingWorkflowResult,
    current_input: WeighingWorkflowInput,
    current_tpda_result: TPDAWorkflowResult | None,
) -> bool:
    if result.input_fingerprint != weighing_input_fingerprint(current_input):
        return True
    if current_tpda_result is None:
        return True
    return (
        result.source_tpda_result_id != current_tpda_result.calculation_id
        or result.source_tpda_fingerprint != current_tpda_result.input_fingerprint
        or current_tpda_result.is_stale
    )


def store_weighing_records(
    session: MutableMapping[str, Any],
    observations: tuple[WeighingObservation, ...],
    *,
    decision: str,
) -> bool:
    existing = session.get("weighing_records_current")
    if existing is not None and decision not in {"replace", "keep", "cancel"}:
        raise ValueError("Se requiere decisión explícita para reemplazar la muestra.")
    if existing is not None and decision in {"keep", "cancel"}:
        return False
    if existing is not None and decision == "replace":
        session.setdefault("weighing_records_history", []).append(existing)
        previous_result = session.get("weighing_phase2_result")
        if previous_result is not None:
            session.setdefault("weighing_result_history", []).append(previous_result)
    session["weighing_records_current"] = observations
    return True
