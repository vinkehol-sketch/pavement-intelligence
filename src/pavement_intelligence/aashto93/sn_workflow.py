"""Fase 5A: entradas trazables y solución del SN requerido AASHTO 93 flexible."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, MutableMapping

from pavement_intelligence.esal.projection_workflow import (
    ProjectionStatus,
    ProjectionWorkflowInput,
    ProjectionWorkflowResult,
    projection_input_fingerprint,
)
from pavement_intelligence.geotechnics.resilient_modulus_review import (
    FutureAASHTOTransfer,
)


CONTRACT_VERSION = "5A-1.0"
METHODOLOGY_VERSION = "AASHTO93-FLEXIBLE-SN-1.0"
ZR_CATALOG_VERSION = "AASHTO93-TABLE-2.2-1.0"
ZR_CATALOG_SOURCE = "AASHTO Guide for Design of Pavement Structures (1993), Tabla 2.2"
ZR_CATALOG = {
    50.0: 0.000,
    75.0: -0.674,
    80.0: -0.841,
    85.0: -1.037,
    90.0: -1.282,
    95.0: -1.645,
    99.0: -2.327,
}
CANONICAL_MR_UNIT = "psi"
MPA_TO_PSI = 145.03773773020923
EQUATION = (
    "log10(W18)=ZR*S0+9.36*log10(SN+1)-0.20+"
    "log10(deltaPSI/(4.2-1.5))/(0.40+1094/(SN+1)^5.19)+"
    "2.32*log10(MR_psi)-8.07"
)
EQUATION_SOURCE = (
    "AASHTO Guide for Design of Pavement Structures (1993), ecuación flexible"
)
COEFFICIENTS = {
    "sn_log": 9.36,
    "constant_1": -0.20,
    "service_denominator": 0.40,
    "service_factor": 1094.0,
    "sn_exponent": 5.19,
    "mr_log": 2.32,
    "constant_2": -8.07,
    "service_initial_reference": 4.2,
    "service_terminal_reference": 1.5,
}
MANDATORY_WARNING = (
    "Este cálculo implementa la ecuación AASHTO 93 para obtener un número estructural "
    "requerido dentro de un flujo demostrativo.\n\n"
    "La validez del resultado depende de la calidad y representatividad de W18, MR, "
    "confiabilidad, serviciabilidad y demás parámetros ingresados.\n\n"
    "No constituye por sí solo un diseño vial aprobado ni una recomendación constructiva."
)
LOWER_BOUND_WARNING_CODE = "SN_CERCANO_LIMITE_INFERIOR"
UPPER_BOUND_WARNING_CODE = "SN_CERCANO_LIMITE_SUPERIOR"
MAX_BOUNDARY_MARGIN_FRACTION = 0.25


@dataclass(frozen=True)
class ESAL5ATransfer:
    transfer_id: str
    transferred_at: str
    traffic_study_id: str
    phase3b_result_id: str
    phase3b_fingerprint: str
    accumulated_esal: float
    period_years: int
    start_year: int
    end_year: int
    method: str
    methodological_status: str
    is_demonstrative: bool
    temporal_expansion_factor: float
    temporal_factor_source: str
    directional_distribution_factor: float
    lane_distribution_factor: float
    operating_days_per_year: int
    growth_rates: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    version: str = "5A-ESAL-1.0"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MR5ATransfer:
    transfer_id: str
    transferred_at: str
    geotechnical_study_id: str
    phase4b_review_id: str
    phase4b_fingerprint: str
    adopted_mr: float
    unit: str
    source: str
    adoption_mode: str
    responsible: str
    justification: str
    evidence: str
    is_demonstrative: bool
    warnings: tuple[str, ...]
    version: str = "5A-MR-1.0"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SolverSettings:
    sn_min: float
    sn_max: float
    tolerance: float
    max_iterations: int
    boundary_margin_fraction: float = 0.02


@dataclass(frozen=True)
class AASHTO93Input:
    design_id: str
    segment: str
    esal_transfer: ESAL5ATransfer
    mr_transfer: MR5ATransfer
    w18: float
    resilient_modulus: float
    original_mr_unit: str
    reliability_percent: float
    zr: float
    zr_source: str
    zr_catalog_version: str
    s0: float
    s0_source: str
    s0_condition: str
    p0: float
    pt: float
    delta_psi: float
    analysis_period: str
    parameter_sources: tuple[tuple[str, str], ...]
    responsible: str
    justification: str
    inherited_warnings: tuple[str, ...]
    solver: SolverSettings
    synthetic_acknowledged: bool
    contract_version: str = CONTRACT_VERSION
    methodology_version: str = METHODOLOGY_VERSION
    created_at: str = ""
    mandatory_warning: str = MANDATORY_WARNING

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AASHTO93Result:
    result_id: str
    created_at: str
    input_fingerprint: str
    required_sn: float
    w18: float
    mr_psi: float
    reliability_percent: float
    zr: float
    s0: float
    p0: float
    pt: float
    delta_psi: float
    equation: str
    coefficients: dict[str, float]
    residual: float
    iterations: int
    initial_interval: tuple[float, float]
    tolerance: float
    boundary_margin_fraction: float
    boundary_margin_absolute: float
    converged: bool
    esal_transfer: ESAL5ATransfer
    mr_transfer: MR5ATransfer
    warnings: tuple[str, ...]
    is_demonstrative: bool
    version: str = CONTRACT_VERSION
    methodology_version: str = METHODOLOGY_VERSION
    canonical_mr_unit: str = CANONICAL_MR_UNIT
    equation_source: str = EQUATION_SOURCE
    mandatory_warning: str = MANDATORY_WARNING

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()


def build_esal_5a_transfer(
    result: ProjectionWorkflowResult,
    current: ProjectionWorkflowInput,
    *,
    transferred_at: str | None = None,
) -> ESAL5ATransfer:
    if result.is_stale or result.input_fingerprint != projection_input_fingerprint(
        current
    ):
        raise ValueError("La transferencia ESAL está desactualizada.")
    allowed = {
        ProjectionStatus.VALID_TO_CONTINUE.value,
        ProjectionStatus.VALID_FOR_DEMONSTRATION.value,
    }
    if result.methodological_status not in allowed or result.accumulated_esal <= 0:
        raise ValueError("El resultado 3B no está aprobado y vigente para Fase 5A.")
    factor = result.temporal_base.expansion_factor_to_daily
    if factor is None or not math.isfinite(factor) or factor <= 0:
        raise ValueError("La expansión temporal 3B no es válida.")
    at = transferred_at or datetime.now(timezone.utc).isoformat()
    return ESAL5ATransfer(
        "5a-esal-" + _hash((result.result_id, result.input_fingerprint, at))[:16],
        at,
        result.source_esal_result_id,
        result.result_id,
        result.input_fingerprint,
        result.accumulated_esal,
        result.projection_years,
        result.base_year,
        result.base_year + result.projection_years - 1,
        result.method,
        result.methodological_status,
        result.is_synthetic,
        factor,
        result.temporal_base.factor_source,
        result.directional_distribution_factor,
        result.lane_distribution_factor,
        result.operating_days_per_year,
        tuple(
            {
                "category": x.category,
                "annual_rate_percent": x.annual_rate_percent,
                "source": x.growth_source,
                "condition": x.growth_condition,
            }
            for x in result.categories
        ),
        tuple(dict.fromkeys((result.method_warning,) + result.warnings)),
    )


def build_mr_5a_transfer(
    transfer: FutureAASHTOTransfer, *, study_id: str, adoption_mode: str, evidence: str
) -> MR5ATransfer:
    if (
        transfer.unit not in {"MPa", "psi"}
        or transfer.adopted_resilient_modulus_mpa <= 0
    ):
        raise ValueError("La transferencia MR tiene unidad o valor inválido.")
    if not transfer.responsible.strip() or not transfer.justification.strip():
        raise ValueError("La transferencia MR exige responsable y justificación.")
    return MR5ATransfer(
        "5a-mr-" + _hash(transfer.as_dict())[:16],
        transfer.transferred_at,
        study_id,
        transfer.geotechnical_review_id,
        transfer.review_fingerprint,
        transfer.adopted_resilient_modulus_mpa,
        transfer.unit,
        transfer.source,
        adoption_mode,
        transfer.responsible,
        transfer.justification,
        evidence,
        transfer.is_demonstrative,
        transfer.warnings,
    )


def zr_from_catalog(reliability_percent: float) -> float:
    if reliability_percent not in ZR_CATALOG:
        raise ValueError("La confiabilidad debe seleccionarse del catálogo versionado.")
    return ZR_CATALOG[reliability_percent]


def convert_mr_to_psi(value: float, unit: str) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError("MR debe ser finito y positivo.")
    if unit == "psi":
        return value
    if unit == "MPa":
        return value * MPA_TO_PSI
    raise ValueError("Unidad MR desconocida; use MPa o psi.")


def aashto_log10_w18(
    sn: float, *, zr: float, s0: float, delta_psi: float, mr_psi: float
) -> float:
    values = (sn, zr, s0, delta_psi, mr_psi)
    if (
        not all(math.isfinite(x) for x in values)
        or sn <= 0
        or s0 <= 0
        or delta_psi <= 0
        or mr_psi <= 0
    ):
        raise ValueError("La ecuación exige valores finitos y positivos en su dominio.")
    service_ratio = delta_psi / (4.2 - 1.5)
    if service_ratio <= 0:
        raise ValueError("ΔPSI produce un logaritmo inválido.")
    return (
        zr * s0
        + 9.36 * math.log10(sn + 1)
        - 0.20
        + math.log10(service_ratio) / (0.40 + 1094 / (sn + 1) ** 5.19)
        + 2.32 * math.log10(mr_psi)
        - 8.07
    )


def residual(sn: float, data: AASHTO93Input) -> float:
    return aashto_log10_w18(
        sn,
        zr=data.zr,
        s0=data.s0,
        delta_psi=data.delta_psi,
        mr_psi=convert_mr_to_psi(data.resilient_modulus, data.original_mr_unit),
    ) - math.log10(data.w18)


def validate_input(data: AASHTO93Input) -> None:
    if (
        not data.design_id.strip()
        or not data.segment.strip()
        or not data.responsible.strip()
        or not data.justification.strip()
    ):
        raise ValueError("Diseño, tramo, responsable y justificación son obligatorios.")
    if not math.isfinite(data.w18) or data.w18 <= 0:
        raise ValueError("W18 debe ser finito y positivo.")
    convert_mr_to_psi(data.resilient_modulus, data.original_mr_unit)
    if data.w18 != data.esal_transfer.accumulated_esal:
        raise ValueError("W18 no coincide con la transferencia ESAL.")
    if (
        data.resilient_modulus != data.mr_transfer.adopted_mr
        or data.original_mr_unit != data.mr_transfer.unit
    ):
        raise ValueError("MR no coincide con la transferencia geotécnica.")
    if data.esal_transfer.is_demonstrative or data.mr_transfer.is_demonstrative:
        if not data.synthetic_acknowledged:
            raise ValueError("La entrada demostrativa exige reconocimiento explícito.")
    if data.zr_source == "CATALOGO":
        if data.zr_catalog_version != ZR_CATALOG_VERSION or data.zr != zr_from_catalog(
            data.reliability_percent
        ):
            raise ValueError("R y ZR son inconsistentes con el catálogo.")
    elif data.zr_source != "MANUAL_JUSTIFICADO":
        raise ValueError("Fuente ZR no admitida.")
    elif data.reliability_percent > 50 and data.zr >= 0:
        raise ValueError("Para R > 50 %, ZR debe ser negativo.")
    if not 50 <= data.reliability_percent <= 99:
        raise ValueError("R debe estar entre 50 % y 99 %.")
    if not math.isfinite(data.zr):
        raise ValueError("ZR debe ser finito.")
    if not math.isfinite(data.s0) or not 0.30 <= data.s0 <= 0.60:
        raise ValueError(
            "S0 debe ser finito y estar en el rango documentado 0,30–0,60."
        )
    if not data.s0_source.strip() or not data.s0_condition.strip():
        raise ValueError("S0 exige fuente y condición.")
    if (
        not all(math.isfinite(x) for x in (data.p0, data.pt, data.delta_psi))
        or not 0 < data.pt < data.p0 <= 5
    ):
        raise ValueError("Serviciabilidad inválida: se exige 0 < pt < p0 ≤ 5.")
    if not math.isclose(data.delta_psi, data.p0 - data.pt, abs_tol=1e-12):
        raise ValueError("ΔPSI debe ser p0 - pt.")
    s = data.solver
    if (
        not all(math.isfinite(x) for x in (s.sn_min, s.sn_max, s.tolerance))
        or s.sn_min <= 0
        or s.sn_max <= s.sn_min
    ):
        raise ValueError("Intervalo SN inválido.")
    if s.tolerance <= 0 or isinstance(s.max_iterations, bool) or s.max_iterations <= 0:
        raise ValueError("Tolerancia e iteraciones deben ser positivas.")
    if (
        not math.isfinite(s.boundary_margin_fraction)
        or not 0 <= s.boundary_margin_fraction <= MAX_BOUNDARY_MARGIN_FRACTION
    ):
        raise ValueError(
            "El margen de proximidad debe ser finito y estar entre 0 y 0,25."
        )


def solver_bound_warnings(
    sn: float, settings: SolverSettings
) -> tuple[tuple[str, ...], float]:
    """Advierte proximidad al borde sin alterar solución ni convergencia."""
    width = settings.sn_max - settings.sn_min
    margin = width * settings.boundary_margin_fraction
    if margin == 0:
        return (), margin
    warnings: list[str] = []
    lower_distance = sn - settings.sn_min
    upper_distance = settings.sn_max - sn
    lower_is_near = lower_distance <= margin or math.isclose(
        lower_distance, margin, rel_tol=1e-12, abs_tol=1e-12
    )
    upper_is_near = upper_distance <= margin or math.isclose(
        upper_distance, margin, rel_tol=1e-12, abs_tol=1e-12
    )
    if lower_is_near:
        warnings.append(
            f"{LOWER_BOUND_WARNING_CODE}: SN={sn:.6f}; límite inferior="
            f"{settings.sn_min:.6f}; margen={margin:.6f}. El SN calculado se "
            "encuentra muy próximo al límite inferior del intervalo de búsqueda. "
            "Amplíe SN mínimo hacia abajo y recalcule para confirmar que la raíz "
            "no está condicionada por el intervalo."
        )
    if upper_is_near:
        warnings.append(
            f"{UPPER_BOUND_WARNING_CODE}: SN={sn:.6f}; límite superior="
            f"{settings.sn_max:.6f}; margen={margin:.6f}. El SN calculado se "
            "encuentra muy próximo al límite superior del intervalo de búsqueda. "
            "Amplíe SN máximo y recalcule para confirmar que la raíz no está "
            "condicionada por el intervalo."
        )
    return tuple(warnings), margin


def input_fingerprint(data: AASHTO93Input) -> str:
    return _hash(data.as_dict())


def calculate_required_sn(data: AASHTO93Input) -> AASHTO93Result:
    validate_input(data)
    lo, hi = data.solver.sn_min, data.solver.sn_max
    flo, fhi = residual(lo, data), residual(hi, data)
    if not all(math.isfinite(x) for x in (flo, fhi)) or flo * fhi > 0:
        raise ValueError("El intervalo SN no encierra una raíz.")
    mid, fmid = lo, flo
    for iteration in range(1, data.solver.max_iterations + 1):
        mid = (lo + hi) / 2
        fmid = residual(mid, data)
        if not math.isfinite(fmid):
            raise ValueError("El residuo dejó de ser finito.")
        if abs(fmid) <= data.solver.tolerance:
            at = datetime.now(timezone.utc).isoformat()
            fp = input_fingerprint(data)
            bound_warnings, boundary_margin = solver_bound_warnings(mid, data.solver)
            warnings = tuple(
                dict.fromkeys(
                    data.inherited_warnings
                    + data.esal_transfer.warnings
                    + data.mr_transfer.warnings
                    + (MANDATORY_WARNING,)
                    + bound_warnings
                )
            )
            return AASHTO93Result(
                "sn5a-" + _hash((fp, at))[:16],
                at,
                fp,
                mid,
                data.w18,
                convert_mr_to_psi(data.resilient_modulus, data.original_mr_unit),
                data.reliability_percent,
                data.zr,
                data.s0,
                data.p0,
                data.pt,
                data.delta_psi,
                EQUATION,
                dict(COEFFICIENTS),
                fmid,
                iteration,
                (data.solver.sn_min, data.solver.sn_max),
                data.solver.tolerance,
                data.solver.boundary_margin_fraction,
                boundary_margin,
                True,
                data.esal_transfer,
                data.mr_transfer,
                warnings,
                data.esal_transfer.is_demonstrative
                or data.mr_transfer.is_demonstrative,
            )
        if flo * fmid <= 0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    raise ValueError(
        f"El solver no convergió en {data.solver.max_iterations} iteraciones; residuo={fmid:g}."
    )


def result_is_stale(result: AASHTO93Result, current: AASHTO93Input) -> bool:
    return result.input_fingerprint != input_fingerprint(current)


def store_result(
    session: MutableMapping[str, Any], data: AASHTO93Input, result: AASHTO93Result
) -> None:
    previous = session.get("aashto93_phase5a_result")
    if isinstance(previous, AASHTO93Result):
        session.setdefault("aashto93_phase5a_history", []).append(previous)
    session["aashto93_phase5a_input"] = data
    session["aashto93_phase5a_result"] = result
