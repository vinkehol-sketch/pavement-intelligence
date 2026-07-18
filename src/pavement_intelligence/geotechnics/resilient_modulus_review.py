"""Fase 4B: comparación y adopción controlada del módulo resiliente."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from enum import Enum
import hashlib
import json
import math
from typing import Any, MutableMapping

from .cbr_workflow import (
    CANONICAL_MR_UNIT, CATALOG_VERSION, GeotechnicalResult,
    convert_resilient_modulus, correlation_catalog, evaluate_correlation_mpa,
)


REVIEW_CONTRACT_VERSION = "1.0"
TRANSFER_VERSION = "1.0"
SOURCE_PRIORITY = (
    "ENSAYO_DIRECTO", "VALOR_MANUAL_VERIFICADO",
    "CORRELACION_EMPIRICA", "DEMOSTRATIVO_SINTETICO",
)
SENSITIVITY_WARNING = (
    "Las bandas de sensibilidad son demostrativas y configurables; no constituyen una regla normativa."
)


class AdoptionMode(str, Enum):
    CORRELATION_SELECTION = "SELECCION_DE_CORRELACION"
    CONSERVATIVE_VALUE = "VALOR_CONSERVADOR"
    DIRECT_TEST = "ENSAYO_DIRECTO"
    JUSTIFIED_MANUAL = "VALOR_MANUAL_JUSTIFICADO"


@dataclass(frozen=True)
class SensitivityBands:
    low_max_percent: float = 10.0
    moderate_max_percent: float = 30.0


@dataclass(frozen=True)
class CorrelationAlternative:
    correlation_id: str
    name: str
    equation: str
    interval_percent: tuple[float, float]
    resilient_modulus_mpa: float
    reference: str
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CorrelationComparison:
    design_cbr_percent: float
    alternatives: tuple[CorrelationAlternative, ...]
    absolute_difference_mpa: float | None
    relative_difference_percent: float | None
    sensitivity_level: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DiscontinuityPoint:
    cbr_percent: float
    alternatives: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class DiscontinuityAnalysis:
    boundary_cbr_percent: float
    epsilon: float
    immediately_before: DiscontinuityPoint
    at_boundary: DiscontinuityPoint
    immediately_after: DiscontinuityPoint
    cross_boundary_difference_percent: float
    warning: str


@dataclass(frozen=True)
class DirectTestEvidence:
    value: float
    unit: str
    laboratory: str
    procedure: str
    test_date: str
    responsible: str
    document_reference: str
    observations: str = ""


@dataclass(frozen=True)
class ReviewInput:
    source_result: GeotechnicalResult
    sensitivity_bands: SensitivityBands
    adoption_mode: str
    selected_correlation_id: str | None = None
    conservative_rule_accepted: bool = False
    manual_value: float | None = None
    manual_unit: str = CANONICAL_MR_UNIT
    manual_source: str = ""
    direct_test: DirectTestEvidence | None = None
    responsible: str = ""
    justification: str = ""
    source_demonstrative_acknowledged: bool = False
    catalog_version: str = CATALOG_VERSION


@dataclass(frozen=True)
class ResilientModulusReviewResult:
    review_id: str
    version: str
    reviewed_at: str
    study_id: str
    source_phase4a_result_id: str
    source_phase4a_fingerprint: str
    input_fingerprint: str
    design_cbr_percent: float
    cbr_selection_criterion: str
    alternatives: tuple[CorrelationAlternative, ...]
    absolute_difference_mpa: float | None
    relative_difference_percent: float | None
    sensitivity_level: str
    sensitivity_bands: SensitivityBands
    selected_correlation_id: str | None
    adopted_resilient_modulus_mpa: float
    canonical_unit: str
    adoption_mode: str
    adoption_reason: str
    responsible: str
    condition: str
    source: str
    confidence_level: str
    limitations: tuple[str, ...]
    evidence_available: str
    warnings: tuple[str, ...]
    catalog_version: str
    approved: bool
    is_demonstrative: bool
    is_stale: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FutureAASHTOTransfer:
    transfer_id: str
    version: str
    transferred_at: str
    geotechnical_review_id: str
    review_fingerprint: str
    adopted_resilient_modulus_mpa: float
    unit: str
    source: str
    responsible: str
    justification: str
    correlation_or_test: str
    is_demonstrative: bool
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_bands(bands: SensitivityBands) -> None:
    if (not math.isfinite(bands.low_max_percent)
            or not math.isfinite(bands.moderate_max_percent)
            or bands.low_max_percent < 0
            or bands.moderate_max_percent <= bands.low_max_percent):
        raise ValueError("Las bandas deben ser finitas, no negativas y crecientes.")


def compare_correlations(cbr_percent: float, bands: SensitivityBands = SensitivityBands()) -> CorrelationComparison:
    _validate_bands(bands)
    if not math.isfinite(cbr_percent) or cbr_percent <= 0:
        raise ValueError("El CBR debe ser finito y mayor que cero.")
    alternatives = tuple(
        CorrelationAlternative(
            item.correlation_id, item.name, item.equation,
            (item.minimum_cbr_percent, item.maximum_cbr_percent),
            evaluate_correlation_mpa(item, cbr_percent), item.reference,
            item.status, item.warnings,
        )
        for item in correlation_catalog().values()
        if item.minimum_cbr_percent <= cbr_percent <= item.maximum_cbr_percent
    )
    if not alternatives:
        return CorrelationComparison(cbr_percent, (), None, None, "SIN_CORRELACION_APLICABLE",
                                     ("Ninguna correlación vigente admite este CBR.",))
    values = [item.resilient_modulus_mpa for item in alternatives]
    minimum, maximum = min(values), max(values)
    if minimum <= 0:
        raise ValueError("El valor mínimo de MR debe ser positivo para calcular sensibilidad.")
    absolute = maximum - minimum
    relative = absolute / minimum * 100
    level = ("BAJA" if relative <= bands.low_max_percent else
             "MODERADA" if relative <= bands.moderate_max_percent else "ALTA")
    warnings = [SENSITIVITY_WARNING]
    if level == "ALTA":
        warnings.append("Sensibilidad ALTA: la adopción exige una decisión manual documentada.")
    return CorrelationComparison(cbr_percent, alternatives, absolute, relative, level, tuple(warnings))


def _point(cbr: float) -> DiscontinuityPoint:
    comparison = compare_correlations(cbr)
    return DiscontinuityPoint(cbr, tuple((x.correlation_id, x.resilient_modulus_mpa)
                                         for x in comparison.alternatives))


def analyze_discontinuity(boundary_cbr_percent: float = 20.0, epsilon: float = 0.01) -> DiscontinuityAnalysis:
    if not math.isfinite(epsilon) or epsilon <= 0 or boundary_cbr_percent - epsilon <= 0:
        raise ValueError("El incremento de discontinuidad debe ser finito y positivo.")
    before = _point(boundary_cbr_percent - epsilon)
    boundary = _point(boundary_cbr_percent)
    after = _point(boundary_cbr_percent + epsilon)
    if not before.alternatives or not after.alternatives:
        raise ValueError("No existen correlaciones a ambos lados del límite solicitado.")
    before_value = before.alternatives[-1][1]
    after_value = after.alternatives[0][1]
    difference = abs(after_value - before_value) / min(after_value, before_value) * 100
    return DiscontinuityAnalysis(
        boundary_cbr_percent, epsilon, before, boundary, after, difference,
        "Una variación pequeña del CBR puede causar un salto metodológico de MR; no implica necesariamente un cambio físico equivalente del suelo.",
    )


def review_input_fingerprint(data: ReviewInput) -> str:
    canonical = json.dumps(asdict(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def review_is_stale(result: ResilientModulusReviewResult, current_input: ReviewInput) -> bool:
    return (result.input_fingerprint != review_input_fingerprint(current_input)
            or result.source_phase4a_fingerprint != current_input.source_result.input_fingerprint
            or current_input.source_result.is_stale)


def _validate_direct(evidence: DirectTestEvidence) -> float:
    if not math.isfinite(evidence.value) or evidence.value <= 0:
        raise ValueError("El MR de ensayo directo debe ser finito y positivo.")
    try:
        date.fromisoformat(evidence.test_date)
    except ValueError as exc:
        raise ValueError("La fecha del ensayo directo debe usar ISO YYYY-MM-DD.") from exc
    if not all(value.strip() for value in (
        evidence.laboratory, evidence.procedure, evidence.responsible, evidence.document_reference
    )):
        raise ValueError("El ensayo directo exige laboratorio, procedimiento, responsable y documento.")
    return convert_resilient_modulus(evidence.value, evidence.unit, "MPa")


def calculate_review(data: ReviewInput) -> ResilientModulusReviewResult:
    source = data.source_result
    if source.is_stale:
        raise ValueError("El resultado Fase 4A está desactualizado.")
    if data.catalog_version != CATALOG_VERSION:
        raise ValueError("Versión del catálogo no vigente.")
    comparison = compare_correlations(source.design_cbr_percent, data.sensitivity_bands)
    try:
        mode = AdoptionMode(data.adoption_mode)
    except ValueError as exc:
        raise ValueError("Modo de adopción no permitido.") from exc
    if not data.responsible.strip() or not data.justification.strip():
        raise ValueError("Toda adopción exige responsable y justificación.")
    selected_id: str | None = None
    limitations = [SENSITIVITY_WARNING]
    warnings = list(comparison.warnings)
    if mode == AdoptionMode.CORRELATION_SELECTION:
        if not data.selected_correlation_id:
            raise ValueError("Debe seleccionar explícitamente una correlación.")
        selected = next((x for x in comparison.alternatives
                         if x.correlation_id == data.selected_correlation_id), None)
        if selected is None:
            raise ValueError("La correlación seleccionada no es aplicable al CBR.")
        if source.is_demonstrative and not data.source_demonstrative_acknowledged:
            raise ValueError("El origen demostrativo de Fase 4A exige aceptación explícita.")
        adopted = selected.resilient_modulus_mpa
        selected_id = selected.correlation_id
        condition, adopted_source, confidence = "ADOPTADO_PARA_DEMOSTRACION", "CORRELACION_EMPIRICA", "BAJA"
        evidence = selected.reference
        is_demo = True
    elif mode == AdoptionMode.CONSERVATIVE_VALUE:
        if not comparison.alternatives:
            raise ValueError("No existen correlaciones aplicables para adoptar un valor conservador.")
        if not data.conservative_rule_accepted:
            raise ValueError("Debe aceptar que conservador significa el menor MR y no es regla normativa.")
        if source.is_demonstrative and not data.source_demonstrative_acknowledged:
            raise ValueError("El origen demostrativo de Fase 4A exige aceptación explícita.")
        selected = min(comparison.alternatives, key=lambda item: item.resilient_modulus_mpa)
        adopted, selected_id = selected.resilient_modulus_mpa, selected.correlation_id
        condition, adopted_source, confidence = "ADOPTADO_PARA_DEMOSTRACION", "CORRELACION_EMPIRICA", "BAJA"
        evidence, is_demo = "Menor MR entre correlaciones aplicables; regla demostrativa aceptada", True
    elif mode == AdoptionMode.DIRECT_TEST:
        if data.direct_test is None:
            raise ValueError("ENSAYO_DIRECTO exige evidencia completa.")
        adopted = _validate_direct(data.direct_test)
        condition, adopted_source, confidence = "ENSAYO_DIRECTO", "ENSAYO_DIRECTO", "ALTA"
        evidence = f"{data.direct_test.laboratory}; {data.direct_test.document_reference}"
        limitations.append("La revisión documental y representatividad del ensayo siguen a cargo del responsable.")
        is_demo = False
    else:
        if data.manual_value is None or not math.isfinite(data.manual_value) or data.manual_value <= 0:
            raise ValueError("El valor manual debe ser finito y positivo.")
        if not data.manual_source.strip():
            raise ValueError("El valor manual justificado exige fuente verificable.")
        adopted = convert_resilient_modulus(data.manual_value, data.manual_unit, "MPa")
        condition, adopted_source, confidence = "ESTIMADO", "VALOR_MANUAL_VERIFICADO", "MEDIA"
        evidence = data.manual_source
        warnings.append("Valor manual justificado: no corresponde a un ensayo directo.")
        is_demo = True
    if not math.isfinite(adopted) or adopted <= 0:
        raise ValueError("El MR adoptado debe ser finito y positivo.")
    fingerprint = review_input_fingerprint(data)
    reviewed_at = datetime.now(timezone.utc).isoformat()
    review_id = "mr-review-" + hashlib.sha256(f"{fingerprint}:{reviewed_at}".encode()).hexdigest()[:16]
    return ResilientModulusReviewResult(
        review_id, REVIEW_CONTRACT_VERSION, reviewed_at, source.study_id, source.result_id,
        source.input_fingerprint, fingerprint, source.design_cbr_percent, source.design_mode,
        comparison.alternatives, comparison.absolute_difference_mpa,
        comparison.relative_difference_percent, comparison.sensitivity_level,
        data.sensitivity_bands, selected_id, adopted, CANONICAL_MR_UNIT,
        mode.value, data.justification.strip(), data.responsible.strip(), condition,
        adopted_source, confidence, tuple(limitations), evidence, tuple(dict.fromkeys(warnings)),
        data.catalog_version, True, is_demo,
    )


def store_review_result(
    session: MutableMapping[str, Any], data: ReviewInput, result: ResilientModulusReviewResult
) -> None:
    previous = session.get("geotechnical_phase4b_result")
    if isinstance(previous, ResilientModulusReviewResult):
        session.setdefault("geotechnical_phase4b_history", []).append(previous)
    session["geotechnical_phase4b_input"] = data
    session["geotechnical_phase4b_result"] = result
    session["geotechnical_future_transfer"] = None


def build_future_transfer(
    result: ResilientModulusReviewResult, current_input: ReviewInput,
    *, transferred_at: str | None = None,
) -> FutureAASHTOTransfer:
    if not result.approved:
        raise ValueError("La revisión geotécnica no está aprobada.")
    if review_is_stale(result, current_input):
        raise ValueError("La revisión geotécnica está desactualizada.")
    timestamp = transferred_at or datetime.now(timezone.utc).isoformat()
    seed = f"{result.review_id}:{result.input_fingerprint}:{timestamp}"
    correlation_or_test = result.selected_correlation_id or result.condition
    return FutureAASHTOTransfer(
        "future-aashto-" + hashlib.sha256(seed.encode()).hexdigest()[:16], TRANSFER_VERSION,
        timestamp, result.review_id, result.input_fingerprint, result.adopted_resilient_modulus_mpa,
        CANONICAL_MR_UNIT, result.source, result.responsible, result.adoption_reason,
        correlation_or_test, result.is_demonstrative, result.warnings,
    )
