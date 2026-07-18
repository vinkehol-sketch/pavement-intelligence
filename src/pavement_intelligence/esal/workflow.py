"""Flujo formal Pesaje → ESAL, aislado de Streamlit y de Diseño."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from statistics import mean, pstdev
from typing import Any, MutableMapping

from pavement_intelligence.traffic.factors import (
    lef_simple_axle,
    lef_tandem_axle,
    lef_tridem_axle,
)
from pavement_intelligence.traffic.tpda_workflow import ProjectionMethod
from pavement_intelligence.weighing.workflow import (
    CANONICAL_WEIGHT_UNIT,
    ESALReadiness,
    HEAVY_CATEGORIES,
    WeighingObservation,
    WeighingStatus,
    WeighingWorkflowResult,
)


STANDARD_SINGLE_AXLE_KN = 80.0
STANDARD_SINGLE_AXLE_KIP = 18.0
EQUIVALENCE_METHOD = "LEY_CUARTA_POTENCIA_EXISTENTE_V1"
EQUIVALENCE_METHOD_SOURCE = "AASHTO Guide 1993, Apéndice D (referencia interna)"
GROUP_REFERENCE_LOAD_KN = {
    "simple_single": 80.0,
    "simple_dual": 80.0,
    "tandem": 142.0,
    "tridem": 213.0,
}


class ESALWorkflowStatus(str, Enum):
    VALID_TO_CONTINUE = "VALIDO_PARA_CONTINUAR"
    VALID_FOR_DEMONSTRATION = "VALIDO_PARA_DEMOSTRACION"
    BLOCKED_BY_WEIGHING = "BLOQUEADO_POR_PESAJE"
    BLOCKED_BY_AXLE_CONFIGURATION = "BLOQUEADO_POR_CONFIGURACION_DE_EJES"
    BLOCKED_BY_EQUIVALENCE_FACTORS = "BLOQUEADO_POR_FACTORES_EQUIVALENTES"
    BLOCKED_BY_TRAFFIC = "BLOQUEADO_POR_TRANSITO"
    BLOCKED_BY_UNITS = "BLOQUEADO_POR_UNIDADES"
    BLOCKED_BY_SYNTHETIC_DATA = "BLOQUEADO_POR_DATOS_SINTETICOS"
    BLOCKED_BY_EMPTY_SAMPLE = "BLOQUEADO_POR_MUESTRA_VACIA"
    BLOCKED_BY_CLASSIFICATION = "BLOQUEADO_POR_CLASIFICACION"
    BLOCKED_BY_LOADS = "BLOQUEADO_POR_CARGAS"
    BLOCKED_BY_ESTIMATED_DATA = "BLOQUEADO_POR_DATOS_ESTIMADOS"
    STALE = "DESACTUALIZADO_REQUIERE_RECALCULO"


class DesignReadiness(str, Enum):
    FIT = "APTO_PARA_DISENO"
    DEMONSTRATION_ONLY = "APTO_SOLO_DEMOSTRACION"
    NOT_FIT = "NO_APTO_PARA_DISENO"


class LoadSource(str, Enum):
    WIM_MEASURED = "WIM_MEDIDO"
    MANUAL_VERIFIED = "MANUAL_VERIFICADO"
    ESTIMATED_BY_CATEGORY = "ESTIMADO_POR_CATEGORIA"
    SYNTHETIC_DEMONSTRATION = "DEMOSTRATIVO_SINTETICO"


@dataclass(frozen=True)
class ESALAxleGroupInput:
    position: int
    axle_type: str
    physical_axle_count: int
    total_group_load_kn: float
    individual_axle_load_kn: float
    canonical_unit: str
    load_source: str
    observations: str


@dataclass(frozen=True)
class ESALVehicleInput:
    vehicle_id: str
    approved_category: str
    origin: str
    axle_groups: tuple[ESALAxleGroupInput, ...]
    gross_weight_kn: float
    canonical_unit: str
    load_source: str
    weighing_condition: str
    quality_warnings: tuple[str, ...]
    generated_at: str
    contract_version: str


@dataclass(frozen=True)
class ESALInputFromWeighing:
    transfer_id: str
    version: str
    transferred_at: str
    source_weighing_result_id: str
    source_weighing_fingerprint: str
    source_tpda_result_id: str
    source_tpda_fingerprint: str
    weighing_methodological_status: str
    weighing_esal_readiness: str
    base_tpda_by_category: dict[str, float]
    projected_traffic_by_category: dict[str, float]
    design_period_years: int
    growth_rate_percent: float
    projection_method: str
    base_year: int
    directional_factor: float
    lane_distribution_factor: float
    projected_design_lane_traffic: float
    categories: tuple[str, ...]
    axle_configurations: dict[str, tuple[str, ...]]
    observations: tuple[WeighingObservation, ...]
    vehicles: tuple[ESALVehicleInput, ...]
    observation_count: int
    weighing_source_type: str
    source_reference: str
    canonical_weight_unit: str
    outlier_record_ids: tuple[str, ...]
    outlier_treatment: str
    gross_axle_tolerance_percent: float
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    is_synthetic: bool
    reviewer: str
    methodological_status: str
    demonstration_mode: bool


@dataclass(frozen=True)
class AxleEquivalentFactor:
    observation_id: str
    category: str
    group_position: int
    axle_type: str
    load_kn: float
    reference_load_kn: float
    equivalent_factor: float
    method: str
    method_version: str
    pavement_type: str
    source: str
    included: bool
    exclusion_reason: str
    load_source: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class VehicleEquivalentFactor:
    observation_id: str
    category: str
    axle_factors: tuple[float, ...]
    vehicle_factor: float
    provenance: str
    validation_state: str
    included: bool
    exclusion_reason: str
    load_source: str
    weighing_condition: str


@dataclass(frozen=True)
class TruckFactorByCategory:
    category: str
    observed_vehicles: int
    observed_esal_total: float
    mean_truck_factor: float
    standard_deviation: float
    minimum: float
    maximum: float
    source: str
    outlier_treatment: str
    is_synthetic: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CategoryESALResult:
    category: str
    base_traffic: float
    projected_traffic: float
    directional_factor: float
    lane_distribution_factor: float
    design_lane_traffic: float
    truck_factor: float
    initial_annual_esal: float
    accumulated_esal: float
    total_percent: float
    provenance: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AnnualESAL:
    year_index: int
    calendar_year: int
    growth_multiplier: float
    annual_esal: float
    accumulated_esal: float


@dataclass(frozen=True)
class ESALWorkflowInput:
    weighing_transfer: ESALInputFromWeighing
    equivalence_method: str = EQUIVALENCE_METHOD
    standard_single_axle_kn: float = STANDARD_SINGLE_AXLE_KN
    pavement_type: str = "PAVIMENTO_FLEXIBLE_APROXIMACION"
    excluded_observation_ids: tuple[str, ...] = ()
    exclusion_reason: str = ""
    outlier_treatment: str = "INCLUIR_Y_MARCAR"
    reviewer: str = ""
    synthetic_acknowledged: bool = False
    estimated_data_acknowledged: bool = False
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ESALWorkflowResult:
    result_id: str
    version: str
    created_at: str
    source_weighing_result_id: str
    source_weighing_fingerprint: str
    source_tpda_result_id: str
    source_tpda_fingerprint: str
    input_fingerprint: str
    equivalence_method: str
    equivalence_method_source: str
    standard_single_axle_kn: float
    standard_single_axle_kip: float
    standard_axle_description: str
    pavement_type: str
    axle_factors: tuple[AxleEquivalentFactor, ...]
    vehicle_factors: tuple[VehicleEquivalentFactor, ...]
    truck_factors_by_category: tuple[TruckFactorByCategory, ...]
    traffic_by_category: tuple[CategoryESALResult, ...]
    annual_esal: tuple[AnnualESAL, ...]
    initial_annual_esal: float
    accumulated_esal: float
    total_design_esal_w18: float
    analyzed_batch_vehicle_count: int
    analyzed_batch_esal: float
    batch_esal_by_category: dict[str, float]
    batch_esal_by_load_source: dict[str, float]
    measured_vehicle_percent: float
    manual_vehicle_percent: float
    estimated_vehicle_percent: float
    synthetic_vehicle_percent: float
    rejected_vehicle_ids: tuple[str, ...]
    pending_vehicle_ids: tuple[str, ...]
    outlier_treatment: str
    excluded_observation_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    is_synthetic: bool
    methodological_status: str
    design_readiness: str
    reviewer: str
    is_stale: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_source_for_observation(observation: WeighingObservation) -> LoadSource:
    if observation.condition == "SINTETICO_DEMOSTRATIVO":
        return LoadSource.SYNTHETIC_DEMONSTRATION
    if observation.condition == "ASUMIDO_POR_USUARIO":
        return LoadSource.ESTIMATED_BY_CATEGORY
    if observation.source_type == "WIM":
        return LoadSource.WIM_MEASURED
    return LoadSource.MANUAL_VERIFIED


def _vehicle_contract(observation: WeighingObservation) -> ESALVehicleInput:
    load_source = _load_source_for_observation(observation)
    warnings: list[str] = []
    if load_source == LoadSource.ESTIMATED_BY_CATEGORY:
        warnings.append("Carga estimada por categoría; no corresponde a una medición.")
    elif load_source == LoadSource.SYNTHETIC_DEMONSTRATION:
        warnings.append("Carga sintética; uso exclusivo de demostración.")
    return ESALVehicleInput(
        vehicle_id=observation.record_id,
        approved_category=observation.category,
        origin=observation.source_reference,
        axle_groups=tuple(
            ESALAxleGroupInput(
                position=group.position,
                axle_type=group.axle_type,
                physical_axle_count=group.physical_axle_count,
                total_group_load_kn=group.load_kn,
                individual_axle_load_kn=group.load_kn / group.physical_axle_count,
                canonical_unit=CANONICAL_WEIGHT_UNIT,
                load_source=load_source.value,
                observations=observation.notes,
            )
            for group in observation.axle_groups
        ),
        gross_weight_kn=observation.gross_weight_kn,
        canonical_unit=CANONICAL_WEIGHT_UNIT,
        load_source=load_source.value,
        weighing_condition=observation.condition,
        quality_warnings=tuple(warnings),
        generated_at=observation.timestamp,
        contract_version="1.0",
    )


def build_esal_input_from_weighing(
    result: WeighingWorkflowResult,
    *,
    allow_demonstration: bool = False,
    transferred_at: str | None = None,
) -> ESALInputFromWeighing:
    if result.is_stale:
        raise ValueError("El resultado de Pesaje está desactualizado.")
    productive = (
        result.esal_readiness == ESALReadiness.FIT.value
        and result.methodological_status == WeighingStatus.VALID_TO_CONTINUE.value
        and not result.is_synthetic
    )
    demo = (
        allow_demonstration
        and result.esal_readiness == ESALReadiness.DEMONSTRATION_ONLY.value
        and result.methodological_status == WeighingStatus.VALID_FOR_DEMONSTRATION.value
        and result.is_synthetic
    )
    if not (productive or demo):
        raise ValueError("El resultado de Pesaje no está habilitado para ESAL.")
    if result.canonical_weight_unit != CANONICAL_WEIGHT_UNIT:
        raise ValueError("Pesaje no utiliza la unidad canónica kN.")
    if not result.observations or result.observation_count != len(result.observations):
        raise ValueError("La muestra de Pesaje está vacía o es inconsistente.")
    if not result.source_tpda_result_id or not result.source_tpda_fingerprint:
        raise ValueError("La firma TPDA de origen está incompleta.")
    if not result.input_fingerprint or not result.reviewer:
        raise ValueError("La trazabilidad de Pesaje está incompleta.")

    timestamp = transferred_at or datetime.now(timezone.utc).isoformat()
    seed = f"{result.result_id}:{result.input_fingerprint}:{timestamp}:{allow_demonstration}"
    vehicles = tuple(_vehicle_contract(item) for item in result.observations)
    if any(
        item.load_source == LoadSource.MANUAL_VERIFIED.value
        and not observation.reviewer.strip()
        for item, observation in zip(vehicles, result.observations)
    ):
        raise ValueError("Una carga manual verificada requiere responsable.")
    return ESALInputFromWeighing(
        transfer_id="weighing-esal-" + hashlib.sha256(seed.encode()).hexdigest()[:16],
        version="1.0",
        transferred_at=timestamp,
        source_weighing_result_id=result.result_id,
        source_weighing_fingerprint=result.input_fingerprint,
        source_tpda_result_id=result.source_tpda_result_id,
        source_tpda_fingerprint=result.source_tpda_fingerprint,
        weighing_methodological_status=result.methodological_status,
        weighing_esal_readiness=result.esal_readiness,
        base_tpda_by_category=dict(result.base_tpda_by_category),
        projected_traffic_by_category=dict(result.projected_traffic_by_category),
        design_period_years=result.design_period_years,
        growth_rate_percent=result.growth_rate_percent,
        projection_method=result.projection_method,
        base_year=result.base_year,
        directional_factor=result.directional_factor,
        lane_distribution_factor=result.lane_distribution_factor,
        projected_design_lane_traffic=result.projected_design_lane_traffic,
        categories=result.categories,
        axle_configurations=dict(result.axle_configurations),
        observations=result.observations,
        vehicles=vehicles,
        observation_count=result.observation_count,
        weighing_source_type=result.weighing_source_type,
        source_reference=result.source_reference,
        canonical_weight_unit=result.canonical_weight_unit,
        outlier_record_ids=result.outlier_record_ids,
        outlier_treatment=result.outlier_treatment,
        gross_axle_tolerance_percent=result.gross_axle_tolerance_percent,
        assumptions=result.assumptions,
        warnings=result.warnings,
        is_synthetic=result.is_synthetic,
        reviewer=result.reviewer,
        methodological_status=result.methodological_status,
        demonstration_mode=demo,
    )


def store_esal_transfer(
    session: MutableMapping[str, Any],
    transfer: ESALInputFromWeighing,
    *,
    decision: str,
) -> bool:
    has_state = any(
        session.get(key) is not None
        for key in (
            "esal_input_from_weighing",
            "esal_phase3_result",
            "esal_phase3_input",
            "esal_result",
        )
    )
    if has_state and decision not in {"replace", "keep", "cancel"}:
        raise ValueError("Se requiere una decisión explícita para el estado ESAL existente.")
    if has_state and decision in {"keep", "cancel"}:
        return False
    if has_state and decision == "replace":
        session.setdefault("esal_history", []).append(
            {
                "replaced_at": datetime.now(timezone.utc).isoformat(),
                "input": session.get("esal_input_from_weighing"),
                "workflow_input": session.get("esal_phase3_input"),
                "result": session.get("esal_phase3_result"),
                "legacy_esal_result": session.get("esal_result"),
            }
        )
    session["esal_input_from_weighing"] = transfer
    session["esal_phase3_input"] = None
    session["esal_phase3_result"] = None
    return True


def weighing_transfer_is_current(
    transfer: ESALInputFromWeighing,
    current_result: WeighingWorkflowResult | None,
) -> bool:
    return bool(
        current_result is not None
        and not current_result.is_stale
        and transfer.source_weighing_result_id == current_result.result_id
        and transfer.source_weighing_fingerprint == current_result.input_fingerprint
        and transfer.source_tpda_result_id == current_result.source_tpda_result_id
        and transfer.source_tpda_fingerprint == current_result.source_tpda_fingerprint
    )


def _factor_for_group(axle_type: str, load_kn: float) -> float:
    if axle_type in {"simple_single", "simple_dual"}:
        return lef_simple_axle(load_kn)
    if axle_type == "tandem":
        return lef_tandem_axle(load_kn)
    if axle_type == "tridem":
        return lef_tridem_axle(load_kn)
    raise ValueError(f"Configuración de eje no soportada: {axle_type}.")


def esal_input_fingerprint(workflow_input: ESALWorkflowInput) -> str:
    canonical = json.dumps(
        asdict(workflow_input), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _growth_multiplier(method: str, rate_decimal: float, year_index: int) -> float:
    if method == ProjectionMethod.EXPONENTIAL.value:
        return (1 + rate_decimal) ** year_index
    if method == ProjectionMethod.LINEAR_B_ACADEMIC.value:
        return 1 + rate_decimal * year_index
    raise ValueError("Método de acumulación no compatible con el contrato TPDA.")


def calculate_esal_workflow(workflow_input: ESALWorkflowInput) -> ESALWorkflowResult:
    transfer = workflow_input.weighing_transfer
    if workflow_input.equivalence_method != EQUIVALENCE_METHOD:
        raise ValueError("Método de equivalencia no permitido.")
    if (
        not math.isfinite(workflow_input.standard_single_axle_kn)
        or workflow_input.standard_single_axle_kn != STANDARD_SINGLE_AXLE_KN
    ):
        raise ValueError("El método vigente exige eje estándar simple dual de 80 kN.")
    if transfer.canonical_weight_unit != CANONICAL_WEIGHT_UNIT:
        raise ValueError("Las cargas deben recibirse en kN.")
    if not workflow_input.reviewer.strip():
        raise ValueError("El revisor ESAL es obligatorio.")
    if transfer.design_period_years <= 0 or transfer.growth_rate_percent < 0:
        raise ValueError("Periodo o crecimiento inválido.")

    excluded = set(workflow_input.excluded_observation_ids)
    if not excluded <= set(transfer.outlier_record_ids):
        raise ValueError("Solo pueden excluirse atípicos identificados por Pesaje.")
    if excluded and not workflow_input.exclusion_reason.strip():
        raise ValueError("La exclusión de atípicos exige un motivo.")
    if not transfer.observations:
        status = ESALWorkflowStatus.BLOCKED_BY_EMPTY_SAMPLE
    else:
        status = None

    axle_details: list[AxleEquivalentFactor] = []
    vehicle_details: list[VehicleEquivalentFactor] = []
    by_category_factors: dict[str, list[float]] = {}
    warnings = list(transfer.warnings)
    rejected_ids: set[str] = set()
    pending_ids: set[str] = set()
    for observation in transfer.observations:
        load_source = _load_source_for_observation(observation)
        is_included = observation.record_id not in excluded
        reason = "" if is_included else workflow_input.exclusion_reason.strip()
        factors: list[float] = []
        if observation.category == "CAMION" or observation.category not in HEAVY_CATEGORIES:
            status = status or ESALWorkflowStatus.BLOCKED_BY_CLASSIFICATION
            pending_ids.add(observation.record_id)
        if not observation.axle_groups:
            status = status or ESALWorkflowStatus.BLOCKED_BY_AXLE_CONFIGURATION
            rejected_ids.add(observation.record_id)
        positions = [group.position for group in observation.axle_groups]
        if len(positions) != len(set(positions)) or any(position <= 0 for position in positions):
            status = status or ESALWorkflowStatus.BLOCKED_BY_AXLE_CONFIGURATION
            rejected_ids.add(observation.record_id)
        for group in observation.axle_groups:
            group_warnings: list[str] = []
            if group.axle_type not in GROUP_REFERENCE_LOAD_KN or group.physical_axle_count <= 0:
                status = status or ESALWorkflowStatus.BLOCKED_BY_AXLE_CONFIGURATION
                rejected_ids.add(observation.record_id)
                factor = 0.0
                reference_load = 0.0
                group_warnings.append("Configuración de grupo inválida.")
            elif group.load_kn <= 0 or not math.isfinite(group.load_kn):
                status = status or ESALWorkflowStatus.BLOCKED_BY_EQUIVALENCE_FACTORS
                rejected_ids.add(observation.record_id)
                factor = 0.0
                reference_load = GROUP_REFERENCE_LOAD_KN[group.axle_type]
                group_warnings.append("Carga faltante, no positiva o no finita.")
            else:
                factor = _factor_for_group(group.axle_type, group.load_kn)
                reference_load = GROUP_REFERENCE_LOAD_KN[group.axle_type]
            factors.append(factor)
            axle_details.append(
                AxleEquivalentFactor(
                    observation_id=observation.record_id,
                    category=observation.category,
                    group_position=group.position,
                    axle_type=group.axle_type,
                    load_kn=group.load_kn,
                    reference_load_kn=reference_load,
                    equivalent_factor=factor,
                    method="Ley de cuarta potencia, función existente por grupo",
                    method_version="1.0",
                    pavement_type=workflow_input.pavement_type,
                    source=EQUIVALENCE_METHOD_SOURCE,
                    included=is_included,
                    exclusion_reason=reason,
                    load_source=load_source.value,
                    warnings=tuple(group_warnings),
                )
            )
        vehicle_factor = sum(factors)
        vehicle_details.append(
            VehicleEquivalentFactor(
                observation_id=observation.record_id,
                category=observation.category,
                axle_factors=tuple(factors),
                vehicle_factor=vehicle_factor,
                provenance=observation.source_reference,
                validation_state=transfer.methodological_status,
                included=is_included,
                exclusion_reason=reason,
                load_source=load_source.value,
                weighing_condition=observation.condition,
            )
        )
        if is_included:
            by_category_factors.setdefault(observation.category, []).append(vehicle_factor)

        if observation.gross_weight_kn <= 0 or not math.isfinite(observation.gross_weight_kn):
            status = status or ESALWorkflowStatus.BLOCKED_BY_LOADS
            rejected_ids.add(observation.record_id)
        elif observation.axle_groups:
            discrepancy = abs(sum(group.load_kn for group in observation.axle_groups) - observation.gross_weight_kn)
            if discrepancy / observation.gross_weight_kn * 100 > transfer.gross_axle_tolerance_percent:
                status = status or ESALWorkflowStatus.BLOCKED_BY_LOADS
                rejected_ids.add(observation.record_id)

    invalid_ids = rejected_ids | pending_ids
    vehicle_details = [
        replace(
            item,
            included=False,
            exclusion_reason=(
                "RECHAZADO_POR_VALIDACION_TECNICA"
                if item.observation_id in invalid_ids
                else item.exclusion_reason
            ),
        )
        if item.observation_id in invalid_ids else item
        for item in vehicle_details
    ]
    by_category_factors = {}
    for item in vehicle_details:
        if item.included:
            by_category_factors.setdefault(item.category, []).append(item.vehicle_factor)

    truck_factors: list[TruckFactorByCategory] = []
    mean_by_category: dict[str, float] = {}
    for category, values in sorted(by_category_factors.items()):
        if not values:
            continue
        mean_factor = mean(values)
        mean_by_category[category] = mean_factor
        truck_factors.append(
            TruckFactorByCategory(
                category=category,
                observed_vehicles=len(values),
                observed_esal_total=sum(values),
                mean_truck_factor=mean_factor,
                standard_deviation=pstdev(values) if len(values) > 1 else 0.0,
                minimum=min(values),
                maximum=max(values),
                source=transfer.source_reference,
                outlier_treatment=workflow_input.outlier_treatment,
                is_synthetic=transfer.is_synthetic,
                warnings=(),
            )
        )

    heavy_with_traffic = {
        category
        for category, value in transfer.base_tpda_by_category.items()
        if category in HEAVY_CATEGORIES and value > 0
    }
    missing_factors = heavy_with_traffic - mean_by_category.keys()
    if missing_factors:
        status = status or ESALWorkflowStatus.BLOCKED_BY_EQUIVALENCE_FACTORS
        warnings.append(
            "Faltan factores observados para categorías pesadas: "
            + ", ".join(sorted(missing_factors))
        )
    if not transfer.base_tpda_by_category or sum(transfer.base_tpda_by_category.values()) <= 0:
        status = status or ESALWorkflowStatus.BLOCKED_BY_TRAFFIC

    rate = transfer.growth_rate_percent / 100.0
    category_accumulated: dict[str, float] = {}
    category_initial: dict[str, float] = {}
    annual_rows: list[AnnualESAL] = []
    accumulated_total = 0.0
    for year_index in range(transfer.design_period_years):
        multiplier = _growth_multiplier(transfer.projection_method, rate, year_index)
        annual_total = 0.0
        for category, base in transfer.base_tpda_by_category.items():
            factor = mean_by_category.get(category, 0.0)
            annual = (
                base
                * multiplier
                * 365.0
                * transfer.directional_factor
                * transfer.lane_distribution_factor
                * factor
            )
            annual_total += annual
            category_accumulated[category] = category_accumulated.get(category, 0.0) + annual
            if year_index == 0:
                category_initial[category] = annual
        accumulated_total += annual_total
        annual_rows.append(
            AnnualESAL(
                year_index=year_index,
                calendar_year=transfer.base_year + year_index,
                growth_multiplier=multiplier,
                annual_esal=annual_total,
                accumulated_esal=accumulated_total,
            )
        )

    traffic_results: list[CategoryESALResult] = []
    for category, base in transfer.base_tpda_by_category.items():
        category_warnings: list[str] = []
        if category not in HEAVY_CATEGORIES:
            category_warnings.append(
                "Categoría liviana conservada; sin factor estructural medido se asigna 0."
            )
        accumulated = category_accumulated.get(category, 0.0)
        traffic_results.append(
            CategoryESALResult(
                category=category,
                base_traffic=base,
                projected_traffic=transfer.projected_traffic_by_category.get(category, 0.0),
                directional_factor=transfer.directional_factor,
                lane_distribution_factor=transfer.lane_distribution_factor,
                design_lane_traffic=(
                    transfer.projected_traffic_by_category.get(category, 0.0)
                    * transfer.directional_factor
                    * transfer.lane_distribution_factor
                ),
                truck_factor=mean_by_category.get(category, 0.0),
                initial_annual_esal=category_initial.get(category, 0.0),
                accumulated_esal=accumulated,
                total_percent=(accumulated / accumulated_total * 100) if accumulated_total else 0.0,
                provenance=transfer.source_reference,
                warnings=tuple(category_warnings),
            )
        )

    synthetic = transfer.is_synthetic
    has_estimated = any(
        _load_source_for_observation(item) == LoadSource.ESTIMATED_BY_CATEGORY
        for item in transfer.observations
    )
    if status is None:
        if synthetic and not workflow_input.synthetic_acknowledged:
            status = ESALWorkflowStatus.BLOCKED_BY_SYNTHETIC_DATA
        elif has_estimated and not workflow_input.estimated_data_acknowledged:
            status = ESALWorkflowStatus.BLOCKED_BY_ESTIMATED_DATA
        elif synthetic:
            status = ESALWorkflowStatus.VALID_FOR_DEMONSTRATION
        else:
            status = ESALWorkflowStatus.VALID_TO_CONTINUE
    if status == ESALWorkflowStatus.VALID_TO_CONTINUE:
        readiness = DesignReadiness.FIT
    elif status == ESALWorkflowStatus.VALID_FOR_DEMONSTRATION:
        readiness = DesignReadiness.DEMONSTRATION_ONLY
    else:
        readiness = DesignReadiness.NOT_FIT

    fingerprint = esal_input_fingerprint(workflow_input)
    created_at = datetime.now(timezone.utc).isoformat()
    result_id = "esal-" + hashlib.sha256(
        f"{transfer.source_weighing_result_id}:{fingerprint}:{created_at}".encode()
    ).hexdigest()[:16]
    included_vehicles = [item for item in vehicle_details if item.included]
    batch_by_category: dict[str, float] = {}
    batch_by_source: dict[str, float] = {}
    source_counts = {source.value: 0 for source in LoadSource}
    for item in included_vehicles:
        batch_by_category[item.category] = batch_by_category.get(item.category, 0.0) + item.vehicle_factor
        batch_by_source[item.load_source] = batch_by_source.get(item.load_source, 0.0) + item.vehicle_factor
        source_counts[item.load_source] += 1
    batch_count = len(included_vehicles)
    percent = lambda source: source_counts[source.value] / batch_count * 100 if batch_count else 0.0
    return ESALWorkflowResult(
        result_id=result_id,
        version="1.0",
        created_at=created_at,
        source_weighing_result_id=transfer.source_weighing_result_id,
        source_weighing_fingerprint=transfer.source_weighing_fingerprint,
        source_tpda_result_id=transfer.source_tpda_result_id,
        source_tpda_fingerprint=transfer.source_tpda_fingerprint,
        input_fingerprint=fingerprint,
        equivalence_method=workflow_input.equivalence_method,
        equivalence_method_source=EQUIVALENCE_METHOD_SOURCE,
        standard_single_axle_kn=STANDARD_SINGLE_AXLE_KN,
        standard_single_axle_kip=STANDARD_SINGLE_AXLE_KIP,
        standard_axle_description=(
            "Eje simple de ruedas duales de referencia: 80 kN, presentación aproximada 18 kip"
        ),
        pavement_type=workflow_input.pavement_type,
        axle_factors=tuple(axle_details),
        vehicle_factors=tuple(vehicle_details),
        truck_factors_by_category=tuple(truck_factors),
        traffic_by_category=tuple(traffic_results),
        annual_esal=tuple(annual_rows),
        initial_annual_esal=annual_rows[0].annual_esal if annual_rows else 0.0,
        accumulated_esal=accumulated_total,
        total_design_esal_w18=accumulated_total,
        analyzed_batch_vehicle_count=batch_count,
        analyzed_batch_esal=sum(item.vehicle_factor for item in included_vehicles),
        batch_esal_by_category=batch_by_category,
        batch_esal_by_load_source=batch_by_source,
        measured_vehicle_percent=percent(LoadSource.WIM_MEASURED),
        manual_vehicle_percent=percent(LoadSource.MANUAL_VERIFIED),
        estimated_vehicle_percent=percent(LoadSource.ESTIMATED_BY_CATEGORY),
        synthetic_vehicle_percent=percent(LoadSource.SYNTHETIC_DEMONSTRATION),
        rejected_vehicle_ids=tuple(sorted(rejected_ids)),
        pending_vehicle_ids=tuple(sorted(pending_ids)),
        outlier_treatment=workflow_input.outlier_treatment,
        excluded_observation_ids=tuple(sorted(excluded)),
        assumptions=tuple(dict.fromkeys(transfer.assumptions + workflow_input.assumptions)),
        warnings=tuple(dict.fromkeys(warnings)),
        is_synthetic=synthetic,
        methodological_status=status.value,
        design_readiness=readiness.value,
        reviewer=workflow_input.reviewer,
    )


def esal_result_is_stale(
    result: ESALWorkflowResult,
    current_input: ESALWorkflowInput,
    current_weighing_result: WeighingWorkflowResult | None,
) -> bool:
    if result.input_fingerprint != esal_input_fingerprint(current_input):
        return True
    return not weighing_transfer_is_current(
        current_input.weighing_transfer, current_weighing_result
    )
