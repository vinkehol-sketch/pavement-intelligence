"""Construcción central del corredor ficticio para el modo demostración.

Los valores declarados viven aquí; los resultados técnicos se obtienen llamando
los flujos oficiales. Este módulo no contiene una segunda implementación de TPDA,
ESAL, CBR/MR ni AASHTO 93.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
import random
from typing import Any

from pavement_intelligence.aashto93.layer_design_workflow import (
    DesignMode,
    LayerInput,
    LayerType,
    LayerWorkflowInput,
    SearchRange,
    SearchSettings,
    build_layer_transfer,
    calculate_layer_design,
    discrete_search,
)
from pavement_intelligence.aashto93.sn_workflow import (
    AASHTO93Input,
    SolverSettings,
    ZR_CATALOG_SOURCE,
    ZR_CATALOG_VERSION,
    build_esal_5a_transfer,
    build_mr_5a_transfer,
    calculate_required_sn,
    zr_from_catalog,
)
from pavement_intelligence.domain.traffic.ocr_presentation import (
    PlateReadingPresentation,
    PlateReviewRecord,
    PlateReviewStatus,
)
from pavement_intelligence.esal.projection_workflow import (
    CategoryGrowthRate,
    ProjectionWorkflowInput,
    TemporalFactorSource,
    build_projection_transfer,
    build_temporal_base,
    calculate_projection_workflow,
)
from pavement_intelligence.esal.workflow import (
    ESALWorkflowInput,
    build_esal_input_from_weighing,
    calculate_esal_workflow,
)
from pavement_intelligence.geotechnics.cbr_workflow import (
    CBRRecord,
    CBRWorkflowInput,
    DataOrigin,
    DesignCBRMode,
    calculate_cbr_workflow,
)
from pavement_intelligence.geotechnics.resilient_modulus_review import (
    AdoptionMode,
    ReviewInput,
    SensitivityBands,
    build_future_transfer,
    calculate_review,
)
from pavement_intelligence.integration.traffic_event_adapter import (
    adapt_traffic_event_for_review,
)
from pavement_intelligence.demo.metadata import (
    DEMO_PROJECT_METADATA,
    DEMO_REPORT_METADATA,
    DEMO_RESPONSIBLE_PARTIES,
    DEMO_REQUIRED_FIELDS,
    demo_widget_defaults,
)
from pavement_intelligence.reporting.workflow import (
    PHASES,
    AdministrativeData,
    ReportMode,
    ReportRequest,
    build_dossier,
    dossier_pdf_bytes,
)
from pavement_intelligence.traffic.tpda_workflow import (
    OFFICIAL_TPDA_CATEGORIES,
    ExpansionMethod,
    FactorTrace,
    ProjectionMethod,
    TPDAWorkflowInput,
    TemporalCoverage,
    TruckReclassification,
    calculate_tpda_workflow,
)
from pavement_intelligence.ui.utils.ocr_privacy import mask_plate
from pavement_intelligence.weighing.workflow import (
    WeighingCondition,
    WeighingSourceType,
    WeighingWorkflowInput,
    build_manual_observation,
    build_weighing_input_from_tpda,
    calculate_weighing_workflow,
)
from pavement_intelligence.vision.pipeline import TrafficEvent


DEMO_SEED = 20260720
DEMO_DATA_ORIGIN = "synthetic_demo"
DEMO_CASE_ID = "DEMO-CORREDOR-ANDINO-01"
DEMO_NOTICE = "DATOS SINTÉTICOS — SOLO DEMOSTRACIÓN"
DEMO_RESPONSIBLE = DEMO_RESPONSIBLE_PARTIES.study_lead
DEMO_REVIEWER = DEMO_RESPONSIBLE_PARTIES.reviewer
DEMO_REFERENCE_AT = "2026-07-18T14:00:00+00:00"
DEMO_SURVEY_HOURS = 2.0
DEMO_TEMPORAL_FACTOR = 12.0
DEMO_SEASONAL_FACTOR = 1.0
DEMO_TPDA_FORMULA = "106 × 12 × 1 = 1.272 veh/día"

# Conteo aprobado para cálculo. BUS se observa en visión, pero queda fuera del
# lote estructural por la limitación declarada del catálogo de ejes vigente.
DEMO_APPROVED_COUNTS = {
    "MOTO": 18,
    "AUTO": 36,
    "CAMIONETA": 14,
    "MINIBUS": 12,
    "BUS": 0,
    "C2": 12,
    "C3": 7,
    "TRACTOCAMION": 4,
    "ARTICULADO": 3,
    "OTRO_PESADO": 0,
}
DEMO_MONITORING_COUNTS = {
    **DEMO_APPROVED_COUNTS,
    "BUS": 6,
    "AUTO": 44,
}


@dataclass(frozen=True)
class DemoCase:
    """Caso completo ya calculado y su carga atómica de sesión."""

    case_id: str
    seed: int
    data_origin: str
    is_demo: bool
    notice: str
    session_payload: dict[str, Any]
    summary: dict[str, Any]


def _preliminary_category(final_category: str) -> tuple[str, str]:
    if final_category == "MOTO":
        return "motorcycle", "MOTO"
    if final_category in {"AUTO", "CAMIONETA"}:
        return "car", "AUTO"
    if final_category in {"MINIBUS", "BUS"}:
        return "bus", "BUS"
    return "truck", "CAMION"


def _traffic_events() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(DEMO_SEED)
    final_categories: list[str] = []
    for category, count in DEMO_APPROVED_COUNTS.items():
        final_categories.extend([category] * count)
    # Seis buses y ocho autos duplicados muestran pendientes iniciales y su
    # resolución manual sin contaminar el conteo técnico aprobado.
    excluded = ["BUS"] * 6 + ["AUTO"] * 8
    rng.shuffle(final_categories)
    rng.shuffle(excluded)
    categories = final_categories + excluded
    base = datetime.fromisoformat(DEMO_REFERENCE_AT)
    raw: list[dict[str, Any]] = []
    reviewed: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    approved_length = len(final_categories)
    for index, final_category in enumerate(categories, start=1):
        original_class, preliminary = _preliminary_category(final_category)
        direction = 1 if index % 2 else -1
        timestamp = base + timedelta(seconds=(index - 1) * 60)
        confidence = round(rng.uniform(0.58, 0.98), 4)
        if index > approved_length:
            confidence = round(rng.uniform(0.35, 0.54), 4)
        event = {
            "event_id": f"demo-event-{index:04d}",
            "track_id": index,
            "original_class": original_class,
            "category": preliminary,
            "confidence": confidence,
            "frame_number": index * 450,
            "video_second": float((index - 1) * 60),
            "direction": direction,
            "centroid_x": float(180 + (index * 37) % 720),
            "centroid_y": 360.0,
            "source": "demo://corredor-andino/video-ficticio",
            "processing_date": timestamp.isoformat(),
            "data_origin": DEMO_DATA_ORIGIN,
        }
        raw.append(dict(event))
        record = adapt_traffic_event_for_review(event)
        changed = final_category != preliminary
        if index <= approved_length:
            record.update(
                {
                    "validation_status": "corregido" if changed else "aceptado",
                    "corrected_category": final_category,
                    "correction_reason": (
                        "Clasificación ABC confirmada visualmente en el caso sintético."
                        if changed
                        else "Categoría automática confirmada en revisión demostrativa."
                    ),
                    "reviewed": True,
                    "reviewed_by": DEMO_REVIEWER,
                    "reviewed_at": (timestamp + timedelta(hours=3)).isoformat(),
                    "include_in_final_count": True,
                }
            )
        else:
            reason = (
                "Bus reservado fuera del lote estructural: configuración de ejes no confirmada."
                if final_category == "BUS"
                else "Cruce duplicado identificado durante la revisión manual demostrativa."
            )
            record.update(
                {
                    "validation_status": "descartado",
                    "corrected_category": final_category,
                    "correction_reason": reason,
                    "reviewed": True,
                    "reviewed_by": DEMO_REVIEWER,
                    "reviewed_at": (timestamp + timedelta(hours=3)).isoformat(),
                    "include_in_final_count": False,
                }
            )
            history.append(
                {
                    "event_id": event["event_id"],
                    "initial_status": "requiere_revision",
                    "final_status": "descartado",
                    "reason": reason,
                    "data_origin": DEMO_DATA_ORIGIN,
                    "is_demo": True,
                }
            )
        reviewed.append(record)
    return raw, reviewed, history


def build_demo_traffic_events() -> list[dict[str, Any]]:
    """Devuelve una copia reproducible de los cruces sintéticos sin revisión."""
    raw, _, _ = _traffic_events()
    return raw


def build_demo_plate_readings() -> tuple[PlateReadingPresentation, ...]:
    """Lecturas inequívocamente ficticias; nunca son fuente del aforo."""
    specs = (
        ("DEMO-01", 0.98, PlateReviewStatus.VALID, ("DEMO-01",)),
        ("FICT-?2", 0.54, PlateReviewStatus.DOUBTFUL, ("FICT-02", "FICT-12")),
        ("TEST-X3", 0.82, PlateReviewStatus.PENDING, ("TEST-X3", "TEST-03")),
        ("", 0.12, PlateReviewStatus.ILLEGIBLE, ()),
    )
    base = datetime.fromisoformat(DEMO_REFERENCE_AT)
    return tuple(
        PlateReadingPresentation(
            reading_id=f"DEMO-OCR-{index:03d}",
            track_id=f"DEMO-TRACK-{index:03d}",
            event_id=f"demo-event-{index:04d}",
            timestamp=base + timedelta(minutes=index),
            original_text=text,
            masked_text=mask_plate(text),
            confidence=confidence,
            vehicle_category=("Automóvil", "Minibús", "Camión C2", "Motocicleta")[index - 1],
            direction="Norte → Sur" if index % 2 else "Sur → Norte",
            status=status,
            crop_image_path=f"generated://demo-plate/{index}",
            frame_image_path="data/samples/ui/assets/traffic_monitoring_urban_avenue.png",
            suggested_alternatives=alternatives,
            data_origin=DEMO_DATA_ORIGIN,
        )
        for index, (text, confidence, status, alternatives) in enumerate(specs, start=1)
    )


def _ocr_reviews(
    readings: tuple[PlateReadingPresentation, ...],
) -> dict[str, PlateReviewRecord]:
    reviewed_at = datetime.fromisoformat("2026-07-18T17:00:00+00:00")
    return {
        readings[0].reading_id: PlateReviewRecord(
            readings[0].reading_id,
            readings[0].original_text,
            readings[0].original_text,
            PlateReviewStatus.VALID,
            "Confirmada sin cambios en demostración",
            "Placa ficticia",
            DEMO_REVIEWER,
            reviewed_at,
            DEMO_DATA_ORIGIN,
        ),
        readings[1].reading_id: PlateReviewRecord(
            readings[1].reading_id,
            readings[1].original_text,
            "FICT-02",
            PlateReviewStatus.VALID,
            "Carácter confundido por OCR",
            "Corrección sintética trazable",
            DEMO_REVIEWER,
            reviewed_at,
            DEMO_DATA_ORIGIN,
        ),
    }


def build_demo_tpda_input() -> TPDAWorkflowInput:
    """Devuelve el contrato TPDA oficial y reproducible del caso demo."""
    automatic = {category: 0 for category in OFFICIAL_TPDA_CATEGORIES}
    automatic.update(DEMO_APPROVED_COUNTS)
    reclassifications = tuple(
        TruckReclassification(
            original_category="CAMION",
            corrected_category=category,
            reason="Configuración visual confirmada en revisión manual sintética.",
            reviewer=DEMO_REVIEWER,
            corrected_at="2026-07-18T17:15:00+00:00",
            data_origin=DEMO_DATA_ORIGIN,
        )
        for category in ("C2", "C3", "TRACTOCAMION", "ARTICULADO")
    )
    return TPDAWorkflowInput(
        batch_id=DEMO_CASE_ID,
        source="Aforo revisado del corredor ficticio, ventana de 2 horas",
        data_origin=DEMO_DATA_ORIGIN,
        automatic_counts=automatic,
        corrected_counts=dict(DEMO_APPROVED_COUNTS),
        pending_categories={"CAMION_NO_CONFIRMADO": 0},
        temporal_coverage=TemporalCoverage(
            declared_hours=DEMO_SURVEY_HOURS,
            verified_hours=DEMO_SURVEY_HOURS,
            duration_source="Intervalo ISO sintético 14:00–16:00 visible en el caso",
            operator_confirmed=True,
        ),
        expansion_method=ExpansionMethod.UNIFORM_24_OVER_HOURS,
        temporal_factor=None,
        seasonal_factor=FactorTrace(
            symbol="FE",
            name="Factor estacional",
            value=DEMO_SEASONAL_FACTOR,
            function="Identidad: sin ajuste estacional en el caso",
            source="Supuesto demostrativo visible; valor neutro 1,0",
            applicability="Corredor ficticio y fecha sintética",
        ),
        projection_method=ProjectionMethod.EXPONENTIAL,
        growth_rate_percent=4.0,
        design_period_years=20,
        base_year=2026,
        directional_factor=0.52,
        lane_distribution_factor=1.0,
        reviewer=DEMO_REVIEWER,
        reclassifications=reclassifications,
        warnings=(
            "BUS y OTRO_PESADO no ingresan al lote estructural por configuración de ejes no confirmada.",
        ),
        assumptions=(
            "Expansión uniforme 24/2 = 12 seleccionada de forma visible.",
            "Tasa geométrica anual 4,0 %, periodo 20 años, FDD 0,52 y FDC 1,00.",
        ),
        is_synthetic=True,
        synthetic_acknowledged=True,
    )


def _tpda() -> tuple[Any, Any]:
    data = build_demo_tpda_input()
    return data, calculate_tpda_workflow(data)


def _weighing(tpda_result: Any) -> tuple[Any, Any, Any]:
    transfer = build_weighing_input_from_tpda(
        tpda_result,
        allow_demonstration=True,
        transferred_at="2026-07-18T17:20:00+00:00",
    )
    specs = (
        ("C2", (("simple_single", 50.0), ("simple_dual", 90.0))),
        ("C2", (("simple_single", 48.0), ("simple_dual", 85.0))),
        ("C3", (("simple_single", 50.0), ("tandem", 150.0))),
        ("C3", (("simple_single", 52.0), ("tandem", 158.0))),
        ("TRACTOCAMION", (("simple_single", 55.0), ("tandem", 160.0))),
        ("TRACTOCAMION", (("simple_single", 52.0), ("tandem", 154.0))),
        ("ARTICULADO", (("simple_single", 55.0), ("tandem", 160.0), ("tandem", 150.0))),
        ("ARTICULADO", (("simple_single", 53.0), ("tandem", 155.0), ("tandem", 148.0))),
    )
    observations = tuple(
        build_manual_observation(
            category=category,
            gross_weight=sum(load for _, load in groups),
            axle_groups=groups,
            unit="kN",
            source_type=WeighingSourceType.DEMONSTRATION_LIBRARY,
            source_reference="Biblioteca sintética central del corredor DEMO-CORREDOR-ANDINO-01",
            condition=WeighingCondition.SYNTHETIC,
            reviewer=DEMO_REVIEWER,
            timestamp=(
                datetime.fromisoformat("2026-07-18T15:00:00+00:00")
                + timedelta(minutes=index * 5)
            ).isoformat(),
            notes="Carga y configuración ficticias, visibles y exclusivas de demostración.",
        )
        for index, (category, groups) in enumerate(specs)
    )
    data = WeighingWorkflowInput(
        tpda_transfer=transfer,
        observations=observations,
        source_type=WeighingSourceType.DEMONSTRATION_LIBRARY,
        source_reference="Caso sintético centralizado; sin pesaje de campo",
        source_date="2026-07-18",
        reviewer=DEMO_REVIEWER,
        validation_state="REVISADO_PARA_DEMOSTRACION",
        assumptions=(
            "Pesos brutos iguales a la suma declarada de grupos de ejes.",
            "Solo categorías con configuración confirmada por el catálogo vigente.",
        ),
        warnings=(DEMO_NOTICE,),
        synthetic_acknowledged=True,
    )
    return transfer, data, calculate_weighing_workflow(data)


def _esal(weighing_result: Any) -> tuple[Any, Any, Any, Any, Any]:
    transfer = build_esal_input_from_weighing(
        weighing_result,
        allow_demonstration=True,
        transferred_at="2026-07-18T17:30:00+00:00",
    )
    data = ESALWorkflowInput(
        weighing_transfer=transfer,
        reviewer=DEMO_REVIEWER,
        synthetic_acknowledged=True,
        assumptions=(
            "Equivalencia calculada por el método demostrativo vigente del proyecto.",
            "No se asignan factores ocultos a categorías sin observación válida.",
        ),
    )
    result = calculate_esal_workflow(data)
    projection_transfer = build_projection_transfer(
        result,
        allow_demonstration=True,
        transferred_at="2026-07-18T17:35:00+00:00",
    )
    temporal = build_temporal_base(
        start_at="2026-07-18T14:00:00+00:00",
        end_at="2026-07-18T16:00:00+00:00",
        observed_hours=2.0,
        observed_days=2.0 / 24.0,
        factor_source=TemporalFactorSource.CALCULATED_DURATION,
        source_reference="Ventana sintética declarada y verificada",
        responsible=DEMO_RESPONSIBLE,
        justification="Expandir la observación ficticia de dos horas a base diaria.",
        notes="Factor visible 24/2 = 12.",
    )
    projection_input = ProjectionWorkflowInput(
        transfer=projection_transfer,
        temporal_base=temporal,
        base_year=2026,
        projection_years=20,
        directional_distribution_factor=0.52,
        lane_distribution_factor=1.0,
        operating_days_per_year=365,
        growth_rates=tuple(
            CategoryGrowthRate(
                category=category,
                annual_rate_percent=4.0,
                source="Supuesto visible del caso demostrativo",
                condition="SINTETICO_DEMOSTRATIVO",
            )
            for category in projection_transfer.categories
        ),
        reviewer=DEMO_REVIEWER,
        synthetic_acknowledged=True,
        assumptions=(
            "Proyección geométrica por categoría a 20 años.",
            "FDD 0,52; FDC 1,00; 365 días/año.",
        ),
    )
    projection_result = calculate_projection_workflow(projection_input)
    return transfer, data, result, projection_input, projection_result


def _geotechnics() -> tuple[Any, Any, Any, Any, Any, Any]:
    records = tuple(
        CBRRecord(
            record_id=f"DEMO-CBR-{index:02d}",
            study_id="DEMO-GEO-01",
            project_segment="Corredor Andino ficticio — Tramo A",
            location=f"Progresiva ficticia K{index}+000",
            depth_m=1.2 + index * 0.3,
            sample_type="Muestra alterada sintética",
            sample_condition="Saturada para demostración",
            cbr_2_5_mm_percent=value,
            cbr_5_0_mm_percent=value - 0.2,
            reported_cbr_percent=value,
            selection_criterion="Valor sintético reportado a 2,5 mm",
            compaction_percent=95.0,
            dry_density_kn_m3=18.0 + index * 0.2,
            moisture_condition="Saturada",
            saturated=True,
            compaction_energy="Proctor modificado declarado; sin ensayo real",
            test_date=f"2026-07-{10 + index:02d}",
            laboratory_or_source="Laboratorio ficticio DEMO-LAB; no verificable",
            responsible=DEMO_RESPONSIBLE,
            declared_standard="ASTM D1883 / AASHTO T 193 declarado solo como contexto",
            data_origin=DataOrigin.SYNTHETIC.value,
            observations=DEMO_NOTICE,
        )
        for index, value in enumerate((6.5, 7.0, 7.5), start=1)
    )
    cbr_input = CBRWorkflowInput(
        study_id="DEMO-GEO-01",
        project_segment="Corredor Andino ficticio — Tramo A",
        records=records,
        design_mode=DesignCBRMode.AVERAGE.value,
        correlation_id="LINEAL_1500_PSI",
        reviewer=DEMO_REVIEWER,
        synthetic_acknowledged=True,
        output_unit="MPa",
        assumptions=(
            "CBR de diseño = promedio explícito de tres muestras sintéticas.",
            "Correlación LINEAL_1500_PSI seleccionada del catálogo existente.",
        ),
    )
    cbr_result = calculate_cbr_workflow(cbr_input)
    review_input = ReviewInput(
        source_result=cbr_result,
        sensitivity_bands=SensitivityBands(10.0, 30.0),
        adoption_mode=AdoptionMode.CORRELATION_SELECTION.value,
        selected_correlation_id="LINEAL_1500_PSI",
        responsible=DEMO_REVIEWER,
        justification="Adoptar de forma visible la única correlación aplicable al CBR sintético.",
        source_demonstrative_acknowledged=True,
    )
    review_result = calculate_review(review_input)
    future = build_future_transfer(
        review_result,
        review_input,
        transferred_at="2026-07-18T17:45:00+00:00",
    )
    return records, cbr_input, cbr_result, review_input, review_result, future


def _aashto(
    projection_input: Any,
    projection_result: Any,
    mr_review_input: Any,
    mr_future: Any,
) -> tuple[Any, Any, Any, Any, Any]:
    esal_transfer = build_esal_5a_transfer(
        projection_result,
        projection_input,
        transferred_at="2026-07-18T17:50:00+00:00",
    )
    mr_transfer = build_mr_5a_transfer(
        mr_future,
        study_id="DEMO-GEO-01",
        adoption_mode=mr_review_input.adoption_mode,
        evidence="Correlación empírica seleccionada y limitaciones visibles",
    )
    sn_input = AASHTO93Input(
        design_id="DEMO-AASHTO93-01",
        segment="Corredor Andino ficticio — Tramo A",
        esal_transfer=esal_transfer,
        mr_transfer=mr_transfer,
        w18=esal_transfer.accumulated_esal,
        resilient_modulus=mr_transfer.adopted_mr,
        original_mr_unit=mr_transfer.unit,
        reliability_percent=90.0,
        zr=zr_from_catalog(90.0),
        zr_source="CATALOGO",
        zr_catalog_version=ZR_CATALOG_VERSION,
        s0=0.45,
        s0_source="Parámetro demostrativo visible; requiere validación profesional",
        s0_condition="DEMOSTRATIVO",
        p0=4.2,
        pt=2.5,
        delta_psi=1.7,
        analysis_period="2026–2045 (20 años)",
        parameter_sources=(
            ("W18", "Transferencia trazable Fase 3B"),
            ("MR", "Transferencia trazable Fase 4B"),
            ("R/ZR", ZR_CATALOG_SOURCE),
            ("S0", "Supuesto demostrativo visible 0,45"),
            ("p0/pt", "Selección demostrativa visible 4,2/2,5"),
        ),
        responsible=DEMO_REVIEWER,
        justification="Evaluar el corredor ficticio con el motor AASHTO 93 flexible existente.",
        inherited_warnings=tuple(
            dict.fromkeys(esal_transfer.warnings + mr_transfer.warnings + (DEMO_NOTICE,))
        ),
        solver=SolverSettings(0.01, 15.0, 0.0001, 100, 0.02),
        synthetic_acknowledged=True,
        created_at="2026-07-18T17:55:00+00:00",
    )
    sn_result = calculate_required_sn(sn_input)
    layer_transfer = build_layer_transfer(
        sn_result,
        sn_input,
        transferred_at="2026-07-18T18:00:00+00:00",
    )
    catalog_source = "Catálogo local demostrativo existente; validar fuente primaria"
    base_layers = (
        LayerInput(
            "DEMO-LAYER-AC",
            LayerType.ASPHALT.value,
            "Concreto asfáltico sintético",
            4.0,
            "in",
            0.44,
            catalog_source,
            "DEMOSTRATIVO_NO_NORMATIVO",
            1.0,
            "No aplica a carpeta",
            0.0,
            "m1 = 1,0 visible",
            "Selección visible del caso",
            3.0,
        ),
        LayerInput(
            "DEMO-LAYER-BASE",
            LayerType.BASE.value,
            "Base granular sintética",
            8.0,
            "in",
            0.14,
            catalog_source,
            "DEMOSTRATIVO_NO_NORMATIVO",
            0.90,
            "Buena declarada",
            15.0,
            "Supuesto demostrativo visible m2 = 0,90",
            "Selección visible del caso",
            4.0,
        ),
        LayerInput(
            "DEMO-LAYER-SUBBASE",
            LayerType.SUBBASE.value,
            "Subbase granular sintética",
            8.0,
            "in",
            0.11,
            catalog_source,
            "DEMOSTRATIVO_NO_NORMATIVO",
            0.85,
            "Regular declarada",
            25.0,
            "Supuesto demostrativo visible m3 = 0,85",
            "Selección visible del caso",
            4.0,
        ),
    )
    search = SearchSettings(
        ranges=(
            SearchRange(LayerType.ASPHALT.value, 3.0, 8.0, 0.5),
            SearchRange(LayerType.BASE.value, 4.0, 12.0, 1.0),
            SearchRange(LayerType.SUBBASE.value, 4.0, 16.0, 1.0),
        ),
        maximum_combinations=2_000,
        order_by="MENOR_EXCEDENTE_SN",
    )
    provisional = LayerWorkflowInput(
        transfer=layer_transfer,
        layers=base_layers,
        mode=DesignMode.DISCRETE.value,
        compliance_tolerance=0.01,
        responsible=DEMO_REVIEWER,
        justification="Búsqueda discreta visible con rangos e incrementos declarados.",
        search=search,
        created_at="2026-07-18T18:05:00+00:00",
    )
    alternatives = discrete_search(provisional)
    if not alternatives:
        raise ValueError("El rango demostrativo no produjo una alternativa de capas.")
    selected = dict(alternatives[0].thicknesses_in)
    adopted_layers = tuple(
        replace(layer, thickness=selected[layer.layer_type]) for layer in base_layers
    )
    layer_input = replace(provisional, layers=adopted_layers)
    layer_result = calculate_layer_design(layer_input)
    return sn_input, sn_result, layer_transfer, layer_input, layer_result


def build_demo_case() -> DemoCase:
    """Calcula el caso de extremo a extremo con contratos oficiales."""
    raw, reviewed, review_history = _traffic_events()
    readings = build_demo_plate_readings()
    ocr_reviews = _ocr_reviews(readings)
    tpda_input, tpda_result = _tpda()
    weighing_transfer, weighing_input, weighing_result = _weighing(tpda_result)
    esal_transfer, esal_input, esal_result, projection_input, projection_result = _esal(
        weighing_result
    )
    (
        cbr_records,
        cbr_input,
        cbr_result,
        mr_review_input,
        mr_review_result,
        mr_future,
    ) = _geotechnics()
    sn_input, sn_result, layer_transfer, layer_input, layer_result = _aashto(
        projection_input,
        projection_result,
        mr_review_input,
        mr_future,
    )
    widget_defaults = demo_widget_defaults()
    widget_defaults.update(
        {
            "esal3b_source": TemporalFactorSource.CALCULATED_DURATION,
            "geotech_design_mode": DesignCBRMode.AVERAGE,
            "geotech_origin": DataOrigin.SYNTHETIC,
            "geotech_correlation_id": cbr_input.correlation_id,
            "geotech_output_unit": cbr_input.output_unit,
            "geotech_4b_mode": AdoptionMode.CORRELATION_SELECTION,
            "geotech_4b_selected": mr_review_input.selected_correlation_id,
            "aashto5a_reliability": sn_input.reliability_percent,
            "aashto5a_zr_mode": sn_input.zr_source,
            "aashto5a_zr": sn_input.zr,
            "aashto5a_s0": sn_input.s0,
            "aashto5a_p0": sn_input.p0,
            "aashto5a_pt": sn_input.pt,
            "aashto5a_sn_min": sn_input.solver.sn_min,
            "aashto5a_sn_max": sn_input.solver.sn_max,
            "aashto5a_tolerance": sn_input.solver.tolerance,
            "aashto5a_max_iterations": sn_input.solver.max_iterations,
            "aashto5a_boundary_margin": sn_input.solver.boundary_margin_fraction,
            "5b_mode": layer_input.mode,
            "5b_tolerance": layer_input.compliance_tolerance,
            "5b_order": layer_input.search.order_by,
            "report_included_phases": list(PHASES),
        }
    )
    for rate in projection_input.growth_rates:
        widget_defaults[f"esal3b_rate_{rate.category}"] = rate.annual_rate_percent
        widget_defaults[f"esal3b_src_{rate.category}"] = rate.source
        widget_defaults[f"esal3b_cond_{rate.category}"] = rate.condition
    for layer in layer_input.layers:
        widget_defaults[f"5b_mat_{layer.layer_type}"] = layer.material
        widget_defaults[f"5b_unit_{layer.layer_type}"] = layer.thickness_unit
        widget_defaults[f"5b_d_{layer.layer_type}"] = layer.thickness
        widget_defaults[f"5b_a_{layer.layer_type}"] = layer.structural_coefficient
        widget_defaults[f"5b_asource_{layer.layer_type}"] = layer.coefficient_source
        widget_defaults[f"5b_m_{layer.layer_type}"] = layer.drainage_coefficient
        widget_defaults[f"5b_q_{layer.layer_type}"] = layer.drainage_quality
        widget_defaults[f"5b_sat_{layer.layer_type}"] = layer.saturation_time_percent
        widget_defaults[f"5b_msource_{layer.layer_type}"] = layer.drainage_source
        widget_defaults[f"5b_min_{layer.layer_type}"] = layer.minimum_thickness or 0.0
    for search_range in layer_input.search.ranges:
        widget_defaults[f"5b_smin_{search_range.layer_type}"] = search_range.minimum_in
        widget_defaults[f"5b_smax_{search_range.layer_type}"] = search_range.maximum_in
        widget_defaults[f"5b_sinc_{search_range.layer_type}"] = search_range.increment_in
    for reading in readings:
        review = ocr_reviews.get(reading.reading_id)
        widget_defaults[f"ocr_corrected_{reading.reading_id}"] = (
            review.corrected_text if review and review.corrected_text is not None else reading.original_text
        )
        widget_defaults[f"ocr_reason_{reading.reading_id}"] = (
            review.reason
            if review and review.reason == "Carácter confundido por OCR"
            else "Otro" if review and review.reason else "Seleccione un motivo..."
        )
        widget_defaults[f"ocr_notes_{reading.reading_id}"] = review.notes if review else ""
    payload: dict[str, Any] = {
        "demo_mode_active": True,
        "demo_case_id": DEMO_CASE_ID,
        "demo_seed": DEMO_SEED,
        "demo_notice": DEMO_NOTICE,
        "data_origin": DEMO_DATA_ORIGIN,
        "is_demo": True,
        "demo_loaded_at": "2026-07-18T18:10:00+00:00",
        "demo_review_history": review_history,
        "demo_project_metadata": asdict(DEMO_PROJECT_METADATA),
        "demo_responsible_parties": asdict(DEMO_RESPONSIBLE_PARTIES),
        "demo_traffic_inputs": {
            "video_source": "demo://corredor-andino/video-ficticio",
            "survey_date": DEMO_PROJECT_METADATA.study_date.isoformat(),
            "schedule": "14:00–16:00",
            "directions": ("ASCENDENTE", "DESCENDENTE"),
            "counting_station": "DEMO-LINE-01",
            "operator": DEMO_RESPONSIBLE_PARTIES.traffic_operator,
            "reviewer": DEMO_RESPONSIBLE_PARTIES.reviewer,
            "data_origin": DEMO_DATA_ORIGIN,
            "is_demo": True,
        },
        "demo_tpda_inputs": tpda_input,
        "demo_weighing_inputs": weighing_input,
        "demo_esal_inputs": {"phase_3a": esal_input, "phase_3b": projection_input},
        "demo_geotechnical_inputs": {"phase_4a": cbr_input, "phase_4b": mr_review_input},
        "demo_pavement_inputs": {"phase_5a": sn_input, "phase_5b": layer_input},
        "demo_report_metadata": dict(DEMO_REPORT_METADATA),
        "demo_required_field_audit": DEMO_REQUIRED_FIELDS,
        "demo_widget_keys": tuple(widget_defaults),
        "demo_module_provenance": {
            module: {"data_origin": DEMO_DATA_ORIGIN, "is_demo": True}
            for module in (
                "monitoring",
                "traffic_review",
                "ocr_experimental",
                "tpda_projection",
                "weighing",
                "esal",
                "geotechnics",
                "aashto93",
                "reporting",
            )
        },
        "vision_events_raw": raw,
        "vision_events_reviewed": reviewed,
        "vision_batch_metadata": {
            "model_name": "YOLO — salida sintética; algoritmo no ejecutado",
            "line_id": "DEMO-LINE-01",
            "line_y": 360,
            "source_video": "demo://corredor-andino/video-ficticio",
            "processing_date": DEMO_REFERENCE_AT,
            "configuration_version": "DEMO-1.0",
            "data_origin": DEMO_DATA_ORIGIN,
            "is_demo": True,
        },
        "traffic_counts_corrected": dict(DEMO_APPROVED_COUNTS),
        "traffic_review_approved": True,
        "is_synthetic_review": True,
        "traffic_review_source_fingerprint": f"synthetic-demo:{DEMO_SEED}",
        "tpda_input_from_review": {
            "batch_id": DEMO_CASE_ID,
            "counts_by_category": dict(DEMO_APPROVED_COUNTS),
            "total": sum(DEMO_APPROVED_COUNTS.values()),
            "duration_hours": DEMO_SURVEY_HOURS,
            "temporal_expansion_factor": DEMO_TEMPORAL_FACTOR,
            "seasonal_factor": DEMO_SEASONAL_FACTOR,
            "tpda_formula": DEMO_TPDA_FORMULA,
            "source": "demo://corredor-andino/video-ficticio",
            "data_origin": DEMO_DATA_ORIGIN,
            "reviewer": DEMO_REVIEWER,
            "is_synthetic": True,
            "is_demo": True,
            "warnings": [DEMO_NOTICE],
            "batch_hash": f"synthetic-demo:{DEMO_SEED}",
        },
        "demo_tpda_authoritative_input": tpda_input,
        "tpda_phase1_input": tpda_input,
        "tpda_phase1_result": tpda_result,
        "tpda_result": tpda_result,
        "aforos_registrados": 1,
        "processing_done": True,
        "events": tuple(TrafficEvent(**event) for event in raw),
        "corrected_records": reviewed,
        "weighing_input_from_tpda": weighing_transfer,
        "weighing_records_current": weighing_input.observations,
        "weighing_phase2_input": weighing_input,
        "weighing_phase2_result": weighing_result,
        "esal_input_from_weighing": esal_transfer,
        "esal_phase3_input": esal_input,
        "esal_phase3_result": esal_result,
        "esal_projection_transfer": projection_input.transfer,
        "esal_projection_input": projection_input,
        "esal_projection_result": projection_result,
        "esal_calculado": True,
        "geotechnical_cbr_records": cbr_records,
        "geotechnical_phase4a_input": cbr_input,
        "geotechnical_phase4a_result": cbr_result,
        "geotechnical_phase4b_input": mr_review_input,
        "geotechnical_phase4b_result": mr_review_result,
        "geotechnical_future_transfer": mr_future,
        "muestras_suelo": len(cbr_records),
        "aashto5a_esal_transfer": sn_input.esal_transfer,
        "aashto5a_mr_transfer": sn_input.mr_transfer,
        "aashto5a_contract_date": sn_input.created_at,
        "aashto93_phase5a_input": sn_input,
        "aashto93_phase5a_result": sn_result,
        "aashto5b_transfer": layer_transfer,
        "aashto5b_contract_date": layer_input.created_at,
        "aashto93_phase5b_input": layer_input,
        "aashto93_phase5b_result": layer_result,
        "diseno_calculado": True,
        "ocr_readings_raw": readings,
        "ocr_review_records": ocr_reviews,
        "ocr_selected_reading_id": readings[0].reading_id,
        "ocr_visible_reading_id": None,
        "ocr_reveal_audit": [],
        "ocr_filters": {},
        "integrated_dossier_history": [],
    }
    payload.update(widget_defaults)
    report_request = ReportRequest(
        administrative=AdministrativeData(
            project_name=DEMO_PROJECT_METADATA.project_name,
            segment=DEMO_PROJECT_METADATA.segment,
            location=DEMO_PROJECT_METADATA.location,
            organization=DEMO_PROJECT_METADATA.requesting_entity,
            responsible=DEMO_RESPONSIBLE_PARTIES.study_lead,
            reviewer=DEMO_RESPONSIBLE_PARTIES.reviewer,
            observations=(
                f"{DEMO_PROJECT_METADATA.observations} {DEMO_NOTICE}. "
                f"Base de tránsito demostrativa: aforo sintético "
                f"de 2 horas; {DEMO_TPDA_FORMULA}. Sin validez profesional ni normativa."
            ),
        ),
        mode=ReportMode.COMPLETE.value,
        included_phases=PHASES,
        partial_report_acknowledged=True,
        include_last_history=False,
    )
    dossier = build_dossier(payload, report_request, generated_at="2026-07-18T18:10:00+00:00")
    payload.update(
        {
            "integrated_report_request": report_request,
            "integrated_dossier": dossier,
            "integrated_dossier_pdf": dossier_pdf_bytes(dossier),
        }
    )
    summary = {
        "case_id": DEMO_CASE_ID,
        "data_origin": DEMO_DATA_ORIGIN,
        "is_demo": True,
        "observed_crossings": len(raw),
        "approved_crossings": sum(DEMO_APPROVED_COUNTS.values()),
        "initially_pending_events": len(review_history),
        "ocr_readings": len(readings),
        "declared_duration_hours": tpda_result.declared_duration_hours,
        "temporal_expansion_factor": tpda_result.temporal_expansion_factor,
        "seasonal_factor": tpda_result.seasonal_factor,
        "tpda_formula": DEMO_TPDA_FORMULA,
        "tpda_base": tpda_result.tpda_base_total,
        "projected_traffic": tpda_result.projected_traffic_total,
        "weighing_observations": weighing_result.observation_count,
        "design_esal_w18": projection_result.accumulated_esal,
        "design_cbr_percent": cbr_result.design_cbr_percent,
        "adopted_mr_mpa": mr_review_result.adopted_resilient_modulus_mpa,
        "required_sn": sn_result.required_sn,
        "provided_sn": layer_result.provided_sn,
        "layer_thicknesses_in": {
            item.layer_type: item.adopted_thickness_in for item in layer_result.contributions
        },
        "report_state": dossier.overall_state,
        "module_provenance": payload["demo_module_provenance"],
    }
    payload["demo_case_summary"] = summary
    return DemoCase(
        case_id=DEMO_CASE_ID,
        seed=DEMO_SEED,
        data_origin=DEMO_DATA_ORIGIN,
        is_demo=True,
        notice=DEMO_NOTICE,
        session_payload=payload,
        summary=summary,
    )
