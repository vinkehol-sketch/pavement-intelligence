"""Sección Streamlit separada para la proyección temporal ESAL Fase 3B."""
from __future__ import annotations

import json
from datetime import datetime
import pandas as pd
import streamlit as st

from pavement_intelligence.esal.projection_workflow import (
    PROJECTION_METHOD_LABEL, PROJECTION_WARNING, CategoryGrowthRate,
    ESALProjectionTransfer, ProjectionWorkflowInput, ProjectionWorkflowResult,
    TemporalFactorSource, build_projection_transfer, build_temporal_base,
    calculate_projection_workflow, projection_result_is_stale,
    projection_transfer_is_current, store_projection_transfer,
)
from pavement_intelligence.esal.workflow import ESALWorkflowResult


def render_projection_section(current_esal: ESALWorkflowResult) -> None:
    st.divider()
    st.header("Fase 3B — Proyección temporal de ESAL")
    st.warning(f"{PROJECTION_METHOD_LABEL}. {PROJECTION_WARNING}")
    st.caption("3B no se ejecuta automáticamente ni transfiere un ESAL a Diseño.")

    existing = st.session_state.get("esal_projection_transfer")
    decision = "replace" if isinstance(existing, ESALProjectionTransfer) else "new"
    allow_demo = st.checkbox("Habilitar transferencia demostrativa sintética", key="esal3b_allow_demo")
    if st.button("Transferir explícitamente resultado 3A vigente a 3B", use_container_width=True):
        try:
            transfer = build_projection_transfer(current_esal, allow_demonstration=allow_demo)
            store_projection_transfer(st.session_state, transfer, decision=decision)
            st.rerun()
        except ValueError as exc:
            st.error(f"Transferencia bloqueada: {exc}")

    transfer = st.session_state.get("esal_projection_transfer")
    if not isinstance(transfer, ESALProjectionTransfer):
        st.info("Realice la transferencia manual para habilitar los parámetros temporales.")
        return
    current = projection_transfer_is_current(transfer, current_esal)
    st.json({"transferencia": transfer.transfer_id, "resultado_3A": transfer.source_esal_result_id,
             "huella_3A": transfer.source_esal_fingerprint, "ESAL_lote_observado": transfer.observed_batch_esal,
             "vehiculos_validos": transfer.valid_vehicle_count, "categorias": transfer.categories,
             "vigente": current}, expanded=False)
    if not current:
        st.error("DESACTUALIZADO: la huella o el identificador del resultado 3A cambió. Transfiera nuevamente.")

    st.subheader("Base temporal y distribución")
    source = st.selectbox("Origen del factor diario", options=list(TemporalFactorSource),
                          format_func=lambda x: x.value)
    unknown = source == TemporalFactorSource.DEMONSTRATION
    register_interval = st.checkbox("Registrar fecha y hora de inicio/fin", disabled=unknown)
    start_at = end_at = None
    if register_interval:
        start_date = st.date_input("Fecha de inicio", key="esal3b_start_date")
        start_time = st.time_input("Hora de inicio", key="esal3b_start_time")
        end_date = st.date_input("Fecha de fin", key="esal3b_end_date")
        end_time = st.time_input("Hora de fin", key="esal3b_end_time")
        start_at = datetime.combine(start_date, start_time).isoformat()
        end_at = datetime.combine(end_date, end_time).isoformat()
    hours = None if unknown else st.number_input("Horas observadas", min_value=0.01, value=24.0)
    manual_factor = None
    if source in {TemporalFactorSource.MANUAL, TemporalFactorSource.TPDA}:
        manual_factor = st.number_input("Factor de expansión diario", min_value=0.000001, value=1.0)
    source_reference = st.text_input("Fuente del factor temporal", value="Registro temporal revisado")
    responsible = st.text_input("Responsable temporal")
    justification = st.text_input("Justificación temporal", value="Cobertura declarada por el operador")
    fdd = st.number_input("FDD", min_value=0.000001, max_value=1.0, value=0.5)
    fdc = st.number_input("FDC", min_value=0.000001, max_value=1.0, value=1.0)
    days = st.number_input("Días de operación por año", min_value=1, max_value=366, value=365, step=1)
    base_year = st.number_input("Año base (n=0)", min_value=1900, max_value=2500,
                                value=transfer.source_reference_year or 2026, step=1)
    years = st.number_input("Número de años de la serie", min_value=1, max_value=100, value=5, step=1)

    st.subheader("Crecimiento explícito por categoría")
    rates = []
    for category in transfer.categories:
        c1, c2, c3 = st.columns(3)
        rate = c1.number_input(f"Tasa anual % — {category}", value=0.0, key=f"esal3b_rate_{category}")
        rate_source = c2.text_input(f"Fuente — {category}", value="Definida por usuario", key=f"esal3b_src_{category}")
        condition = c3.text_input(f"Condición — {category}", value="REVISADA", key=f"esal3b_cond_{category}")
        rates.append(CategoryGrowthRate(category, rate, rate_source, condition))
    reviewer = st.text_input("Revisor Fase 3B")
    synthetic_ack = st.checkbox("Reconozco el uso exclusivamente demostrativo de datos sintéticos",
                                disabled=not transfer.is_synthetic)

    try:
        temporal = build_temporal_base(
            start_at=start_at, end_at=end_at, observed_hours=hours,
            observed_days=(hours / 24 if hours else None), factor_source=source,
            source_reference=source_reference, responsible=responsible,
            justification=justification, manual_factor=manual_factor,
        )
        data = ProjectionWorkflowInput(
            transfer=transfer, temporal_base=temporal, base_year=int(base_year),
            projection_years=int(years), directional_distribution_factor=fdd,
            lane_distribution_factor=fdc, operating_days_per_year=int(days),
            growth_rates=tuple(rates), reviewer=reviewer,
            synthetic_acknowledged=synthetic_ack,
        )
    except ValueError as exc:
        st.error(f"Base temporal incompleta: {exc}")
        return

    previous = st.session_state.get("esal_projection_result")
    if isinstance(previous, ProjectionWorkflowResult) and projection_result_is_stale(previous, data, current_esal):
        st.error("DESACTUALIZADO: cambiaron la fuente 3A o los parámetros 3B; se conserva el resultado anterior.")
    if st.button("Calcular proyección temporal ESAL", type="primary", disabled=not current,
                 use_container_width=True):
        try:
            result = calculate_projection_workflow(data)
            if isinstance(previous, ProjectionWorkflowResult):
                st.session_state.setdefault("esal_projection_history", []).append(previous)
            st.session_state["esal_projection_input"] = data
            st.session_state["esal_projection_result"] = result
            st.rerun()
        except (TypeError, ValueError, ArithmeticError, OverflowError) as exc:
            st.error(f"Proyección bloqueada: {exc}")

    result = st.session_state.get("esal_projection_result")
    if not isinstance(result, ProjectionWorkflowResult):
        return
    st.subheader("Magnitudes temporales")
    st.dataframe(pd.DataFrame([{
        "ESAL lote observado": result.observed_batch_esal,
        "ESAL medio/vehículo": result.average_esal_per_vehicle,
        "ESAL diario base": result.base_daily_esal,
        "ESAL diario distribuido": result.distributed_daily_esal,
        "ESAL anual base": result.base_annual_esal,
        "ESAL acumulado": result.accumulated_esal,
    }]), hide_index=True, use_container_width=True)
    st.dataframe(pd.DataFrame([vars(x) for x in result.categories]), hide_index=True, use_container_width=True)
    annual = pd.DataFrame([vars(x) for x in result.annual_series])
    st.dataframe(annual, hide_index=True, use_container_width=True)
    if not annual.empty:
        st.line_chart(annual.set_index("calendar_year")[["annual_projected_esal", "accumulated_esal"]])
    st.dataframe(pd.DataFrame([vars(x) for x in result.source_breakdown]), hide_index=True,
                 use_container_width=True)
    with st.expander("Trazabilidad completa 3B"):
        st.json(result.as_dict())
    st.download_button("Descargar resultado 3B", json.dumps(result.as_dict(), ensure_ascii=False, indent=2),
                       file_name=f"{result.result_id}.json", mime="application/json")
