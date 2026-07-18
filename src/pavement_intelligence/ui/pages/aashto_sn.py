"""Sección independiente Fase 5A: número estructural requerido."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import streamlit as st

from pavement_intelligence.aashto93.sn_workflow import (
    AASHTO93Input,
    AASHTO93Result,
    MANDATORY_WARNING,
    SolverSettings,
    ZR_CATALOG,
    ZR_CATALOG_SOURCE,
    ZR_CATALOG_VERSION,
    build_esal_5a_transfer,
    build_mr_5a_transfer,
    calculate_required_sn,
    convert_mr_to_psi,
    result_is_stale,
    store_result,
    zr_from_catalog,
)
from pavement_intelligence.esal.projection_workflow import (
    ProjectionWorkflowInput,
    ProjectionWorkflowResult,
)
from pavement_intelligence.geotechnics.resilient_modulus_review import (
    FutureAASHTOTransfer,
    ReviewInput,
    ResilientModulusReviewResult,
    review_is_stale,
)

st.title("AASHTO 93 — SN requerido · Fase 5A")
st.warning(MANDATORY_WARNING)
st.caption("Flujo independiente: no calcula capas, espesores, materiales ni costos.")
for key, value in (
    ("aashto5a_esal_transfer", None),
    ("aashto5a_mr_transfer", None),
    ("aashto93_phase5a_history", []),
):
    st.session_state.setdefault(key, value)
st.session_state.setdefault(
    "aashto5a_contract_date", datetime.now(timezone.utc).isoformat()
)

st.subheader("1. Transferencias manuales")
with st.container(border=True):
    r3 = st.session_state.get("esal_projection_result")
    i3 = st.session_state.get("esal_projection_input")
    if st.button("Importar ESAL aprobado desde Fase 3B", icon=":material/download:"):
        try:
            if not isinstance(r3, ProjectionWorkflowResult) or not isinstance(
                i3, ProjectionWorkflowInput
            ):
                raise ValueError("No existe resultado e input 3B completos.")
            st.session_state["aashto5a_esal_transfer"] = build_esal_5a_transfer(r3, i3)
            st.rerun()
        except ValueError as exc:
            st.error(f"Transferencia ESAL bloqueada: {exc}")
    esal = st.session_state["aashto5a_esal_transfer"]
    st.write("Estado ESAL:", "IMPORTADO" if esal else "AUSENTE")
    if esal:
        st.json(esal.as_dict(), expanded=False)
with st.container(border=True):
    future = st.session_state.get("geotechnical_future_transfer")
    review = st.session_state.get("geotechnical_phase4b_result")
    review_input = st.session_state.get("geotechnical_phase4b_input")
    if st.button("Importar MR aprobado desde Fase 4B", icon=":material/download:"):
        try:
            if not isinstance(future, FutureAASHTOTransfer) or not isinstance(
                review, ResilientModulusReviewResult
            ):
                raise ValueError("Primero cree el contrato manual futuro en Fase 4B.")
            if (
                future.review_fingerprint != review.input_fingerprint
                or review.is_stale
                or not review.approved
            ):
                raise ValueError(
                    "El contrato MR no coincide con la revisión 4B vigente."
                )
            st.session_state["aashto5a_mr_transfer"] = build_mr_5a_transfer(
                future,
                study_id=review.study_id,
                adoption_mode=review.adoption_mode,
                evidence=review.evidence_available,
            )
            st.rerun()
        except ValueError as exc:
            st.error(f"Transferencia MR bloqueada: {exc}")
    mr = st.session_state["aashto5a_mr_transfer"]
    st.write("Estado MR:", "IMPORTADO" if mr else "AUSENTE")
    if mr:
        st.json(mr.as_dict(), expanded=False)

if not esal or not mr:
    st.error("Cálculo bloqueado: se requieren ambas transferencias manuales vigentes.")
    st.stop()

esal_current = (
    isinstance(r3, ProjectionWorkflowResult)
    and isinstance(i3, ProjectionWorkflowInput)
    and not r3.is_stale
    and r3.input_fingerprint == esal.phase3b_fingerprint
)
mr_current = (
    isinstance(future, FutureAASHTOTransfer)
    and isinstance(review, ResilientModulusReviewResult)
    and isinstance(review_input, ReviewInput)
    and not review.is_stale
    and not review_is_stale(review, review_input)
    and review.approved
    and review.input_fingerprint == mr.phase4b_fingerprint == future.review_fingerprint
)
if not esal_current or not mr_current:
    st.error(
        "Cálculo bloqueado: una transferencia cambió o quedó desactualizada en su fase de origen."
    )
    st.stop()

st.subheader("2. Parámetros explícitos")
st.metric("W18 importado", f"{esal.accumulated_esal:,.2f}")
st.metric("MR importado", f"{mr.adopted_mr:,.4f} {mr.unit}")
st.caption(
    f"Conversión controlada para la ecuación: {convert_mr_to_psi(mr.adopted_mr, mr.unit):,.2f} psi"
)
with st.form("aashto5a_form", border=True):
    design_id = st.text_input("Identificador del diseño")
    segment = st.text_input("Tramo")
    reliability = st.selectbox("Confiabilidad R (%)", list(ZR_CATALOG))
    zr_mode = st.segmented_control(
        "Fuente ZR", ["CATALOGO", "MANUAL_JUSTIFICADO"], default="CATALOGO"
    )
    catalog_zr = zr_from_catalog(float(reliability))
    zr = st.number_input(
        "ZR", value=float(catalog_zr), disabled=zr_mode == "CATALOGO", format="%.4f"
    )
    st.caption(f"Catálogo {ZR_CATALOG_VERSION}: {ZR_CATALOG_SOURCE}")
    s0 = st.number_input(
        "S0 explícito (rango admitido 0,30–0,60)", value=0.45, format="%.3f"
    )
    s0_source = st.text_input("Fuente de S0")
    s0_condition = st.selectbox("Condición de S0", ["MANUAL", "DEMOSTRATIVO"])
    p0 = st.number_input("Serviciabilidad inicial p0", value=4.2, format="%.2f")
    pt = st.number_input("Serviciabilidad terminal pt", value=2.5, format="%.2f")
    st.write(f"ΔPSI explícito calculado: **{p0 - pt:.3f}**")
    responsible = st.text_input("Responsable")
    justification = st.text_area(
        "Justificación (incluya justificación de ZR si es manual)"
    )
    acknowledged = st.checkbox(
        "Reconozco la condición demostrativa/sintética de los datos"
    )
    sn_min = st.number_input("SN mínimo", value=0.01, format="%.4f")
    sn_max = st.number_input("SN máximo", value=15.0, format="%.2f")
    tolerance = st.number_input("Tolerancia de residuo", value=0.0001, format="%.6f")
    max_iterations = st.number_input("Iteraciones máximas", value=100, step=1)
    boundary_margin_fraction = st.number_input(
        "Margen relativo para advertir proximidad a límites",
        min_value=0.0,
        max_value=0.25,
        value=0.02,
        format="%.3f",
        help="Fracción del ancho del intervalo; 0,02 equivale al 2 %.",
    )
    submitted = st.form_submit_button(
        "Calcular SN requerido", type="primary", icon=":material/calculate:"
    )

data = AASHTO93Input(
    design_id,
    segment,
    esal,
    mr,
    esal.accumulated_esal,
    mr.adopted_mr,
    mr.unit,
    float(reliability),
    catalog_zr if zr_mode == "CATALOGO" else float(zr),
    zr_mode or "CATALOGO",
    ZR_CATALOG_VERSION,
    float(s0),
    s0_source,
    s0_condition,
    float(p0),
    float(pt),
    float(p0 - pt),
    f"{esal.start_year}–{esal.end_year}",
    (
        ("W18", "TRANSFERENCIA_FASE_3B"),
        ("MR", "TRANSFERENCIA_FASE_4B"),
        ("R_ZR", zr_mode or "CATALOGO"),
        ("S0", s0_source),
        ("SERVICIABILIDAD", "INGRESO_EXPLICITO"),
    ),
    responsible,
    justification,
    esal.warnings + mr.warnings,
    SolverSettings(
        float(sn_min),
        float(sn_max),
        float(tolerance),
        int(max_iterations),
        float(boundary_margin_fraction),
    ),
    acknowledged,
    created_at=st.session_state["aashto5a_contract_date"],
)
previous = st.session_state.get("aashto93_phase5a_result")
if isinstance(previous, AASHTO93Result) and result_is_stale(previous, data):
    st.error(
        "DESACTUALIZADO: cambiaron entradas o metodología; el resultado anterior permanece en histórico."
    )
if submitted:
    try:
        result = calculate_required_sn(data)
        store_result(st.session_state, data, result)
        st.rerun()
    except (TypeError, ValueError, ArithmeticError, OverflowError) as exc:
        st.error(f"Cálculo bloqueado: {exc}")

result = st.session_state.get("aashto93_phase5a_result")
if isinstance(result, AASHTO93Result):
    st.subheader("3. Resultado")
    if result_is_stale(result, data):
        st.error("Resultado desactualizado; recalcule antes de usarlo.")
    else:
        st.metric("SN requerido", f"{result.required_sn:.4f}")
        st.write(
            f"Convergencia: **SÍ** · residuo: `{result.residual:.3e}` · iteraciones: `{result.iterations}`"
        )
    st.code(result.equation)
    for warning in result.warnings:
        if warning.startswith("SN_CERCANO_LIMITE_"):
            st.warning(warning)
    st.json(result.as_dict(), expanded=False)
    st.download_button(
        "Descargar resultado JSON",
        json.dumps(result.as_dict(), ensure_ascii=False, indent=2),
        file_name=f"{result.result_id}.json",
        mime="application/json",
        icon=":material/download:",
    )
