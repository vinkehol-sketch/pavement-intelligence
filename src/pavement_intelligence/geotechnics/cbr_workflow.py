"""Flujo independiente y auditable CBR -> módulo resiliente (Fase 4A)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from enum import Enum
import hashlib
import json
import math
from statistics import mean
from typing import Any, MutableMapping


CONTRACT_VERSION = "1.0"
CATALOG_VERSION = "1.0"
RESULT_VERSION = "1.0"
CANONICAL_MR_UNIT = "MPa"
METHODOLOGY_WARNING = (
    "La estimación del módulo resiliente mediante CBR depende de una correlación empírica. "
    "No sustituye un ensayo directo de módulo resiliente ni constituye por sí sola un "
    "diseño estructural aprobado."
)


class DataOrigin(str, Enum):
    LABORATORY_TEST = "ENSAYO_LABORATORIO"
    FIELD_TEST = "ENSAYO_CAMPO"
    VERIFIED_MANUAL = "INGRESO_MANUAL_VERIFICADO"
    ESTIMATED = "VALOR_ESTIMADO"
    SYNTHETIC = "DEMOSTRATIVO_SINTETICO"


class DesignCBRMode(str, Enum):
    SINGLE_VALUE = "VALOR_UNICO"
    CONSERVATIVE_MINIMUM = "MINIMO_CONSERVADOR"
    PERCENTILE = "PERCENTIL"
    AVERAGE = "PROMEDIO"
    JUSTIFIED_MANUAL = "SELECCION_MANUAL_JUSTIFICADA"


@dataclass(frozen=True)
class CBRRecord:
    record_id: str
    study_id: str
    project_segment: str
    location: str
    depth_m: float
    sample_type: str
    sample_condition: str
    cbr_2_5_mm_percent: float | None
    cbr_5_0_mm_percent: float | None
    reported_cbr_percent: float
    selection_criterion: str
    compaction_percent: float | None
    dry_density_kn_m3: float | None
    moisture_condition: str
    saturated: bool
    compaction_energy: str | None
    test_date: str
    laboratory_or_source: str
    responsible: str
    declared_standard: str
    data_origin: str
    observations: str = ""
    warnings: tuple[str, ...] = ()
    is_valid: bool = True
    rejection_reason: str = ""
    contract_version: str = CONTRACT_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResilientModulusCorrelation:
    correlation_id: str
    name: str
    equation: str
    minimum_cbr_percent: float
    maximum_cbr_percent: float
    input_unit: str
    native_output_unit: str
    reference: str
    status: str
    warnings: tuple[str, ...]
    coefficients: tuple[tuple[str, float], ...]
    soil_condition: str
    extrapolation_allowed: bool
    version: str = CATALOG_VERSION


CORRELATIONS = (
    ResilientModulusCorrelation(
        "LINEAL_1500_PSI", "Lineal 1500 psi por punto CBR", "MR [psi] = 1500 × CBR",
        0.01, 10.0, "% CBR", "psi", "Documentación local cbr_modulo_resiliente.md y assumptions.md",
        "EMPIRICA_DEMOSTRATIVA_FUENTE_PRIMARIA_PENDIENTE",
        ("Aplicabilidad y atribución normativa requieren confirmación primaria.",),
        (("k", 1500.0),), "SUBRASANTE_GENERAL", False,
    ),
    ResilientModulusCorrelation(
        "LINEAL_3500_PSI_LOCAL", "Lineal local 3500 psi por punto CBR", "MR [psi] = 3500 × CBR",
        7.2, 20.0, "% CBR", "psi", "Correlación hallada en hojas de cálculo locales; ver cbr_modulo_resiliente.md",
        "DEMOSTRATIVA_NO_NORMATIVA", ("Fuente primaria y continuidad física no confirmadas.",),
        (("k", 3500.0),), "SUBRASANTE_GENERAL", False,
    ),
    ResilientModulusCorrelation(
        "LOG_4326_LOCAL", "Logarítmica local para CBR alto", "MR [psi] = 4326 × ln(CBR) + 241",
        20.0, 150.0, "% CBR", "psi", "Fórmula de planilla local; ver metodos_pendientes_confirmacion_pavimento.md",
        "DEMOSTRATIVA_NO_NORMATIVA", ("La documentación local advierte una discontinuidad pendiente de resolver.",),
        (("a", 4326.0), ("b", 241.0)), "SUBRASANTE_GENERAL", False,
    ),
)


@dataclass(frozen=True)
class CBRWorkflowInput:
    study_id: str
    project_segment: str
    records: tuple[CBRRecord, ...]
    design_mode: str
    correlation_id: str
    percentile: float | None = None
    manual_record_id: str | None = None
    manual_justification: str = ""
    reviewer: str = ""
    synthetic_acknowledged: bool = False
    output_unit: str = CANONICAL_MR_UNIT
    coefficient_overrides: tuple[tuple[str, float], ...] = ()
    catalog_version: str = CATALOG_VERSION
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeotechnicalResult:
    result_id: str
    version: str
    created_at: str
    input_fingerprint: str
    study_id: str
    project_segment: str
    design_cbr_percent: float
    design_mode: str
    percentile: float | None
    used_record_ids: tuple[str, ...]
    excluded_record_ids: tuple[str, ...]
    correlation_id: str
    correlation_name: str
    correlation_equation: str
    correlation_coefficients: tuple[tuple[str, float], ...]
    applicability_interval_percent: tuple[float, float]
    correlation_reference: str
    correlation_status: str
    resilient_modulus_mpa: float
    displayed_resilient_modulus: float
    displayed_unit: str
    value_origin: str
    warnings: tuple[str, ...]
    reviewer: str
    methodological_status: str
    is_demonstrative: bool
    is_stale: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeotechnicalTransfer:
    transfer_id: str
    version: str
    transferred_at: str
    source_result_id: str
    source_fingerprint: str
    design_cbr_percent: float
    resilient_modulus_mpa: float
    value_origin: str
    methodological_status: str
    project_segment: str


def correlation_catalog() -> dict[str, ResilientModulusCorrelation]:
    return {item.correlation_id: item for item in CORRELATIONS}


def convert_resilient_modulus(value: float, from_unit: str, to_unit: str) -> float:
    if not math.isfinite(value):
        raise ValueError("El módulo resiliente debe ser finito.")
    factors = {"MPa": 1.0, "kPa": 0.001, "psi": 0.006894757293168361, "ksi": 6.894757293168361}
    if from_unit not in factors or to_unit not in factors:
        raise ValueError("Unidad de módulo resiliente desconocida.")
    return value * factors[from_unit] / factors[to_unit]


def _validate_iso_date(value: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("La fecha del ensayo debe usar ISO YYYY-MM-DD.") from exc


def validate_cbr_record(record: CBRRecord) -> tuple[str, ...]:
    if record.contract_version != CONTRACT_VERSION:
        raise ValueError("Versión de contrato CBR no admitida.")
    if not record.record_id.strip() or not record.study_id.strip() or not record.project_segment.strip():
        raise ValueError("Registro, estudio y tramo son obligatorios.")
    if not math.isfinite(record.depth_m) or record.depth_m < 0:
        raise ValueError("La profundidad debe ser finita y no negativa.")
    values = [record.reported_cbr_percent]
    values.extend(x for x in (record.cbr_2_5_mm_percent, record.cbr_5_0_mm_percent) if x is not None)
    if any(not math.isfinite(x) or x <= 0 for x in values):
        raise ValueError("Todo CBR disponible debe ser finito y mayor que cero.")
    if any(x > 150 for x in values):
        raise ValueError("CBR fuera del rango físico razonable adoptado (máximo 150 %).")
    if record.compaction_percent is not None and (
        not math.isfinite(record.compaction_percent) or not 0 < record.compaction_percent <= 100
    ):
        raise ValueError("La compactación debe estar en (0, 100] %.")
    if record.dry_density_kn_m3 is not None and (
        not math.isfinite(record.dry_density_kn_m3) or record.dry_density_kn_m3 <= 0
    ):
        raise ValueError("La densidad seca debe ser finita y positiva.")
    _validate_iso_date(record.test_date)
    try:
        origin = DataOrigin(record.data_origin)
    except ValueError as exc:
        raise ValueError("Origen CBR no identificado.") from exc
    if not record.laboratory_or_source.strip() or not record.declared_standard.strip():
        raise ValueError("Fuente y procedimiento declarado son obligatorios.")
    if origin in {DataOrigin.VERIFIED_MANUAL, DataOrigin.ESTIMATED, DataOrigin.SYNTHETIC} and not record.responsible.strip():
        raise ValueError("Los datos manuales, estimados o sintéticos exigen responsable.")
    warnings = list(record.warnings)
    if record.cbr_2_5_mm_percent is None and record.cbr_5_0_mm_percent is None:
        warnings.append("Solo existe CBR final informado; no se dispone de valores individuales o curva.")
    elif not any(math.isclose(record.reported_cbr_percent, value, rel_tol=0, abs_tol=1e-9)
                 for value in (record.cbr_2_5_mm_percent, record.cbr_5_0_mm_percent)
                 if value is not None):
        warnings.append("El CBR reportado no coincide con 2,5 mm ni 5,0 mm; revisar el criterio declarado.")
    if record.compaction_percent is not None and record.compaction_percent < 90:
        warnings.append("Compactación menor a 90 %; revisar representatividad para servicio.")
    if not record.saturated:
        warnings.append("CBR no saturado; puede no representar la condición crítica de humedad.")
    return tuple(dict.fromkeys(warnings))


def percentile_linear(values: tuple[float, ...], percentile: float) -> float:
    if not values:
        raise ValueError("No existen valores para calcular el percentil.")
    if not math.isfinite(percentile) or not 0 <= percentile <= 100:
        raise ValueError("El percentil debe ser finito y estar entre 0 y 100.")
    ordered = sorted(values)
    rank = percentile / 100 * (len(ordered) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    fraction = rank - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def input_fingerprint(data: CBRWorkflowInput) -> str:
    canonical = json.dumps(asdict(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def result_is_stale(result: GeotechnicalResult, current_input: CBRWorkflowInput) -> bool:
    return result.input_fingerprint != input_fingerprint(current_input)


def _design_cbr(data: CBRWorkflowInput, records: tuple[CBRRecord, ...]) -> tuple[float, tuple[str, ...]]:
    mode = DesignCBRMode(data.design_mode)
    values = tuple(x.reported_cbr_percent for x in records)
    ids = tuple(x.record_id for x in records)
    if mode == DesignCBRMode.SINGLE_VALUE:
        if len(records) != 1:
            raise ValueError("VALOR_UNICO exige exactamente una muestra válida.")
        return values[0], ids
    if mode == DesignCBRMode.CONSERVATIVE_MINIMUM:
        value = min(values)
        return value, tuple(x.record_id for x in records if x.reported_cbr_percent == value)
    if mode == DesignCBRMode.AVERAGE:
        if len(records) < 2:
            raise ValueError("PROMEDIO exige al menos dos muestras y no presume representatividad.")
        return mean(values), ids
    if mode == DesignCBRMode.PERCENTILE:
        if data.percentile is None:
            raise ValueError("PERCENTIL exige declarar el percentil.")
        return percentile_linear(values, data.percentile), ids
    if not data.manual_record_id or not data.manual_justification.strip() or not data.reviewer.strip():
        raise ValueError("La selección manual exige registro, responsable y justificación.")
    selected = next((x for x in records if x.record_id == data.manual_record_id), None)
    if selected is None:
        raise ValueError("El registro seleccionado manualmente no es válido o está excluido.")
    return selected.reported_cbr_percent, (selected.record_id,)


def _native_modulus(correlation_id: str, cbr: float, coefficients: dict[str, float]) -> float:
    if correlation_id in {"LINEAL_1500_PSI", "LINEAL_3500_PSI_LOCAL"}:
        return coefficients["k"] * cbr
    if correlation_id == "LOG_4326_LOCAL":
        return coefficients["a"] * math.log(cbr) + coefficients["b"]
    raise ValueError("Correlación no implementada.")


def calculate_cbr_workflow(data: CBRWorkflowInput) -> GeotechnicalResult:
    if not data.study_id.strip() or not data.project_segment.strip() or not data.reviewer.strip():
        raise ValueError("Estudio, tramo y revisor son obligatorios.")
    if data.catalog_version != CATALOG_VERSION:
        raise ValueError("Versión del catálogo de correlaciones no vigente.")
    convert_resilient_modulus(1.0, "MPa", data.output_unit)
    valid: list[CBRRecord] = []
    excluded: list[str] = []
    warnings = [METHODOLOGY_WARNING]
    record_ids = [record.record_id for record in data.records]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("Los identificadores de registros CBR deben ser únicos.")
    synthetic_excluded = False
    for record in data.records:
        if not record.is_valid:
            excluded.append(record.record_id)
            continue
        record_warnings = validate_cbr_record(record)
        warnings.extend(f"{record.record_id}: {item}" for item in record_warnings)
        if record.data_origin == DataOrigin.SYNTHETIC.value and not data.synthetic_acknowledged:
            excluded.append(record.record_id)
            synthetic_excluded = True
            continue
        valid.append(record)
    if synthetic_excluded:
        warnings.append("Se excluyeron datos sintéticos no reconocidos explícitamente.")
    if not valid:
        raise ValueError("No existen registros CBR válidos habilitados para el cálculo.")
    design_cbr, used_ids = _design_cbr(data, tuple(valid))
    excluded.extend(x.record_id for x in valid if x.record_id not in used_ids)
    catalog = correlation_catalog()
    if data.correlation_id not in catalog:
        raise ValueError("La correlación debe seleccionarse explícitamente del catálogo vigente.")
    correlation = catalog[data.correlation_id]
    if not correlation.minimum_cbr_percent <= design_cbr <= correlation.maximum_cbr_percent:
        raise ValueError("CBR fuera del intervalo de aplicabilidad; no se permite extrapolación.")
    coefficients = dict(correlation.coefficients)
    for name, value in data.coefficient_overrides:
        if name not in coefficients:
            raise ValueError(f"Coeficiente desconocido: {name}.")
        if not math.isfinite(value):
            raise ValueError(f"Coeficiente {name} debe ser finito.")
        coefficients[name] = value
    if any(not math.isfinite(x) for x in coefficients.values()):
        raise ValueError("Los coeficientes deben ser finitos.")
    native = _native_modulus(correlation.correlation_id, design_cbr, coefficients)
    if not math.isfinite(native) or native <= 0:
        raise ValueError("La correlación produjo un módulo resiliente no positivo o no finito.")
    mr_mpa = convert_resilient_modulus(native, correlation.native_output_unit, "MPa")
    displayed = convert_resilient_modulus(mr_mpa, "MPa", data.output_unit)
    warnings.extend(correlation.warnings)
    used_origins = {x.data_origin for x in valid if x.record_id in used_ids}
    is_demo = bool(used_origins & {DataOrigin.ESTIMATED.value, DataOrigin.SYNTHETIC.value}) or "DEMOSTRATIVA" in correlation.status
    status = "VALIDO_PARA_DEMOSTRACION" if is_demo else "VALIDO_PARA_FUTURA_REVISION"
    origin = "MODULO_RESILIENTE_ESTIMADO_POR_CORRELACION"
    fingerprint = input_fingerprint(data)
    created = datetime.now(timezone.utc).isoformat()
    result_id = "geotech-" + hashlib.sha256(f"{fingerprint}:{created}".encode()).hexdigest()[:16]
    return GeotechnicalResult(
        result_id, RESULT_VERSION, created, fingerprint, data.study_id, data.project_segment,
        design_cbr, data.design_mode, data.percentile, used_ids, tuple(dict.fromkeys(excluded)),
        correlation.correlation_id, correlation.name, correlation.equation,
        tuple(coefficients.items()), (correlation.minimum_cbr_percent, correlation.maximum_cbr_percent),
        correlation.reference, correlation.status, mr_mpa, displayed, data.output_unit, origin,
        tuple(dict.fromkeys(warnings + list(data.assumptions))), data.reviewer, status, is_demo,
    )


def store_geotechnical_result(
    session: MutableMapping[str, Any], data: CBRWorkflowInput, result: GeotechnicalResult
) -> None:
    previous = session.get("geotechnical_phase4a_result")
    if isinstance(previous, GeotechnicalResult):
        session.setdefault("geotechnical_phase4a_history", []).append(previous)
    session["geotechnical_phase4a_input"] = data
    session["geotechnical_phase4a_result"] = result


def build_geotechnical_transfer(
    result: GeotechnicalResult, *, transferred_at: str | None = None
) -> GeotechnicalTransfer:
    if result.is_stale:
        raise ValueError("El resultado geotécnico está desactualizado.")
    timestamp = transferred_at or datetime.now(timezone.utc).isoformat()
    seed = f"{result.result_id}:{result.input_fingerprint}:{timestamp}"
    return GeotechnicalTransfer(
        "geotech-transfer-" + hashlib.sha256(seed.encode()).hexdigest()[:16], "1.0", timestamp,
        result.result_id, result.input_fingerprint, result.design_cbr_percent,
        result.resilient_modulus_mpa, result.value_origin, result.methodological_status,
        result.project_segment,
    )
