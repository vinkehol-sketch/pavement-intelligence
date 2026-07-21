"""Fase 6A: integración final y reportes demostrativos del MVP."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pavement_intelligence.reporting.workflow import (
    MANDATORY_WARNING,
    PHASES,
    AdministrativeData,
    IntegratedDossier,
    ReportMode,
    ReportRequest,
    build_dossier,
    collect_phase_records,
    dossier_is_stale,
    dossier_json_bytes,
    dossier_pdf_bytes,
    store_dossier,
)
from pavement_intelligence.ui.utils.widget_state import widget_default

st.title("Expediente integrado y reportes · Fase 6A")
st.warning(MANDATORY_WARNING)
st.caption(
    "No exporta el estado completo de Streamlit, rutas locales, costos, firmas ni aprobación normativa."
)
st.session_state.setdefault("integrated_dossier_history", [])
demo_request = st.session_state.get("integrated_report_request")
demo_request = (
    demo_request
    if st.session_state.get("demo_mode_active")
    and isinstance(demo_request, ReportRequest)
    else None
)
defaults = demo_request.administrative if demo_request else AdministrativeData(
    "", "", "", "", "", "", ""
)

st.subheader("Datos administrativos")
project_name = st.text_input(
    "Nombre del proyecto",
    **widget_default(st.session_state, "report_project_name", defaults.project_name),
)
segment = st.text_input(
    "Tramo", **widget_default(st.session_state, "report_segment", defaults.segment)
)
location = st.text_input(
    "Ubicación", **widget_default(st.session_state, "report_location", defaults.location)
)
organization = st.text_input(
    "Entidad u organización",
    **widget_default(st.session_state, "report_organization", defaults.organization),
)
responsible = st.text_input(
    "Responsable",
    **widget_default(st.session_state, "report_responsible", defaults.responsible),
)
reviewer = st.text_input(
    "Revisor", **widget_default(st.session_state, "report_reviewer", defaults.reviewer)
)
observations = st.text_area(
    "Observaciones administrativas",
    **widget_default(st.session_state, "report_observations", defaults.observations),
)

if st.session_state.get("demo_mode_active"):
    with st.expander("Identificación del informe demostrativo", expanded=True):
        st.text_input("Título del informe", key="report_title", disabled=True)
        st.text_input("Código del estudio", key="report_study_code", disabled=True)
        st.text_input("Elaboró", key="report_prepared_by", disabled=True)
        st.text_input("Revisó", key="report_reviewed_by", disabled=True)
        st.text_input("Aprobó", key="report_approved_by", disabled=True)
        st.date_input("Fecha del informe", key="report_date", disabled=True)
        st.text_input("Versión", key="report_version", disabled=True)
        st.text_area("Descargo de responsabilidad", key="report_disclaimer", disabled=True)

records = collect_phase_records(st.session_state)
st.subheader("Estado de fases y continuidad")
st.dataframe(
    pd.DataFrame(
        [
            {
                "Fase": x.phase,
                "Estado": x.state,
                "Continuidad": x.continuity,
                "Resultado": x.identifier or "Ausente",
                "Huella": (x.result_fingerprint or "-")[:16],
                "Dependencia": x.dependency or "-",
                "Bloqueos": " | ".join(x.blockers),
            }
            for x in records
        ]
    ),
    hide_index=True,
)

mode = st.segmented_control(
    "Modo de reporte",
    [x.value for x in ReportMode],
    **widget_default(
        st.session_state,
        "report_mode",
        demo_request.mode if demo_request else ReportMode.PARTIAL.value,
        parameter="default",
    ),
)
included = st.multiselect(
    "Fases incluidas",
    list(PHASES),
    **widget_default(
        st.session_state,
        "report_included_phases",
        list(demo_request.included_phases) if demo_request else list(PHASES),
        parameter="default",
    ),
)
partial_ack = st.checkbox(
    "Acepto generar un reporte parcial que identifica explícitamente fases faltantes",
    disabled=mode != ReportMode.PARTIAL.value,
    **widget_default(
        st.session_state,
        "report_partial_ack",
        demo_request.partial_report_acknowledged if demo_request else False,
    ),
)
include_history = st.checkbox(
    "Incluir únicamente el último resultado anterior disponible por fase",
    **widget_default(
        st.session_state,
        "report_include_history",
        demo_request.include_last_history if demo_request else False,
    ),
)

request = ReportRequest(
    AdministrativeData(
        project_name,
        segment,
        location,
        organization,
        responsible,
        reviewer,
        observations,
    ),
    mode or ReportMode.PARTIAL.value,
    tuple(included),
    partial_ack,
    include_history,
)

st.subheader("Vista previa")
st.write(f"Fases seleccionadas: **{len(included)}** · Modo: **{mode}**")
missing_preview = [
    x.phase for x in records if x.phase in included and x.main_result is None
]
if missing_preview:
    st.warning("Fases faltantes: " + ", ".join(missing_preview))
blockers_preview = [
    f"{x.phase}: {b}" for x in records if x.phase in included for b in x.blockers
]
for blocker in blockers_preview:
    st.error("Bloqueo: " + blocker)

if st.button(
    "Generar expediente demostrativo", type="primary", icon=":material/description:"
):
    try:
        dossier = build_dossier(st.session_state, request)
        pdf = dossier_pdf_bytes(dossier)
        store_dossier(st.session_state, dossier, request, pdf)
        st.rerun()
    except (TypeError, ValueError, ArithmeticError, OverflowError) as exc:
        st.error(f"Generación bloqueada: {exc}")

dossier = st.session_state.get("integrated_dossier")
stored_request = st.session_state.get("integrated_report_request")
if isinstance(dossier, IntegratedDossier):
    stale = not isinstance(stored_request, ReportRequest) or dossier_is_stale(
        dossier, st.session_state, request
    )
    st.subheader("Expediente generado")
    st.write(
        f"Estado textual: **{'DESACTUALIZADO - REGENERAR' if stale else dossier.overall_state}**"
    )
    st.write(
        f"Continuidad: **{'BLOQUEADA' if dossier.blockers else 'CONFIRMADA PARA LAS FASES INCLUIDAS'}**"
    )
    st.json(
        {
            "expediente": dossier.dossier_id,
            "huella": dossier.request_fingerprint,
            "faltantes": dossier.missing_phases,
            "bloqueos": dossier.blockers,
        },
        expanded=False,
    )
    st.download_button(
        "Descargar expediente JSON",
        dossier_json_bytes(dossier),
        file_name=f"{dossier.dossier_id}.json",
        mime="application/json",
        disabled=stale,
        icon=":material/download:",
    )
    st.download_button(
        "Descargar reporte PDF",
        st.session_state.get("integrated_dossier_pdf", b""),
        file_name=f"{dossier.dossier_id}.pdf",
        mime="application/pdf",
        disabled=stale,
        icon=":material/picture_as_pdf:",
    )
