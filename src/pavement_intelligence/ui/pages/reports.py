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

st.title("Expediente integrado y reportes · Fase 6A")
st.warning(MANDATORY_WARNING)
st.caption(
    "No exporta el estado completo de Streamlit, rutas locales, costos, firmas ni aprobación normativa."
)
st.session_state.setdefault("integrated_dossier_history", [])

st.subheader("Datos administrativos")
project_name = st.text_input("Nombre del proyecto")
segment = st.text_input("Tramo")
location = st.text_input("Ubicación")
organization = st.text_input("Entidad u organización")
responsible = st.text_input("Responsable")
reviewer = st.text_input("Revisor")
observations = st.text_area("Observaciones administrativas")

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
    "Modo de reporte", [x.value for x in ReportMode], default=ReportMode.PARTIAL.value
)
included = st.multiselect("Fases incluidas", list(PHASES), default=list(PHASES))
partial_ack = st.checkbox(
    "Acepto generar un reporte parcial que identifica explícitamente fases faltantes",
    disabled=mode != ReportMode.PARTIAL.value,
)
include_history = st.checkbox(
    "Incluir únicamente el último resultado anterior disponible por fase"
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
