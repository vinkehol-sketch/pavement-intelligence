"""Metadatos y valores visibles del caso demostrativo.

Este módulo contiene únicamente entradas ficticias. Los resultados técnicos se
siguen construyendo con los motores oficiales en :mod:`pavement_intelligence.demo.case`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Any


DEMO_STUDY_DATE = date(2026, 7, 18)


@dataclass(frozen=True)
class DemoProjectMetadata:
    project_name: str
    project_code: str
    study_type: str
    location: str
    segment: str
    requesting_entity: str
    consultant: str
    study_date: date
    observations: str
    data_origin: str = "synthetic_demo"
    is_demo: bool = True


@dataclass(frozen=True)
class DemoResponsibleParties:
    study_lead: str
    traffic_operator: str
    reviewer: str
    pavement_designer: str
    report_prepared_by: str
    report_reviewed_by: str
    report_approved_by: str


@dataclass(frozen=True)
class DemoRequiredField:
    screen: str
    field: str
    state_key: str
    data_type: str
    validation: str
    demo_value: Any


DEMO_PROJECT_METADATA = DemoProjectMetadata(
    project_name="Evaluación demostrativa del Corredor Andino",
    project_code="DEMO-CORREDOR-ANDINO-01",
    study_type="Estudio demostrativo de tránsito y diseño de pavimento",
    location="Corredor vial ficticio, La Paz, Bolivia",
    segment="Progresiva ficticia 0+000 a 2+500",
    requesting_entity="Entidad Municipal Demostrativa",
    consultant="Equipo Pavement Intelligence",
    study_date=DEMO_STUDY_DATE,
    observations=(
        "Caso sintético generado exclusivamente para demostrar el flujo funcional "
        "de la plataforma."
    ),
)

DEMO_RESPONSIBLE_PARTIES = DemoResponsibleParties(
    study_lead="Ing. Demo Vial",
    traffic_operator="Operador Demo",
    reviewer="Auditor Vial",
    pavement_designer="Especialista Demo en Pavimentos",
    report_prepared_by="Equipo Pavement Intelligence",
    report_reviewed_by="Auditor Vial",
    report_approved_by="Aprobador Demo",
)

DEMO_REPORT_METADATA: dict[str, Any] = {
    "report_title": "Informe demostrativo del Corredor Andino",
    "study_code": DEMO_PROJECT_METADATA.project_code,
    "entity": DEMO_PROJECT_METADATA.requesting_entity,
    "location": DEMO_PROJECT_METADATA.location,
    "study_lead": DEMO_RESPONSIBLE_PARTIES.study_lead,
    "prepared_by": DEMO_RESPONSIBLE_PARTIES.report_prepared_by,
    "reviewed_by": DEMO_RESPONSIBLE_PARTIES.report_reviewed_by,
    "approved_by": DEMO_RESPONSIBLE_PARTIES.report_approved_by,
    "date": DEMO_STUDY_DATE.isoformat(),
    "version": "DEMO-1.0",
    "observations": DEMO_PROJECT_METADATA.observations,
    "disclaimer": (
        "DATOS SINTÉTICOS — SOLO DEMOSTRACIÓN. No constituye estudio oficial, "
        "diseño constructivo, firma profesional ni aprobación normativa."
    ),
    "data_origin": "synthetic_demo",
    "is_demo": True,
}


def demo_widget_defaults() -> dict[str, Any]:
    """Valores iniciales de widgets; se copian una sola vez al cargar el caso."""
    return {
        "traffic_review_manual_reason": (
            "Corrección demostrativa por clasificación visual supervisada."
        ),
        "traffic_review_manual_reviewer": DEMO_RESPONSIBLE_PARTIES.traffic_operator,
        "traffic_review_synthetic_ack": True,
        "traffic_review_totals_ack": True,
        "traffic_review_transfer_ack": True,
        "plate_session_reviewer": DEMO_RESPONSIBLE_PARTIES.reviewer,
        "ocr_reviewer": DEMO_RESPONSIBLE_PARTIES.reviewer,
        "weighing_source_label": "Biblioteca demostrativa",
        "weighing_source_date": DEMO_STUDY_DATE,
        "weighing_reviewer": DEMO_RESPONSIBLE_PARTIES.reviewer,
        "weighing_demo_library_ack": True,
        "weighing_tolerance": 5.0,
        "weighing_outlier_treatment": "MARCAR_SIN_EXCLUIR",
        "weighing_synthetic_ack": True,
        "weighing_esal_demo_mode": True,
        "weighing_esal_transfer_confirmed": True,
        "esal_reviewer": DEMO_RESPONSIBLE_PARTIES.reviewer,
        "esal_synthetic_ack": True,
        "esal_estimated_ack": True,
        "esal_assumptions": (
            "Factores camión derivados únicamente de observaciones sintéticas "
            "incluidas; ley de cuarta potencia como aproximación académica."
        ),
        "esal3b_allow_demo": True,
        "esal3b_register_interval": True,
        "esal3b_start_date": DEMO_STUDY_DATE,
        "esal3b_start_time": time(14, 0),
        "esal3b_end_date": DEMO_STUDY_DATE,
        "esal3b_end_time": time(16, 0),
        "esal3b_hours": 2.0,
        "esal3b_source_reference": "Ventana sintética declarada y verificada 14:00–16:00",
        "esal3b_responsible": DEMO_RESPONSIBLE_PARTIES.study_lead,
        "esal3b_justification": "Expansión visible 24/2 = 12 para el caso demostrativo.",
        "esal3b_fdd": 0.52,
        "esal3b_fdc": 1.0,
        "esal3b_days": 365,
        "esal3b_base_year": 2026,
        "esal3b_years": 20,
        "esal3b_reviewer": DEMO_RESPONSIBLE_PARTIES.reviewer,
        "esal3b_synthetic_ack": True,
        "geotech_study_id": "DEMO-GEO-01",
        "geotech_segment": DEMO_PROJECT_METADATA.segment,
        "geotech_location": "Progresiva ficticia 1+250",
        "geotech_depth": 1.5,
        "geotech_sample_type": "Muestra alterada sintética",
        "geotech_sample_condition": "Saturada para demostración",
        "geotech_cbr_reported": 7.0,
        "geotech_cbr_25": 7.0,
        "geotech_cbr_50": 6.8,
        "geotech_selection": "Valor sintético reportado a 2,5 mm",
        "geotech_compaction": 95.0,
        "geotech_density": 18.4,
        "geotech_moisture": "Saturada",
        "geotech_saturated": True,
        "geotech_energy": "Proctor modificado declarado; sin ensayo real",
        "geotech_test_date": DEMO_STUDY_DATE,
        "geotech_source": "Laboratorio ficticio DEMO-LAB; no verificable",
        "geotech_responsible": DEMO_RESPONSIBLE_PARTIES.study_lead,
        "geotech_standard": "ASTM D1883 / AASHTO T 193 declarado solo como contexto",
        "geotech_observations": DEMO_PROJECT_METADATA.observations,
        "geotech_phase4a_reviewer": DEMO_RESPONSIBLE_PARTIES.reviewer,
        "geotech_synthetic_ack": True,
        "geotech_4b_responsible": DEMO_RESPONSIBLE_PARTIES.reviewer,
        "geotech_4b_justification": (
            "Adoptar de forma visible la correlación aplicable al CBR sintético."
        ),
        "geotech_4b_demo_ack": True,
        "aashto5a_design_id": "DEMO-AASHTO93-01",
        "aashto5a_segment": DEMO_PROJECT_METADATA.segment,
        "aashto5a_s0_source": "Parámetro demostrativo visible; requiere validación profesional",
        "aashto5a_s0_condition": "DEMOSTRATIVO",
        "aashto5a_responsible": DEMO_RESPONSIBLE_PARTIES.pavement_designer,
        "aashto5a_justification": (
            "Evaluar el corredor ficticio con el motor AASHTO 93 flexible existente."
        ),
        "aashto5a_acknowledged": True,
        "5b_responsible": DEMO_RESPONSIBLE_PARTIES.pavement_designer,
        "5b_justification": "Búsqueda discreta visible con rangos e incrementos declarados.",
        "5b_mode": "BUSQUEDA_DISCRETA",
        "pavement_responsible": DEMO_RESPONSIBLE_PARTIES.pavement_designer,
        "pavement_reviewer": DEMO_RESPONSIBLE_PARTIES.reviewer,
        "pavement_criteria": (
            "Pavimento flexible; AASHTO 93; parámetros y limitaciones visibles del caso demo."
        ),
        "report_project_name": DEMO_PROJECT_METADATA.project_name,
        "report_title": DEMO_REPORT_METADATA["report_title"],
        "report_study_code": DEMO_REPORT_METADATA["study_code"],
        "report_prepared_by": DEMO_REPORT_METADATA["prepared_by"],
        "report_reviewed_by": DEMO_REPORT_METADATA["reviewed_by"],
        "report_approved_by": DEMO_REPORT_METADATA["approved_by"],
        "report_date": DEMO_STUDY_DATE,
        "report_version": DEMO_REPORT_METADATA["version"],
        "report_disclaimer": DEMO_REPORT_METADATA["disclaimer"],
        "report_segment": DEMO_PROJECT_METADATA.segment,
        "report_location": DEMO_PROJECT_METADATA.location,
        "report_organization": DEMO_PROJECT_METADATA.requesting_entity,
        "report_responsible": DEMO_RESPONSIBLE_PARTIES.study_lead,
        "report_reviewer": DEMO_RESPONSIBLE_PARTIES.reviewer,
        "report_observations": (
            f"{DEMO_PROJECT_METADATA.observations} {DEMO_REPORT_METADATA['disclaimer']}"
        ),
        "report_mode": "REPORTE_COMPLETO",
        "report_partial_ack": True,
        "report_include_history": False,
    }


DEMO_REQUIRED_FIELDS = (
    DemoRequiredField("Revisión del aforo", "Aceptación sintética", "traffic_review_synthetic_ack", "bool", "Obligatoria para aprobar lote sintético", True),
    DemoRequiredField("Revisión del aforo", "Aprobación de totales", "traffic_review_totals_ack", "bool", "Habilita aprobación final", True),
    DemoRequiredField("OCR", "Revisor", "ocr_reviewer", "str", "Requerido para guardar revisión", DEMO_RESPONSIBLE_PARTIES.reviewer),
    DemoRequiredField("TPDA", "Duración declarada", "demo_tpda_duration_hours", "float", "Mayor que cero y cobertura confirmada", 2.0),
    DemoRequiredField("TPDA", "Responsable", "demo_tpda_reviewer", "str", "Obligatorio para calcular", DEMO_RESPONSIBLE_PARTIES.reviewer),
    DemoRequiredField("Pesaje", "Fuente", "weighing_source_label", "str", "Fuente de cargas declarada", "Biblioteca demostrativa"),
    DemoRequiredField("Pesaje", "Revisor", "weighing_reviewer", "str", "Obligatorio para validar muestra", DEMO_RESPONSIBLE_PARTIES.reviewer),
    DemoRequiredField("ESAL", "Revisor", "esal_reviewer", "str", "Obligatorio para calcular", DEMO_RESPONSIBLE_PARTIES.reviewer),
    DemoRequiredField("Geotecnia 4A", "Fuente", "geotech_source", "str", "Trazabilidad del CBR", "Laboratorio ficticio DEMO-LAB; no verificable"),
    DemoRequiredField("Geotecnia 4A", "Responsable", "geotech_responsible", "str", "Trazabilidad del ensayo", DEMO_RESPONSIBLE_PARTIES.study_lead),
    DemoRequiredField("Geotecnia 4B", "Justificación", "geotech_4b_justification", "str", "Obligatoria para adopción", "Adopción explícita de correlación sintética"),
    DemoRequiredField("AASHTO 5A", "Fuente S0", "aashto5a_s0_source", "str", "Obligatoria para calcular SN", "Parámetro demostrativo visible"),
    DemoRequiredField("AASHTO 5A", "Responsable", "aashto5a_responsible", "str", "Obligatorio para calcular SN", DEMO_RESPONSIBLE_PARTIES.pavement_designer),
    DemoRequiredField("Capas 5B", "Justificación", "5b_justification", "str", "Obligatoria para evaluar propuesta", "Búsqueda discreta visible"),
    DemoRequiredField("Reportes", "Proyecto", "report_project_name", "str", "Dato administrativo obligatorio", DEMO_PROJECT_METADATA.project_name),
    DemoRequiredField("Reportes", "Entidad", "report_organization", "str", "Dato administrativo obligatorio", DEMO_PROJECT_METADATA.requesting_entity),
)
