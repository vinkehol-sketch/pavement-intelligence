"""Fase 5B: evaluación demostrativa y trazable de capas AASHTO 93."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import itertools
import json
import math
from typing import Any, MutableMapping

from .sn_workflow import AASHTO93Input, AASHTO93Result, result_is_stale


CONTRACT_VERSION = "5B-1.0"
METHODOLOGY_VERSION = "AASHTO93-LAYERS-DEMO-1.0"
COEFFICIENT_CATALOG_VERSION = "LOCAL-AASHTO93-DEMO-1.0"
DRAINAGE_RANGE = (0.40, 1.40)
MAX_SEARCH_COMBINATIONS = 10_000
MANDATORY_WARNING = (
    "El diseño por capas presentado es una evaluación demostrativa basada en el "
    "número estructural AASHTO 93 y en parámetros seleccionados por el usuario.\n\n"
    "Los coeficientes estructurales, drenaje, materiales, espesores mínimos y "
    "criterios de redondeo requieren validación técnica, normativa, constructiva "
    "y económica.\n\n"
    "El resultado no constituye una especificación de construcción ni un diseño "
    "vial aprobado."
)
MINIMUM_THICKNESS_WARNING = (
    "No existe una tabla local confirmada y universal de espesores mínimos para "
    "este flujo; cualquier mínimo ingresado es manual y requiere validación."
)


class LayerType(str, Enum):
    ASPHALT = "CARPETA_ASFALTICA"
    BASE = "BASE"
    SUBBASE = "SUBBASE"


class DesignMode(str, Enum):
    MANUAL = "EVALUAR_PROPUESTA_MANUAL"
    ADJUST_ONE = "AJUSTAR_UNA_CAPA"
    DISCRETE = "BUSQUEDA_DISCRETA_DEMOSTRATIVA"


class ComplianceStatus(str, Enum):
    NOT_COMPLIANT = "NO_CUMPLE"
    COMPLIANT = "CUMPLE"
    COMPLIANT_EXCESS = "CUMPLE_CON_EXCEDENTE"
    STALE = "DESACTUALIZADO"
    BLOCKED = "BLOQUEADO"


@dataclass(frozen=True)
class StructuralCoefficient:
    coefficient_id: str
    layer_type: str
    material: str
    description: str
    value: float
    source: str
    applicable_range: str
    condition: str = "DEMOSTRATIVO_NO_NORMATIVO"
    version: str = COEFFICIENT_CATALOG_VERSION
    warnings: tuple[str, ...] = ()


def coefficient_catalog() -> dict[str, StructuralCoefficient]:
    source = "Documentación local materiales_base_subbase.md y diseno_por_capas.md; validar fuente primaria"
    return {
        item.coefficient_id: item
        for item in (
            StructuralCoefficient(
                "AC_044",
                LayerType.ASPHALT.value,
                "Concreto asfáltico",
                "Coeficiente superior del rango local documentado",
                0.44,
                source,
                "0.35–0.44",
            ),
            StructuralCoefficient(
                "AC_040",
                LayerType.ASPHALT.value,
                "Concreto asfáltico",
                "Valor demostrativo usado en casos locales",
                0.40,
                source,
                "0.35–0.44",
            ),
            StructuralCoefficient(
                "BASE_014",
                LayerType.BASE.value,
                "Base granular",
                "Coeficiente superior del rango local documentado",
                0.14,
                source,
                "0.10–0.14",
            ),
            StructuralCoefficient(
                "BASE_012",
                LayerType.BASE.value,
                "Base granular",
                "Valor demostrativo local",
                0.12,
                source,
                "0.10–0.14",
            ),
            StructuralCoefficient(
                "SUBBASE_011",
                LayerType.SUBBASE.value,
                "Subbase granular",
                "Coeficiente superior del rango local documentado",
                0.11,
                source,
                "0.08–0.11",
            ),
            StructuralCoefficient(
                "SUBBASE_008",
                LayerType.SUBBASE.value,
                "Subbase granular",
                "Coeficiente inferior del rango local documentado",
                0.08,
                source,
                "0.08–0.11",
            ),
        )
    }


@dataclass(frozen=True)
class LayerDesignTransfer:
    transfer_id: str
    transferred_at: str
    design_id: str
    phase5a_result_id: str
    phase5a_fingerprint: str
    required_sn: float
    w18: float
    mr_psi: float
    reliability_percent: float
    p0: float
    pt: float
    delta_psi: float
    is_demonstrative: bool
    warnings: tuple[str, ...]
    responsible: str
    methodology_version: str
    version: str = "5A-TO-5B-1.0"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LayerInput:
    layer_id: str
    layer_type: str
    material: str
    thickness: float
    thickness_unit: str
    structural_coefficient: float
    coefficient_source: str
    coefficient_condition: str
    drainage_coefficient: float
    drainage_quality: str
    saturation_time_percent: float
    drainage_source: str
    parameter_source: str
    minimum_thickness: float | None = None
    minimum_thickness_unit: str = "in"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchRange:
    layer_type: str
    minimum_in: float
    maximum_in: float
    increment_in: float


@dataclass(frozen=True)
class SearchSettings:
    ranges: tuple[SearchRange, ...] = ()
    maximum_combinations: int = MAX_SEARCH_COMBINATIONS
    order_by: str = "MENOR_EXCEDENTE_SN"


@dataclass(frozen=True)
class RoundingRecord:
    layer_type: str
    before_in: float
    after_in: float
    increment_in: float
    rule: str
    responsible: str
    justification: str


@dataclass(frozen=True)
class LayerWorkflowInput:
    transfer: LayerDesignTransfer
    layers: tuple[LayerInput, ...]
    mode: str
    compliance_tolerance: float
    responsible: str
    justification: str
    adjusted_layer: str | None = None
    search: SearchSettings = SearchSettings()
    rounding: tuple[RoundingRecord, ...] = ()
    coefficient_catalog_version: str = COEFFICIENT_CATALOG_VERSION
    methodology_version: str = METHODOLOGY_VERSION
    created_at: str = ""
    mandatory_warning: str = MANDATORY_WARNING

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LayerContribution:
    layer_id: str
    layer_type: str
    material: str
    exact_thickness: float
    original_unit: str
    thickness_in: float
    adopted_thickness_in: float
    structural_coefficient: float
    drainage_coefficient: float
    sn_contribution: float
    source: str
    condition: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class LayerAlternative:
    thicknesses_in: tuple[tuple[str, float], ...]
    provided_sn: float
    excess_sn: float
    total_thickness_in: float
    asphalt_thickness_in: float


@dataclass(frozen=True)
class MinimumThicknessStatus:
    layer_id: str
    layer_type: str
    material: str
    adopted_thickness: float
    declared_minimum: float | None
    difference: float | None
    deficit: float | None
    display_unit: str
    status: str
    is_manual_non_normative: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LayerDesignResult:
    result_id: str
    created_at: str
    input_fingerprint: str
    required_sn: float
    provided_sn: float
    contributions: tuple[LayerContribution, ...]
    deficit: float
    excess: float
    compliance_percent: float
    status: str
    tolerance: float
    mode: str
    adjusted_layer: str | None
    search_settings: SearchSettings
    alternatives: tuple[LayerAlternative, ...]
    rounding: tuple[RoundingRecord, ...]
    transfer: LayerDesignTransfer
    warnings: tuple[str, ...]
    is_demonstrative: bool
    version: str = CONTRACT_VERSION
    methodology_version: str = METHODOLOGY_VERSION
    mandatory_warning: str = MANDATORY_WARNING

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hash(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def build_layer_transfer(
    result: AASHTO93Result, current: AASHTO93Input, *, transferred_at: str | None = None
) -> LayerDesignTransfer:
    if not result.converged or result_is_stale(result, current):
        raise ValueError("El resultado 5A no está vigente y convergido.")
    if not math.isfinite(result.required_sn) or result.required_sn <= 0:
        raise ValueError("El SN requerido debe ser finito y positivo.")
    at = transferred_at or datetime.now(timezone.utc).isoformat()
    return LayerDesignTransfer(
        "5b-transfer-" + _hash((result.result_id, result.input_fingerprint, at))[:16],
        at,
        current.design_id,
        result.result_id,
        result.input_fingerprint,
        result.required_sn,
        result.w18,
        result.mr_psi,
        result.reliability_percent,
        result.p0,
        result.pt,
        result.delta_psi,
        result.is_demonstrative,
        result.warnings,
        current.responsible,
        result.methodology_version,
    )


def thickness_to_inches(value: float, unit: str) -> float:
    if not math.isfinite(value) or value < 0:
        raise ValueError("El espesor debe ser finito y no negativo.")
    if unit == "in":
        return value
    if unit == "cm":
        return value / 2.54
    if unit == "mm":
        return value / 25.4
    raise ValueError("Unidad de espesor desconocida; use in, cm o mm.")


def inches_to_thickness(value: float, unit: str) -> float:
    if unit == "in":
        return value
    if unit == "cm":
        return value * 2.54
    if unit == "mm":
        return value * 25.4
    raise ValueError("Unidad de espesor desconocida; use in, cm o mm.")


def minimum_thickness_statuses(
    data: LayerWorkflowInput,
    result: LayerDesignResult,
    *,
    adopted_by_layer_in: dict[str, float] | None = None,
) -> tuple[MinimumThicknessStatus, ...]:
    """Deriva el control visual de mínimos sin modificar cálculo ni huella."""
    inputs = {item.layer_type: item for item in data.layers}
    contributions = {item.layer_type: item for item in result.contributions}
    rows: list[MinimumThicknessStatus] = []
    for layer_type in (item.value for item in LayerType):
        source = inputs[layer_type]
        contribution = contributions[layer_type]
        adopted_in = (
            adopted_by_layer_in[layer_type]
            if adopted_by_layer_in is not None
            else contribution.adopted_thickness_in
        )
        adopted = inches_to_thickness(adopted_in, source.thickness_unit)
        if source.minimum_thickness is None:
            rows.append(
                MinimumThicknessStatus(
                    source.layer_id,
                    layer_type,
                    source.material,
                    adopted,
                    None,
                    None,
                    None,
                    source.thickness_unit,
                    "MÍNIMO NO DECLARADO",
                    False,
                )
            )
            continue
        minimum_in = thickness_to_inches(
            source.minimum_thickness, source.minimum_thickness_unit
        )
        minimum = inches_to_thickness(minimum_in, source.thickness_unit)
        difference = adopted - minimum
        if math.isclose(adopted_in, minimum_in, rel_tol=1e-12, abs_tol=1e-12):
            status = "IGUAL AL MÍNIMO MANUAL DECLARADO"
            difference = 0.0
        elif difference > 0:
            status = "CUMPLE MÍNIMO MANUAL DECLARADO"
        else:
            status = "NO CUMPLE MÍNIMO MANUAL DECLARADO"
        rows.append(
            MinimumThicknessStatus(
                source.layer_id,
                layer_type,
                source.material,
                adopted,
                minimum,
                difference,
                max(0.0, -difference),
                source.thickness_unit,
                status,
                True,
            )
        )
    return tuple(rows)


def layer_contribution(
    layer: LayerInput, *, adopted_in: float | None = None
) -> LayerContribution:
    thickness_in = thickness_to_inches(layer.thickness, layer.thickness_unit)
    adopted = thickness_in if adopted_in is None else adopted_in
    for label, value in (
        ("coeficiente estructural", layer.structural_coefficient),
        ("coeficiente de drenaje", layer.drainage_coefficient),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"El {label} debe ser finito y positivo.")
    if layer.layer_type == LayerType.ASPHALT.value and not math.isclose(
        layer.drainage_coefficient, 1.0
    ):
        raise ValueError("La carpeta asfáltica usa m1=1 no editable en Fase 5B.")
    if (
        layer.layer_type != LayerType.ASPHALT.value
        and not DRAINAGE_RANGE[0] <= layer.drainage_coefficient <= DRAINAGE_RANGE[1]
    ):
        raise ValueError("m2 y m3 deben estar en el rango documentado 0,40–1,40.")
    if not all(
        (
            layer.material.strip(),
            layer.coefficient_source.strip(),
            layer.parameter_source.strip(),
        )
    ):
        raise ValueError("Cada capa exige material y fuentes explícitas.")
    if (
        layer.coefficient_condition == "MANUAL_JUSTIFICADO"
        and not layer.coefficient_source.strip()
    ):
        raise ValueError("El coeficiente manual exige fuente.")
    if layer.layer_type != LayerType.ASPHALT.value:
        if (
            not layer.drainage_source.strip()
            or not layer.drainage_quality.strip()
            or not math.isfinite(layer.saturation_time_percent)
        ):
            raise ValueError("El drenaje exige calidad, saturación y fuente.")
        if not 0 <= layer.saturation_time_percent <= 100:
            raise ValueError("El tiempo de saturación debe estar entre 0 y 100 %.")
    warnings = list(layer.warnings)
    if layer.minimum_thickness is None:
        warnings.append(MINIMUM_THICKNESS_WARNING)
    else:
        minimum = thickness_to_inches(
            layer.minimum_thickness, layer.minimum_thickness_unit
        )
        if adopted < minimum:
            warnings.append("ESPESOR_MENOR_AL_MINIMO_MANUAL_DECLARADO")
    contribution = layer.structural_coefficient * layer.drainage_coefficient * adopted
    return LayerContribution(
        layer.layer_id,
        layer.layer_type,
        layer.material,
        layer.thickness,
        layer.thickness_unit,
        thickness_in,
        adopted,
        layer.structural_coefficient,
        layer.drainage_coefficient,
        contribution,
        layer.parameter_source,
        layer.coefficient_condition,
        tuple(dict.fromkeys(warnings)),
    )


def round_up_thickness(
    value_in: float,
    increment_in: float,
    *,
    layer_type: str,
    responsible: str,
    justification: str,
) -> RoundingRecord:
    if (
        not all(math.isfinite(x) for x in (value_in, increment_in))
        or value_in < 0
        or increment_in <= 0
    ):
        raise ValueError("Valor e incremento de redondeo deben ser finitos y válidos.")
    if not responsible.strip() or not justification.strip():
        raise ValueError("El redondeo exige responsable y justificación.")
    after = math.ceil((value_in / increment_in) - 1e-12) * increment_in
    return RoundingRecord(
        layer_type,
        value_in,
        after,
        increment_in,
        "HACIA_ARRIBA",
        responsible,
        justification,
    )


def adjust_layer(
    layers: tuple[LayerInput, ...], required_sn: float, target_type: str
) -> tuple[LayerInput, ...]:
    target = next((x for x in layers if x.layer_type == target_type), None)
    if target is None:
        raise ValueError("La capa a ajustar no existe.")
    other = sum(
        layer_contribution(x).sn_contribution for x in layers if x is not target
    )
    denominator = target.structural_coefficient * target.drainage_coefficient
    if not math.isfinite(denominator) or denominator <= 0:
        raise ValueError("El denominador de ajuste debe ser positivo.")
    exact_in = max(0.0, (required_sn - other) / denominator)
    return tuple(
        replace(x, thickness=inches_to_thickness(exact_in, x.thickness_unit))
        if x is target
        else x
        for x in layers
    )


def _range_values(item: SearchRange) -> tuple[float, ...]:
    if not all(
        math.isfinite(x) for x in (item.minimum_in, item.maximum_in, item.increment_in)
    ):
        raise ValueError("Los límites de búsqueda deben ser finitos.")
    if (
        item.minimum_in < 0
        or item.maximum_in < item.minimum_in
        or item.increment_in <= 0
    ):
        raise ValueError("Límites o incremento de búsqueda inválidos.")
    count = (
        math.floor((item.maximum_in - item.minimum_in) / item.increment_in + 1e-12) + 1
    )
    return tuple(item.minimum_in + i * item.increment_in for i in range(count))


def discrete_search(data: LayerWorkflowInput) -> tuple[LayerAlternative, ...]:
    if len(data.search.ranges) != 3:
        raise ValueError("La búsqueda exige límites para las tres capas.")
    values = tuple(_range_values(x) for x in data.search.ranges)
    combinations = math.prod(len(x) for x in values)
    if data.search.maximum_combinations <= 0 or combinations > min(
        data.search.maximum_combinations, MAX_SEARCH_COMBINATIONS
    ):
        raise ValueError("La búsqueda excede el límite de combinaciones.")
    by_type = {x.layer_type: x for x in data.layers}
    alternatives = []
    for combo in itertools.product(*values):
        contributions = [
            layer_contribution(by_type[r.layer_type], adopted_in=v)
            for r, v in zip(data.search.ranges, combo, strict=True)
        ]
        provided = sum(x.sn_contribution for x in contributions)
        if provided + data.compliance_tolerance >= data.transfer.required_sn:
            pairs = tuple(
                (r.layer_type, v)
                for r, v in zip(data.search.ranges, combo, strict=True)
            )
            asphalt = dict(pairs)[LayerType.ASPHALT.value]
            alternatives.append(
                LayerAlternative(
                    pairs,
                    provided,
                    max(0.0, provided - data.transfer.required_sn),
                    sum(combo),
                    asphalt,
                )
            )
    keys = {
        "MENOR_EXCEDENTE_SN": lambda x: (
            x.excess_sn,
            x.total_thickness_in,
            x.thicknesses_in,
        ),
        "MENOR_ESPESOR_TOTAL": lambda x: (
            x.total_thickness_in,
            x.excess_sn,
            x.thicknesses_in,
        ),
        "MENOR_ESPESOR_ASFALTICO": lambda x: (
            x.asphalt_thickness_in,
            x.total_thickness_in,
            x.thicknesses_in,
        ),
    }
    if data.search.order_by not in keys:
        raise ValueError("Criterio de orden demostrativo desconocido.")
    return tuple(sorted(alternatives, key=keys[data.search.order_by]))


def validate_input(data: LayerWorkflowInput) -> None:
    if data.coefficient_catalog_version != COEFFICIENT_CATALOG_VERSION:
        raise ValueError("Catálogo de coeficientes desactualizado.")
    if data.mode not in {x.value for x in DesignMode}:
        raise ValueError("Modo de diseño desconocido.")
    if not math.isfinite(data.transfer.required_sn) or data.transfer.required_sn <= 0:
        raise ValueError("SN requerido inválido.")
    if (
        not math.isfinite(data.compliance_tolerance)
        or data.compliance_tolerance < 0
        or data.compliance_tolerance > 0.1
    ):
        raise ValueError("La tolerancia debe ser finita y estar entre 0 y 0,1 SN.")
    if not data.responsible.strip() or not data.justification.strip():
        raise ValueError("Responsable y justificación son obligatorios.")
    if len(data.layers) != 3 or {x.layer_type for x in data.layers} != {
        x.value for x in LayerType
    }:
        raise ValueError("Se requieren exactamente carpeta, base y subbase.")
    for layer in data.layers:
        layer_contribution(layer)


def input_fingerprint(data: LayerWorkflowInput) -> str:
    return _hash(data.as_dict())


def calculate_layer_design(data: LayerWorkflowInput) -> LayerDesignResult:
    validate_input(data)
    layers = data.layers
    if data.mode == DesignMode.ADJUST_ONE.value:
        if data.adjusted_layer not in {x.value for x in LayerType}:
            raise ValueError("Seleccione explícitamente la capa a ajustar.")
        layers = adjust_layer(layers, data.transfer.required_sn, data.adjusted_layer)
    rounding_by_type = {x.layer_type: x for x in data.rounding}
    contributions = tuple(
        layer_contribution(
            x,
            adopted_in=(
                rounding_by_type[x.layer_type].after_in
                if x.layer_type in rounding_by_type
                else None
            ),
        )
        for x in layers
    )
    provided = sum(x.sn_contribution for x in contributions)
    delta = provided - data.transfer.required_sn
    if abs(delta) <= data.compliance_tolerance:
        status = ComplianceStatus.COMPLIANT
    elif delta > 0:
        status = ComplianceStatus.COMPLIANT_EXCESS
    else:
        status = ComplianceStatus.NOT_COMPLIANT
    alternatives = (
        discrete_search(replace(data, layers=layers))
        if data.mode == DesignMode.DISCRETE.value
        else ()
    )
    warnings = tuple(
        dict.fromkeys(
            (MANDATORY_WARNING, MINIMUM_THICKNESS_WARNING)
            + data.transfer.warnings
            + tuple(w for x in contributions for w in x.warnings)
        )
    )
    at = datetime.now(timezone.utc).isoformat()
    fp = input_fingerprint(data)
    return LayerDesignResult(
        "layer5b-" + _hash((fp, at))[:16],
        at,
        fp,
        data.transfer.required_sn,
        provided,
        contributions,
        max(0.0, -delta),
        max(0.0, delta),
        100 * provided / data.transfer.required_sn,
        status.value,
        data.compliance_tolerance,
        data.mode,
        data.adjusted_layer,
        data.search,
        alternatives,
        data.rounding,
        data.transfer,
        warnings,
        True,
    )


def result_is_stale_5b(result: LayerDesignResult, current: LayerWorkflowInput) -> bool:
    return result.input_fingerprint != input_fingerprint(current)


def store_result(
    session: MutableMapping[str, Any],
    data: LayerWorkflowInput,
    result: LayerDesignResult,
) -> None:
    previous = session.get("aashto93_phase5b_result")
    if isinstance(previous, LayerDesignResult):
        session.setdefault("aashto93_phase5b_history", []).append(previous)
    session["aashto93_phase5b_input"] = data
    session["aashto93_phase5b_result"] = result
