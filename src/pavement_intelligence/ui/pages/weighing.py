"""Interfaz controlada de Pesaje vehicular — Fase 2."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from pavement_intelligence.traffic.tpda_workflow import TPDAWorkflowResult
from pavement_intelligence.weighing.workflow import (
    ALLOWED_AXLE_TYPES,
    CANONICAL_WEIGHT_UNIT,
    HEAVY_CATEGORIES,
    WeighingCondition,
    WeighingInputFromTPDA,
    WeighingSourceType,
    WeighingWorkflowInput,
    WeighingWorkflowResult,
    build_manual_observation,
    calculate_weighing_workflow,
    parse_weighing_csv,
    store_weighing_records,
    tpda_transfer_is_current,
    weighing_result_is_stale,
)
from pavement_intelligence.esal.workflow import (
    build_esal_input_from_weighing,
    store_esal_transfer,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEMO_PATH = PROJECT_ROOT / "data/samples/caso_demostrativo/pesaje_vehicular.csv"


def _show_transfer(transfer: WeighingInputFromTPDA) -> None:
    st.subheader("1. Origen del tránsito")
    st.json(
        {
            "resultado_tpda": transfer.source_tpda_result_id,
            "huella_tpda": transfer.source_tpda_fingerprint,
            "estado": transfer.tpda_methodological_status,
            "fecha_transferencia": transfer.transferred_at,
            "periodo_diseño": transfer.design_period_years,
            "tasa_crecimiento": transfer.growth_rate_percent,
            "FDD": transfer.directional_factor,
            "FDC": transfer.lane_distribution_factor,
            "categorias": [item.category for item in transfer.categories],
            "sintetico": transfer.is_synthetic,
            "advertencias": transfer.warnings,
        },
        expanded=False,
    )


def _records_table(records) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ID": item.record_id,
                "Fecha": item.timestamp,
                "Categoría": item.category,
                "Peso bruto (kN)": item.gross_weight_kn,
                "Suma ejes (kN)": item.axle_load_sum_kn,
                "Ejes físicos": item.physical_axle_count,
                "Configuración": ", ".join(group.axle_type for group in item.axle_groups),
                "Condición": item.condition,
                "Fuente": item.source_reference,
            }
            for item in records
        ]
    )


def render() -> None:
    st.title("⚖️ Pesaje vehicular — Fase 2")
    st.warning(
        "Este módulo valida cargas y prepara un resultado para auditoría. "
        "No transfiere datos ni calcula ESAL."
    )

    transfer = st.session_state.get("weighing_input_from_tpda")
    current_tpda = st.session_state.get("tpda_phase1_result")
    if not isinstance(transfer, WeighingInputFromTPDA):
        st.error(
            "No existe una transferencia manual válida desde TPDA. "
            "Regrese a Aforo y TPDA y use “Usar TPDA validado en Pesaje”."
        )
        st.stop()
    if not isinstance(current_tpda, TPDAWorkflowResult):
        current_tpda = None

    _show_transfer(transfer)
    transfer_current = tpda_transfer_is_current(transfer, current_tpda)
    if not transfer_current:
        st.error(
            "La firma TPDA actual no coincide con la transferencia de Pesaje. "
            "Los datos se conservan, pero se requiere una nueva transferencia."
        )
    if transfer.is_synthetic:
        st.error("Cadena TPDA sintética: Pesaje operará únicamente en modo demostrativo.")

    st.subheader("2. Fuente de cargas")
    source_label = st.selectbox(
        "Tipo de fuente",
        [
            "Archivo CSV",
            "Exportación WIM",
            "Pesaje estático",
            "Ingreso manual",
            "Biblioteca demostrativa",
        ],
    )
    source_type = {
        "Archivo CSV": WeighingSourceType.CSV,
        "Exportación WIM": WeighingSourceType.WIM,
        "Pesaje estático": WeighingSourceType.STATIC_SCALE,
        "Ingreso manual": WeighingSourceType.MANUAL,
        "Biblioteca demostrativa": WeighingSourceType.DEMONSTRATION_LIBRARY,
    }[source_label]
    source_date = st.date_input("Fecha de la fuente", value=date.today()).isoformat()
    reviewer = st.text_input("Revisor de Pesaje")
    candidate = None
    source_reference = ""
    candidate_synthetic = False

    if source_type in {
        WeighingSourceType.CSV,
        WeighingSourceType.WIM,
        WeighingSourceType.STATIC_SCALE,
    }:
        uploaded = st.file_uploader("Archivo CSV de cargas", type=["csv"])
        condition_label = st.selectbox(
            "Condición declarada de los datos",
            ["Medidos", "Importados", "Asumidos"],
        )
        condition = {
            "Medidos": WeighingCondition.MEASURED,
            "Importados": WeighingCondition.IMPORTED,
            "Asumidos": WeighingCondition.ASSUMED,
        }[condition_label]
        if uploaded is not None and reviewer:
            try:
                text = uploaded.getvalue().decode("utf-8-sig")
                source_reference = uploaded.name
                candidate = parse_weighing_csv(
                    text,
                    source_reference=source_reference,
                    source_type=source_type,
                    condition=condition,
                    reviewer=reviewer,
                )
                candidate_synthetic = condition == WeighingCondition.SYNTHETIC
                st.success(f"Muestra validada estructuralmente: {len(candidate)} registros.")
            except (UnicodeDecodeError, ValueError) as exc:
                st.error(f"Archivo rechazado: {exc}")
    elif source_type == WeighingSourceType.DEMONSTRATION_LIBRARY:
        st.error(
            "pesaje_vehicular.csv es sintético y no constituye evidencia de cargas reales."
        )
        if st.checkbox("Reconozco el carácter sintético de la biblioteca") and reviewer:
            source_reference = str(DEMO_PATH)
            try:
                candidate = parse_weighing_csv(
                    DEMO_PATH,
                    source_reference=source_reference,
                    source_type=source_type,
                    condition=WeighingCondition.SYNTHETIC,
                    reviewer=reviewer,
                )
                candidate_synthetic = True
                st.success(f"Biblioteca demostrativa preparada: {len(candidate)} registros.")
            except ValueError as exc:
                st.error(str(exc))
    else:
        transferred_categories = [
            item.category
            for item in transfer.categories
            if item.requires_load_configuration
        ]
        category = st.selectbox("Categoría estructural", transferred_categories or ["SIN_CATEGORIA"])
        unit = st.selectbox("Unidad de entrada", ["kN", "kg", "toneladas"])
        gross = st.number_input("Peso bruto", min_value=0.0, value=0.0)
        group_count = st.number_input("Número de grupos de eje", min_value=1, max_value=6, value=2)
        groups = []
        for index in range(int(group_count)):
            c1, c2 = st.columns(2)
            axle_type = c1.selectbox(
                f"Tipo grupo {index + 1}",
                sorted(ALLOWED_AXLE_TYPES),
                key=f"weighing_axle_type_{index}",
            )
            load = c2.number_input(
                f"Carga grupo {index + 1}",
                min_value=0.0,
                value=0.0,
                key=f"weighing_axle_load_{index}",
            )
            groups.append((axle_type, load))
        condition = st.selectbox(
            "Origen de la configuración",
            [
                WeighingCondition.MEASURED.value,
                WeighingCondition.ASSUMED.value,
            ],
        )
        source_reference = st.text_input("Referencia de medición o supuesto")
        if gross > 0 and all(load > 0 for _, load in groups) and reviewer and source_reference:
            try:
                observation = build_manual_observation(
                    category=category,
                    gross_weight=gross,
                    axle_groups=tuple(groups),
                    unit=unit,
                    source_type=source_type,
                    source_reference=source_reference,
                    condition=WeighingCondition(condition),
                    reviewer=reviewer,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                candidate = (observation,)
            except ValueError as exc:
                st.error(str(exc))

    existing_records = st.session_state.get("weighing_records_current")
    decision = "replace"
    if existing_records is not None and candidate is not None:
        st.warning("Ya existe una muestra de Pesaje; no se reemplazará silenciosamente.")
        choice = st.radio(
            "Decisión sobre la muestra existente",
            [
                "Conservar muestra actual",
                "Reemplazar y conservar histórico",
                "Cancelar carga",
            ],
        )
        decision = {
            "Conservar muestra actual": "keep",
            "Reemplazar y conservar histórico": "replace",
            "Cancelar carga": "cancel",
        }[choice]
    if candidate is not None and st.button("Adoptar muestra validada"):
        stored = store_weighing_records(
            st.session_state,
            candidate,
            decision=decision,
        )
        if stored:
            st.success("Muestra adoptada. El resultado anterior, si existe, se conserva como histórico.")
            st.rerun()
        else:
            st.info("La muestra existente fue conservada.")

    records = st.session_state.get("weighing_records_current")
    if records is None:
        st.info("No hay una muestra de cargas adoptada.")
        st.stop()

    st.subheader("3. Configuraciones y validación")
    st.caption(f"Unidad interna canónica: {CANONICAL_WEIGHT_UNIT}.")
    st.dataframe(_records_table(records), hide_index=True, use_container_width=True)
    tolerance = st.number_input(
        "Tolerancia entre suma de ejes y peso bruto (%)",
        min_value=0.1,
        max_value=20.0,
        value=5.0,
    )
    outlier_treatment = st.selectbox(
        "Tratamiento de valores atípicos",
        ["MARCAR_SIN_EXCLUIR", "REVISAR_MANUALMENTE"],
    )
    synthetic_chain = transfer.is_synthetic or any(
        item.condition == WeighingCondition.SYNTHETIC.value for item in records
    )
    synthetic_ack = False
    if synthetic_chain:
        synthetic_ack = st.checkbox(
            "Reconozco que la cadena contiene datos sintéticos y es solo demostrativa"
        )

    workflow_input = WeighingWorkflowInput(
        tpda_transfer=transfer,
        observations=tuple(records),
        source_type=source_type,
        source_reference=source_reference or records[0].source_reference,
        source_date=source_date,
        reviewer=reviewer or records[0].reviewer,
        validation_state="REVISADO_EN_UI",
        assumptions=(
            "Las configuraciones de eje proceden exclusivamente de la fuente declarada.",
        ),
        gross_axle_tolerance_percent=tolerance,
        outlier_treatment=outlier_treatment,
        synthetic_acknowledged=synthetic_ack,
    )

    previous = st.session_state.get("weighing_phase2_result")
    if isinstance(previous, WeighingWorkflowResult):
        stale = weighing_result_is_stale(previous, workflow_input, current_tpda)
        if stale:
            st.error(
                "DESACTUALIZADO: cambió TPDA, la muestra, configuración, fuente, "
                "tolerancia o tratamiento de atípicos. El resultado anterior se conserva."
            )

    if st.button(
        "Validar y calcular resultado de Pesaje",
        type="primary",
        disabled=not transfer_current,
        use_container_width=True,
    ):
        result = calculate_weighing_workflow(workflow_input)
        if isinstance(previous, WeighingWorkflowResult):
            st.session_state.setdefault("weighing_result_history", []).append(previous)
        st.session_state["weighing_phase2_result"] = result
        st.session_state["weighing_phase2_input"] = workflow_input
        st.rerun()

    result = st.session_state.get("weighing_phase2_result")
    if isinstance(result, WeighingWorkflowResult):
        stale = weighing_result_is_stale(result, workflow_input, current_tpda)
        st.subheader("4. Resultado formal")
        if stale:
            st.error("Resultado conservado, pero no vigente.")
        elif result.esal_readiness == "APTO_PARA_ESAL":
            st.success("Indicador: APTO_PARA_ESAL. Pendiente de auditoría independiente.")
        elif result.esal_readiness == "APTO_SOLO_DEMOSTRACION":
            st.info("Indicador: APTO_SOLO_DEMOSTRACION.")
        else:
            st.warning("Indicador: NO_APTO_PARA_ESAL.")
        c1, c2, c3 = st.columns(3)
        c1.metric("Observaciones", result.observation_count)
        c2.metric("Categorías", len(result.categories))
        c3.metric("Atípicos", len(result.outlier_record_ids))
        with st.expander("Detalle técnico y trazabilidad", expanded=True):
            st.json(result.as_dict())
        st.download_button(
            "Descargar resultado de Pesaje",
            data=json.dumps(result.as_dict(), ensure_ascii=False, indent=2),
            file_name=f"{result.result_id}.json",
            mime="application/json",
        )

        st.subheader("5. Transferir resultado validado a ESAL")
        st.caption(
            "Transferencia manual de observaciones, configuraciones, cargas y tránsito. "
            "No calcula ESAL ni publica W18 en Diseño."
        )
        st.json(
            {
                "resultado_pesaje": result.result_id,
                "fecha": result.created_at,
                "fuente_tpda": result.source_tpda_result_id,
                "fuente_pesaje": result.source_reference,
                "categorias": result.categories,
                "configuraciones": result.axle_configurations,
                "observaciones": result.observation_count,
                "unidad": result.canonical_weight_unit,
                "estado": result.methodological_status,
                "sintetico": result.is_synthetic,
                "advertencias": result.warnings,
                "aptitud": result.esal_readiness,
            },
            expanded=False,
        )
        existing_esal = any(
            st.session_state.get(key) is not None
            for key in (
                "esal_input_from_weighing",
                "esal_phase3_input",
                "esal_phase3_result",
                "esal_result",
            )
        )
        esal_decision = "replace"
        if existing_esal:
            st.warning("ESAL ya contiene configuración o resultados; no se sobrescribirán.")
            esal_choice = st.radio(
                "Decisión sobre el estado ESAL existente",
                [
                    "Conservar configuración ESAL actual",
                    "Reemplazar y conservar histórico ESAL",
                    "Cancelar transferencia a ESAL",
                ],
            )
            esal_decision = {
                "Conservar configuración ESAL actual": "keep",
                "Reemplazar y conservar histórico ESAL": "replace",
                "Cancelar transferencia a ESAL": "cancel",
            }[esal_choice]

        esal_demo = False
        if result.is_synthetic:
            esal_demo = st.checkbox(
                "Transferir a ESAL únicamente en modo demostrativo",
                key="weighing_esal_demo_mode",
            )
        esal_confirmed = st.checkbox(
            "Confirmo que revisé cargas, ejes, atípicos, estado y advertencias",
            key="weighing_esal_transfer_confirmed",
        )
        transfer_disabled = (
            stale
            or not esal_confirmed
            or (
                result.esal_readiness != "APTO_PARA_ESAL"
                and not (
                    result.esal_readiness == "APTO_SOLO_DEMOSTRACION"
                    and esal_demo
                )
            )
        )
        if stale:
            st.error("No se puede transferir un resultado de Pesaje desactualizado.")
        if st.button(
            "Usar pesaje validado en ESAL",
            disabled=transfer_disabled,
            use_container_width=True,
        ):
            try:
                esal_transfer = build_esal_input_from_weighing(
                    result,
                    allow_demonstration=esal_demo,
                )
                stored = store_esal_transfer(
                    st.session_state,
                    esal_transfer,
                    decision=esal_decision,
                )
                if stored:
                    st.success("Contrato Pesaje → ESAL creado. Abra ESAL para calcular.")
                else:
                    st.info("Transferencia cancelada; se conservó el estado ESAL actual.")
            except ValueError as exc:
                st.error(f"Transferencia bloqueada: {exc}")


if __name__ == "__main__":
    render()
