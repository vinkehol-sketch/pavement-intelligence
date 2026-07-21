"""Sección Streamlit para revisión y adopción controlada de MR — Fase 4B."""
from __future__ import annotations

from datetime import date
import json

import pandas as pd
import streamlit as st

from pavement_intelligence.geotechnics.cbr_workflow import GeotechnicalResult
from pavement_intelligence.geotechnics.resilient_modulus_review import (
    AdoptionMode, DirectTestEvidence, ReviewInput, ResilientModulusReviewResult,
    SensitivityBands, analyze_discontinuity, build_future_transfer,
    calculate_review, compare_correlations, review_is_stale, store_review_result,
)


def render_review_section(source_result: GeotechnicalResult, *, source_current: bool) -> None:
    st.divider()
    st.header("Revisión y adopción del módulo resiliente — Fase 4B")
    st.warning("La comparación es metodológica y demostrativa. Ningún valor se transfiere automáticamente a Diseño.")
    st.session_state.setdefault("geotechnical_phase4b_input", None)
    st.session_state.setdefault("geotechnical_phase4b_result", None)
    st.session_state.setdefault("geotechnical_phase4b_history", [])
    st.session_state.setdefault("geotechnical_future_transfer", None)
    if not source_current:
        st.error("Fuente 4A DESACTUALIZADA: recalcule CBR antes de aprobar o transferir 4B.")

    st.metric("CBR de diseño recibido", f"{source_result.design_cbr_percent:.3f} %")
    low = st.number_input("Límite superior de sensibilidad baja (%)", min_value=0.0, value=10.0)
    moderate = st.number_input("Límite superior de sensibilidad moderada (%)", min_value=0.01, value=30.0)
    bands = SensitivityBands(low, moderate)
    try:
        comparison = compare_correlations(source_result.design_cbr_percent, bands)
    except ValueError as exc:
        st.error(f"Comparación bloqueada: {exc}")
        return
    st.subheader("Correlaciones aplicables")
    if comparison.alternatives:
        st.dataframe(pd.DataFrame([{
            "Correlación": item.correlation_id, "Fórmula": item.equation,
            "Rango CBR (%)": f"{item.interval_percent[0]}–{item.interval_percent[1]}",
            "MR (MPa)": item.resilient_modulus_mpa, "Referencia": item.reference,
            "Carácter": item.status, "Advertencias": " | ".join(item.warnings),
        } for item in comparison.alternatives]), hide_index=True, width="stretch")
        st.write(f"Diferencia absoluta: **{comparison.absolute_difference_mpa:,.3f} MPa**")
        st.write(f"Diferencia relativa: **{comparison.relative_difference_percent:,.3f} %**")
    else:
        st.error("No existe correlación aplicable para el CBR recibido.")
    st.write(f"Nivel textual de sensibilidad: **{comparison.sensitivity_level}**")
    for warning in comparison.warnings:
        st.warning(warning)

    if 7.2 <= source_result.design_cbr_percent <= 10:
        st.warning("Zona de solapamiento 7,2–10: las correlaciones lineales producen resultados distintos.")
    discontinuity = analyze_discontinuity()
    with st.expander("Discontinuidad metodológica alrededor de CBR 20"):
        st.dataframe(pd.DataFrame([
            {"Posición": "19,99", "Alternativas": dict(discontinuity.immediately_before.alternatives)},
            {"Posición": "20,00", "Alternativas": dict(discontinuity.at_boundary.alternatives)},
            {"Posición": "20,01", "Alternativas": dict(discontinuity.immediately_after.alternatives)},
        ]), hide_index=True, width="stretch")
        st.warning(discontinuity.warning)
        st.write(f"Salto relativo entre lados: **{discontinuity.cross_boundary_difference_percent:,.3f} %**")

    st.subheader("Adopción humana controlada")
    mode = st.selectbox(
        "Modo de adopción", list(AdoptionMode),
        format_func=lambda item: item.value, key="geotech_4b_mode",
    )
    applicable_ids = [item.correlation_id for item in comparison.alternatives]
    selected = st.selectbox(
        "Correlación seleccionada", [""] + applicable_ids,
        disabled=mode != AdoptionMode.CORRELATION_SELECTION,
        key="geotech_4b_selected",
    )
    conservative_ack = st.checkbox(
        "Acepto que conservador significa menor MR aplicable y no es una regla normativa",
        disabled=mode != AdoptionMode.CONSERVATIVE_VALUE,
    )
    manual_value = st.number_input("MR manual", min_value=0.001, value=50.0,
                                   disabled=mode != AdoptionMode.JUSTIFIED_MANUAL)
    manual_unit = st.selectbox("Unidad del MR manual", ["MPa", "kPa", "psi", "ksi"],
                               disabled=mode != AdoptionMode.JUSTIFIED_MANUAL)
    manual_source = st.text_input("Fuente del valor manual", disabled=mode != AdoptionMode.JUSTIFIED_MANUAL)
    direct_value = st.number_input("MR de ensayo directo", min_value=0.001, value=50.0,
                                   disabled=mode != AdoptionMode.DIRECT_TEST)
    direct_unit = st.selectbox("Unidad del ensayo directo", ["MPa", "kPa", "psi", "ksi"],
                               disabled=mode != AdoptionMode.DIRECT_TEST)
    direct_lab = st.text_input("Laboratorio del ensayo directo", disabled=mode != AdoptionMode.DIRECT_TEST)
    direct_procedure = st.text_input("Procedimiento del ensayo directo", disabled=mode != AdoptionMode.DIRECT_TEST)
    direct_date = st.date_input("Fecha del ensayo directo", value=date.today(),
                                disabled=mode != AdoptionMode.DIRECT_TEST)
    direct_document = st.text_input("Documento del ensayo directo", disabled=mode != AdoptionMode.DIRECT_TEST)
    responsible = st.text_input(
        "Responsable de la adopción", key="geotech_4b_responsible"
    )
    justification = st.text_area(
        "Justificación de la adopción", key="geotech_4b_justification"
    )
    demo_ack = st.checkbox(
        "Reconozco el carácter demostrativo de la fuente Fase 4A",
        key="geotech_4b_demo_ack",
    )
    direct = None
    if mode == AdoptionMode.DIRECT_TEST:
        direct = DirectTestEvidence(
            direct_value, direct_unit, direct_lab, direct_procedure, direct_date.isoformat(),
            responsible, direct_document,
        )
    data = ReviewInput(
        source_result=source_result, sensitivity_bands=bands, adoption_mode=mode.value,
        selected_correlation_id=selected or None, conservative_rule_accepted=conservative_ack,
        manual_value=manual_value if mode == AdoptionMode.JUSTIFIED_MANUAL else None,
        manual_unit=manual_unit, manual_source=manual_source, direct_test=direct,
        responsible=responsible, justification=justification,
        source_demonstrative_acknowledged=demo_ack,
    )
    previous = st.session_state.get("geotechnical_phase4b_result")
    if isinstance(previous, ResilientModulusReviewResult) and review_is_stale(previous, data):
        st.error("DESACTUALIZADO: cambió la fuente 4A, bandas, modo, evidencia o decisión de adopción.")
        st.session_state["geotechnical_future_transfer"] = None
    if st.button("Aprobar adopción de MR", type="primary", disabled=not source_current,
                 icon=":material/verified:"):
        try:
            result = calculate_review(data)
            store_review_result(st.session_state, data, result)
            st.rerun()
        except ValueError as exc:
            st.error(f"Adopción bloqueada: {exc}")
    result = st.session_state.get("geotechnical_phase4b_result")
    if not isinstance(result, ResilientModulusReviewResult):
        st.info("Estado: PENDIENTE DE ADOPCIÓN EXPLÍCITA.")
        return
    stale = review_is_stale(result, data) or not source_current
    st.subheader("Resultado aprobado")
    st.metric("MR adoptado", f"{result.adopted_resilient_modulus_mpa:,.3f} MPa")
    st.write(f"Estado: **{'DESACTUALIZADO' if stale else 'APROBADO'}**")
    st.write(f"Fuente: `{result.source}` | Confianza: `{result.confidence_level}`")
    st.download_button("Descargar revisión 4B JSON", json.dumps(result.as_dict(), ensure_ascii=False, indent=2),
                       file_name=f"{result.review_id}.json", mime="application/json",
                       icon=":material/download:")
    if st.button("Crear contrato manual para futura Fase AASHTO", disabled=stale,
                 icon=":material/output:"):
        try:
            st.session_state["geotechnical_future_transfer"] = build_future_transfer(result, data)
            st.success("Contrato futuro creado; no se escribió en Diseño ni se calculó SN.")
        except ValueError as exc:
            st.error(f"Transferencia bloqueada: {exc}")
