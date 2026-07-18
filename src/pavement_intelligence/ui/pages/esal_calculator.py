"""Interfaz del flujo formal de ESAL — Fase 3."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from pavement_intelligence.esal.workflow import (
    EQUIVALENCE_METHOD,
    EQUIVALENCE_METHOD_LABEL,
    EQUIVALENCE_METHOD_SOURCE,
    EQUIVALENCE_METHOD_WARNING,
    STANDARD_SINGLE_AXLE_KIP,
    STANDARD_SINGLE_AXLE_KN,
    ESALInputFromWeighing,
    ESALWorkflowInput,
    ESALWorkflowResult,
    calculate_esal_workflow,
    esal_result_is_stale,
    weighing_transfer_is_current,
)
from pavement_intelligence.weighing.workflow import WeighingWorkflowResult
from pavement_intelligence.ui.pages.esal_projection_section import render_projection_section


def render() -> None:
    st.title("🔢 ESAL (W18) — Fase 3")
    st.warning(
        f"{EQUIVALENCE_METHOD_WARNING} No transfiere resultados a Diseño de "
        "Pavimento, Suelos ni Reportes."
    )

    transfer = st.session_state.get("esal_input_from_weighing")
    current_weighing = st.session_state.get("weighing_phase2_result")
    if not isinstance(transfer, ESALInputFromWeighing):
        st.error(
            "No existe una transferencia manual válida desde Pesaje. "
            "Use “Usar pesaje validado en ESAL” en la Fase 2."
        )
        st.stop()
    if not isinstance(current_weighing, WeighingWorkflowResult):
        current_weighing = None

    st.subheader("1. Origen")
    st.json(
        {
            "resultado_pesaje": transfer.source_weighing_result_id,
            "huella_pesaje": transfer.source_weighing_fingerprint,
            "resultado_tpda": transfer.source_tpda_result_id,
            "huella_tpda": transfer.source_tpda_fingerprint,
            "fuente": transfer.source_reference,
            "estado": transfer.methodological_status,
            "categorias": transfer.categories,
            "observaciones": transfer.observation_count,
            "unidad": transfer.canonical_weight_unit,
            "sintetico": transfer.is_synthetic,
        },
        expanded=False,
    )
    source_current = weighing_transfer_is_current(transfer, current_weighing)
    if not source_current:
        st.error(
            "La firma del Pesaje actual no coincide con la transferencia ESAL. "
            "El resultado anterior se conserva, pero se requiere nueva transferencia."
        )
    if transfer.is_synthetic:
        st.error("Cadena sintética: el resultado solo puede ser demostrativo.")

    st.subheader("2. Método de equivalencia")
    st.markdown(
        f"""
        - **Método:** {EQUIVALENCE_METHOD_LABEL} (`{EQUIVALENCE_METHOD}`)
        - **Eje estándar:** eje simple de ruedas duales, **{STANDARD_SINGLE_AXLE_KN:.0f} kN**
        - **Presentación equivalente:** aproximadamente **{STANDARD_SINGLE_AXLE_KIP:.0f} kip**
        - **Fuente interna:** {EQUIVALENCE_METHOD_SOURCE}
        - **Grupos soportados:** simple, tándem y trídem
        """
    )
    st.caption(
        "Convención interna única: 80 kN. No se reemplaza por 80,07 kN, "
        "8,16 toneladas ni 18.000 lb durante el cálculo."
    )

    st.subheader("3. Observaciones y atípicos")
    observations = pd.DataFrame(
        [
            {
                "ID": item.record_id,
                "Categoría": item.category,
                "Peso bruto kN": item.gross_weight_kn,
                "Grupos": ", ".join(group.axle_type for group in item.axle_groups),
                "Cargas kN": ", ".join(f"{group.load_kn:.2f}" for group in item.axle_groups),
                "Atípico": item.record_id in transfer.outlier_record_ids,
                "Fuente": item.source_reference,
            }
            for item in transfer.observations
        ]
    )
    st.dataframe(observations, hide_index=True, use_container_width=True)
    excluded = st.multiselect(
        "Atípicos a excluir explícitamente",
        options=list(transfer.outlier_record_ids),
        default=[],
        help="Por defecto todos permanecen incluidos. Solo pueden excluirse atípicos ya identificados.",
    )
    exclusion_reason = ""
    if excluded:
        exclusion_reason = st.text_input("Motivo obligatorio de exclusión")
    outlier_treatment = (
        "EXCLUIR_ATIPICOS_SELECCIONADOS"
        if excluded
        else "INCLUIR_TODOS_Y_MARCAR_ATIPICOS"
    )

    reviewer = st.text_input("Revisor ESAL")
    synthetic_ack = False
    if transfer.is_synthetic:
        synthetic_ack = st.checkbox(
            "Reconozco que TPDA/Pesaje son sintéticos y el ESAL es demostrativo"
        )
    has_estimated = any(
        item.load_source == "ESTIMADO_POR_CATEGORIA" for item in transfer.vehicles
    )
    estimated_ack = False
    if has_estimated:
        st.warning(
            "El lote contiene cargas ESTIMADO_POR_CATEGORIA; no son mediciones WIM ni manuales verificadas."
        )
        estimated_ack = st.checkbox(
            "Reconozco visiblemente que las cargas estimadas no son datos medidos"
        )
    assumptions_text = st.text_area(
        "Supuestos adicionales",
        value="Factores camión derivados únicamente de observaciones incluidas.",
    )

    workflow_input = ESALWorkflowInput(
        weighing_transfer=transfer,
        excluded_observation_ids=tuple(excluded),
        exclusion_reason=exclusion_reason,
        outlier_treatment=outlier_treatment,
        reviewer=reviewer,
        synthetic_acknowledged=synthetic_ack,
        estimated_data_acknowledged=estimated_ack,
        assumptions=(assumptions_text,),
    )

    previous = st.session_state.get("esal_phase3_result")
    if isinstance(previous, ESALWorkflowResult):
        stale = esal_result_is_stale(previous, workflow_input, current_weighing)
        if stale:
            st.error(
                "DESACTUALIZADO: cambió Pesaje, método, eje estándar, selección de "
                "atípicos, reconocimiento o supuestos. El resultado anterior se conserva."
            )

    if st.button(
        "Calcular y validar ESAL",
        type="primary",
        disabled=not source_current,
        use_container_width=True,
    ):
        try:
            result = calculate_esal_workflow(workflow_input)
            if isinstance(previous, ESALWorkflowResult):
                st.session_state.setdefault("esal_result_history", []).append(previous)
            st.session_state["esal_phase3_input"] = workflow_input
            st.session_state["esal_phase3_result"] = result
            st.rerun()
        except (TypeError, ValueError, OverflowError) as exc:
            st.error(f"Cálculo bloqueado: {exc}")

    result = st.session_state.get("esal_phase3_result")
    if not isinstance(result, ESALWorkflowResult):
        return

    stale = esal_result_is_stale(result, workflow_input, current_weighing)
    st.subheader("4. Factores equivalentes")
    if stale:
        st.error("Resultado conservado, pero no vigente.")
    elif result.design_readiness == "APTO_PARA_DEMOSTRACION_ACADEMICA":
        st.info("Indicador: APTO_PARA_DEMOSTRACION_ACADEMICA; no es aptitud de diseño oficial.")
    elif result.design_readiness == "APTO_SOLO_DEMOSTRACION":
        st.info("Indicador: APTO_SOLO_DEMOSTRACION.")
    else:
        st.warning("Indicador: NO_APTO_PARA_CONSOLIDACION_DEMOSTRATIVA.")

    axle_frame = pd.DataFrame(
        [
            {
                "Observación": item.observation_id,
                "Categoría": item.category,
                "Grupo": item.group_position,
                "Tipo": item.axle_type,
                "Carga kN": item.load_kn,
                "Referencia kN": item.reference_load_kn,
                "Factor": item.equivalent_factor,
                "Incluido": item.included,
                "Motivo exclusión": item.exclusion_reason,
            }
            for item in result.axle_factors
        ]
    )
    st.dataframe(axle_frame, hide_index=True, use_container_width=True)

    vehicle_frame = pd.DataFrame(
        [
            {
                "Vehículo": item.observation_id,
                "Categoría": item.category,
                "Fuente de carga": item.load_source,
                "Condición de Pesaje": item.weighing_condition,
                "ESAL del vehículo": item.vehicle_factor,
                "Incluido": item.included,
                "Motivo": item.exclusion_reason,
            }
            for item in result.vehicle_factors
        ]
    )
    st.dataframe(vehicle_frame, hide_index=True, use_container_width=True)

    structural_frame = pd.DataFrame(
        [
            {
                "Categoría": item.category,
                "Compatible": item.is_valid,
                "Configuración recibida": " - ".join(item.received_configuration) or "VACÍA",
                "Configuraciones esperadas": " | ".join(
                    " - ".join(pattern) for pattern in item.expected_configurations
                ) or "CONFIGURACION_NO_CONFIRMADA",
                "Códigos": ", ".join(item.error_codes) or "NINGUNO",
                "Mensajes": " ".join(item.messages + item.warnings) or "Compatible",
                "Versión catálogo": item.catalog_version,
            }
            for item in result.structural_validations
        ]
    )
    st.markdown("**Compatibilidad categoría ↔ configuración física**")
    st.dataframe(structural_frame, hide_index=True, use_container_width=True)

    truck_frame = pd.DataFrame(
        [
            {
                "Categoría": item.category,
                "Vehículos": item.observed_vehicles,
                "ESAL observado": item.observed_esal_total,
                "Factor camión medio": item.mean_truck_factor,
                "Desv. estándar": item.standard_deviation,
                "Mínimo": item.minimum,
                "Máximo": item.maximum,
            }
            for item in result.truck_factors_by_category
        ]
    )
    st.dataframe(truck_frame, hide_index=True, use_container_width=True)

    st.subheader("5. Tránsito de diseño y resultados")
    traffic_frame = pd.DataFrame(
        [
            {
                "Categoría": item.category,
                "TPDA base": item.base_traffic,
                "Tránsito proyectado": item.projected_traffic,
                "FDD": item.directional_factor,
                "FDC": item.lane_distribution_factor,
                "Tránsito carril": item.design_lane_traffic,
                "Factor camión": item.truck_factor,
                "ESAL anual inicial": item.initial_annual_esal,
                "ESAL acumulado": item.accumulated_esal,
                "% total": item.total_percent,
            }
            for item in result.traffic_by_category
        ]
    )
    st.dataframe(traffic_frame, hide_index=True, use_container_width=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("ESAL anual inicial", f"{result.initial_annual_esal:,.0f}")
    c2.metric("ESAL acumulado", f"{result.accumulated_esal:,.0f}")
    c3.metric("W18 aproximado demostrativo", f"{result.total_design_esal_w18:,.0f}")

    st.subheader("6. Resumen del lote de cargas analizado")
    s1, s2 = st.columns(2)
    s1.metric("Vehículos incluidos", result.analyzed_batch_vehicle_count)
    s2.metric("ESAL del lote", f"{result.analyzed_batch_esal:,.4f}")
    st.dataframe(pd.DataFrame([
        {"Fuente de carga": "WIM_MEDIDO", "Porcentaje de vehículos": result.measured_vehicle_percent},
        {"Fuente de carga": "MANUAL_VERIFICADO", "Porcentaje de vehículos": result.manual_vehicle_percent},
        {"Fuente de carga": "ESTIMADO_POR_CATEGORIA", "Porcentaje de vehículos": result.estimated_vehicle_percent},
        {"Fuente de carga": "DEMOSTRATIVO_SINTETICO", "Porcentaje de vehículos": result.synthetic_vehicle_percent},
    ]), hide_index=True, use_container_width=True)
    st.caption(
        f"Rechazados: {len(result.rejected_vehicle_ids)} | Pendientes: {len(result.pending_vehicle_ids)}. "
        "Las fuentes se muestran mediante texto y no solo mediante color."
    )

    annual_frame = pd.DataFrame(
        [
            {
                "Año": item.calendar_year,
                "Multiplicador": item.growth_multiplier,
                "ESAL anual": item.annual_esal,
                "ESAL acumulado": item.accumulated_esal,
            }
            for item in result.annual_esal
        ]
    )
    st.line_chart(annual_frame.set_index("Año")[["ESAL anual", "ESAL acumulado"]])
    with st.expander("Detalle técnico y trazabilidad", expanded=True):
        st.json(result.as_dict())
    st.download_button(
        "Descargar resultado ESAL",
        data=json.dumps(result.as_dict(), ensure_ascii=False, indent=2),
        file_name=f"{result.result_id}.json",
        mime="application/json",
    )
    st.info(
        "No existe transferencia a Diseño. El indicador debe auditarse antes de "
        "implementar cualquier consumo de esal_phase3_result."
    )
    render_projection_section(result)


if __name__ == "__main__":
    render()
