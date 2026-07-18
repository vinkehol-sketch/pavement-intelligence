"""Interfaz de Aforo y TPDA.

La pantalla recopila entradas y presenta resultados. Toda la matemática y la
decisión metodológica residen en traffic.tpda_workflow.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from pavement_intelligence.traffic.tpda_workflow import (
    ExpansionMethod,
    FactorTrace,
    MethodologicalStatus,
    OFFICIAL_TPDA_CATEGORIES,
    PENDING_TRUCK_CATEGORY,
    ProjectionMethod,
    TPDAWorkflowInput,
    TPDAWorkflowResult,
    TemporalCoverage,
    TruckReclassification,
    calculate_tpda_workflow,
    classify_visual_events,
    inspect_csv_temporal_coverage,
    reclassify_pending_trucks,
    result_is_stale,
)
from pavement_intelligence.utils.validators import (
    validate_design_period,
    validate_growth_rate,
    validate_survey_duration,
)
from pavement_intelligence.weighing.workflow import (
    build_weighing_input_from_tpda,
    store_weighing_transfer,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEMO_SURVEY_PATH = PROJECT_ROOT / "data/samples/caso_demostrativo/aforo_24h.csv"
DEFAULT_DEMO_COUNTS = {
    "MOTO": 85, "AUTO": 650, "CAMIONETA": 320, "MINIBUS": 90,
    "BUS": 45, "C2": 55, "C3": 12, "TRACTOCAMION": 8,
    "ARTICULADO": 5, "OTRO_PESADO": 3,
}


def _empty_counts() -> dict[str, int]:
    return {category: 0 for category in OFFICIAL_TPDA_CATEGORIES}


def _stable_batch_id(source: str, counts: dict[str, int | float]) -> str:
    payload = json.dumps({"source": source, "counts": counts}, sort_keys=True)
    return "batch-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _counts_from_review(payload: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    counts = _empty_counts()
    pending = {PENDING_TRUCK_CATEGORY: 0}
    for category, raw in payload.get("counts_by_category", {}).items():
        normalized = str(category).upper()
        value = int(raw)
        if normalized in counts:
            counts[normalized] += value
        elif normalized in {"CAMION", "TRUCK", PENDING_TRUCK_CATEGORY}:
            pending[PENDING_TRUCK_CATEGORY] += value
    return counts, pending


def _read_count_csv(data: Any) -> tuple[pd.DataFrame, dict[str, int], list[str]]:
    frame = pd.read_csv(data)
    required = {"category_id", "count"}
    if not required.issubset(frame.columns):
        raise ValueError("El CSV debe contener category_id y count.")
    counts = _empty_counts()
    warnings: list[str] = []
    for _, row in frame.iterrows():
        category = str(row["category_id"]).strip().upper()
        value = int(row["count"])
        if value < 0:
            raise ValueError(f"Conteo negativo para {category}.")
        if category in counts:
            counts[category] += value
        elif category in {"CAMION", "TRUCK", PENDING_TRUCK_CATEGORY}:
            warnings.append(f"{value} camiones requieren reclasificación manual.")
        else:
            warnings.append(f"Categoría ignorada por no pertenecer al catálogo: {category}.")
    return frame, counts, warnings


def _render_status(result: TPDAWorkflowResult, stale: bool) -> None:
    status = MethodologicalStatus.STALE.value if stale else result.methodological_status
    if stale:
        st.error("DESACTUALIZADO: las entradas cambiaron. El resultado previo se conserva y requiere recálculo.")
    elif result.methodologically_fit_for_next_phase:
        st.success("Resultado metodológicamente apto para la siguiente fase.")
    elif result.methodological_status == MethodologicalStatus.VALID_FOR_DEMONSTRATION.value:
        st.info("Resultado válido únicamente para demostración; no habilita la siguiente fase.")
    else:
        st.warning(f"Estado metodológico: {status}")


def render() -> None:
    st.title("📊 Aforo y TPDA — Fase 1")
    st.caption(
        "Conteo revisado → clasificación válida → expansión temporal única → "
        "TPDA base → proyección trazable"
    )
    st.warning(
        "Esta fase no transfiere resultados a Pesaje ni ESAL. Los factores configurables "
        "no están validados como valores oficiales para Bolivia."
    )

    review_payload = st.session_state.get("tpda_input_from_review")
    sources = ["Introducción manual", "Importar CSV", "Eventos visuales en sesión"]
    if review_payload:
        sources.insert(0, "Conteo revisado aprobado")
    source_mode = st.radio("Origen de los conteos", sources, horizontal=True)

    automatic_counts = _empty_counts()
    pending = {PENDING_TRUCK_CATEGORY: 0}
    source = "manual"
    data_origin = "MANUAL"
    source_warnings: list[str] = []
    is_synthetic = False
    temporal_evidence = False
    duration_source = "DECLARADA_POR_OPERADOR"
    reviewer_default = ""

    if source_mode == "Conteo revisado aprobado" and review_payload:
        automatic_counts, pending = _counts_from_review(review_payload)
        source = str(review_payload.get("source", "traffic_review"))
        data_origin = str(review_payload.get("data_origin", "VIDEO_REVISADO"))
        is_synthetic = bool(review_payload.get("is_synthetic", False))
        source_warnings.extend(review_payload.get("warnings", []))
        reviewer_default = str(review_payload.get("reviewer", ""))
        st.success("Conteo revisado cargado con su trazabilidad de origen.")
    elif source_mode == "Eventos visuales en sesión":
        events = st.session_state.get("corrected_records") or st.session_state.get("events") or []
        automatic_counts, pending = classify_visual_events(events)
        source = "eventos_visuales_sesion"
        data_origin = "VISION_PENDIENTE_DE_REVISION"
        st.info(f"Eventos encontrados: {len(events)}.")
    elif source_mode == "Importar CSV":
        uploaded = st.file_uploader("CSV de conteo", type=["csv"])
        load_demo = st.button("Cargar CSV demostrativo agregado")
        if load_demo:
            st.session_state["tpda_demo_csv_selected"] = True
        selected: Any | None = uploaded
        if selected is None and st.session_state.get("tpda_demo_csv_selected"):
            selected = DEMO_SURVEY_PATH
            is_synthetic = True
            source = str(DEMO_SURVEY_PATH)
            data_origin = "CSV_SINTETICO_DEMOSTRATIVO"
        if selected is not None:
            try:
                frame, automatic_counts, csv_warnings = _read_count_csv(selected)
                source_warnings.extend(csv_warnings)
                temporal_evidence = inspect_csv_temporal_coverage(list(frame.columns))
                duration_source = (
                    "METADATOS_TEMPORALES_DEL_CSV"
                    if temporal_evidence
                    else "DURACION_DECLARADA_SIN_EVIDENCIA_INTERNA"
                )
                if uploaded is not None:
                    source = uploaded.name
                    data_origin = "CSV_CARGADO_POR_USUARIO"
                st.success(f"CSV cargado: {len(frame)} registros.")
            except Exception as exc:
                st.error(str(exc))
    else:
        use_demo = st.checkbox("Usar conteos sintéticos de demostración")
        if use_demo:
            automatic_counts = dict(DEFAULT_DEMO_COUNTS)
            source = "valores_demostrativos_integrados"
            data_origin = "SINTETICO_DEMOSTRATIVO"
            is_synthetic = True

    st.subheader("1. Clasificación y corrección")
    count_frame = pd.DataFrame(
        {
            "Categoría": list(OFFICIAL_TPDA_CATEGORIES),
            "Conteo automático": [automatic_counts[c] for c in OFFICIAL_TPDA_CATEGORIES],
            "Conteo corregido": [automatic_counts[c] for c in OFFICIAL_TPDA_CATEGORIES],
        }
    )
    edited = st.data_editor(
        count_frame,
        hide_index=True,
        use_container_width=True,
        disabled=["Categoría", "Conteo automático"],
        column_config={
            "Conteo corregido": st.column_config.NumberColumn(min_value=0, step=1, format="%d")
        },
        key="tpda_count_editor",
    )
    corrected_counts = {
        str(row["Categoría"]): int(row["Conteo corregido"])
        for _, row in edited.iterrows()
    }

    pending_input = st.number_input(
        "Camiones visuales sin confirmar",
        min_value=0,
        value=int(pending[PENDING_TRUCK_CATEGORY]),
        step=1,
        help="No se asignan automáticamente a C2 ni se asume número de ejes.",
    )
    pending = {PENDING_TRUCK_CATEGORY: int(pending_input)}
    reclassifications: tuple[TruckReclassification, ...] = ()

    if pending_input:
        st.warning("CAMION_NO_CONFIRMADO: requiere reclasificación manual antes de continuar.")
        with st.expander("Reclasificar camiones pendientes", expanded=True):
            target = st.selectbox("Categoría vehicular confirmada", OFFICIAL_TPDA_CATEGORIES[5:])
            reason = st.text_input("Motivo de reclasificación")
            truck_reviewer = st.text_input("Revisor de clasificación")
            if st.button("Registrar reclasificación"):
                try:
                    updated, remaining, trace = reclassify_pending_trucks(
                        corrected_counts,
                        int(pending_input),
                        target,
                        reason,
                        truck_reviewer,
                    )
                    st.session_state["tpda_truck_resolution"] = {
                        "pending_source": int(pending_input),
                        "counts": updated,
                        "remaining": remaining,
                        "trace": asdict(trace),
                    }
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    resolution = st.session_state.get("tpda_truck_resolution")
    if resolution and resolution.get("pending_source") == int(pending_input):
        corrected_counts = dict(resolution["counts"])
        pending = dict(resolution["remaining"])
        reclassifications = (TruckReclassification(**resolution["trace"]),)
        st.success("Reclasificación manual aplicada y trazada.")

    st.subheader("2. Cobertura y expansión temporal")
    duration = st.number_input(
        "Duración declarada del aforo (horas)",
        min_value=0.1,
        max_value=168.0,
        value=24.0,
        step=1.0,
    )
    duration_validation = validate_survey_duration(duration)
    for warning in duration_validation.warnings:
        st.warning(warning)
    for error in duration_validation.errors:
        st.error(error)

    verified_hours: float | None = duration if temporal_evidence else None
    coverage_confirmed = temporal_evidence or duration < 24
    if duration >= 24 and not temporal_evidence:
        st.warning(
            "El archivo o registro fue declarado como aforo de 24 horas, pero su "
            "cobertura temporal no puede verificarse automáticamente."
        )
        coverage_confirmed = st.checkbox(
            "Confirmo manualmente que la duración declarada corresponde a la cobertura del aforo"
        )

    temporal_trace: FactorTrace | None = None
    if duration < 24:
        expansion_label = st.selectbox(
            "Método único de expansión temporal",
            ["Uniforme 24/duración", "Factor temporal documentado por el usuario"],
        )
        if expansion_label.startswith("Uniforme"):
            expansion_method = ExpansionMethod.UNIFORM_24_OVER_HOURS
        else:
            expansion_method = ExpansionMethod.DOCUMENTED_TEMPORAL_FACTOR
            temporal_value = st.number_input(
                "f_n — factor de expansión temporal",
                min_value=0.01,
                value=1.0,
                step=0.05,
            )
            temporal_source = st.text_input("Fuente del factor temporal", value="")
            temporal_trace = FactorTrace(
                symbol="f_n",
                name="Factor de expansión temporal",
                value=temporal_value,
                function="Sustituye a 24/duración; convierte el periodo observado a 24 horas.",
                source=temporal_source or "SIN_FUENTE_DECLARADA",
                applicability="Solo aforos menores a 24 horas.",
            )
            st.warning("Factor definido por el usuario; no validado como valor oficial para Bolivia.")
    else:
        expansion_method = ExpansionMethod.NONE_24H
        st.info("Sin expansión horaria adicional para un aforo declarado de 24 horas o más.")

    seasonal_value = st.number_input(
        "f_e — factor de corrección del periodo observado",
        min_value=0.01,
        value=1.0,
        step=0.05,
    )
    seasonal_source = st.text_input(
        "Fuente de f_e",
        value="Identidad 1,0; sin corrección estacional" if seasonal_value == 1 else "",
    )
    seasonal_trace = FactorTrace(
        symbol="f_e",
        name="Factor de corrección estacional configurable",
        value=seasonal_value,
        function="Convierte el TPD del periodo observado en TPDA.",
        source=seasonal_source or "SIN_FUENTE_DECLARADA",
        applicability="Aplicar una vez; usar 1,0 si no se justifica corrección.",
    )
    st.caption("f_n y f_e son configurables; no se presentan como factores oficiales de la ABC.")

    st.subheader("3. Proyección y distribución posterior")
    projection_label = st.selectbox(
        "Método de proyección",
        ["Exponencial / compuesto — principal del MVP", "Lineal B — alternativa académica no oficial"],
    )
    projection_method = (
        ProjectionMethod.EXPONENTIAL
        if projection_label.startswith("Exponencial")
        else ProjectionMethod.LINEAR_B_ACADEMIC
    )
    with st.expander("Método histórico Lineal A — experimental, no seleccionable"):
        st.error(
            "Lineal A mezcla bases expandidas y no expandidas. Se conserva solo por "
            "trazabilidad histórica y está excluida del flujo normal."
        )

    growth_rate = st.number_input("Tasa anual de crecimiento (%)", min_value=0.0, value=4.0)
    design_period = st.number_input("Periodo de diseño (años)", min_value=5, value=20, step=1)
    base_year = st.number_input("Año base", min_value=1900, value=datetime.now().year, step=1)
    for validation in (validate_growth_rate(growth_rate), validate_design_period(int(design_period))):
        for warning in validation.warnings:
            st.warning(warning)
        for error in validation.errors:
            st.error(error)

    st.markdown("**Distribución posterior al TPDA base y a la proyección**")
    fdd = st.number_input("FDD — factor direccional", min_value=0.01, max_value=1.0, value=0.5)
    fdc = st.number_input("FDC — factor por carril", min_value=0.01, max_value=1.0, value=1.0)

    reviewer = st.text_input("Responsable del cálculo", value=reviewer_default)
    synthetic_ack = False
    if is_synthetic:
        st.error("Los conteos son sintéticos y solo sirven para demostración.")
        synthetic_ack = st.checkbox("Reconozco que los datos son sintéticos")

    batch_id = (
        str(review_payload.get("batch_hash"))
        if source_mode == "Conteo revisado aprobado" and review_payload
        else _stable_batch_id(source, automatic_counts)
    )
    workflow_input = TPDAWorkflowInput(
        batch_id=batch_id,
        source=source,
        data_origin=data_origin,
        automatic_counts=automatic_counts,
        corrected_counts=corrected_counts,
        pending_categories=pending,
        temporal_coverage=TemporalCoverage(
            declared_hours=duration,
            verified_hours=verified_hours,
            duration_source=duration_source,
            operator_confirmed=coverage_confirmed,
        ),
        expansion_method=expansion_method,
        temporal_factor=temporal_trace,
        seasonal_factor=seasonal_trace,
        projection_method=projection_method,
        growth_rate_percent=growth_rate,
        design_period_years=int(design_period),
        base_year=int(base_year),
        directional_factor=fdd,
        lane_distribution_factor=fdc,
        reviewer=reviewer,
        reclassifications=reclassifications,
        warnings=tuple(source_warnings),
        assumptions=("Factores configurables sujetos a respaldo del operador.",),
        is_synthetic=is_synthetic,
        synthetic_acknowledged=synthetic_ack,
    )

    previous = st.session_state.get("tpda_phase1_result")
    if isinstance(previous, TPDAWorkflowResult):
        _render_status(previous, result_is_stale(previous, workflow_input))

    if st.button("Calcular y evaluar Fase 1", type="primary", use_container_width=True):
        try:
            result = calculate_tpda_workflow(workflow_input)
            st.session_state["tpda_phase1_result"] = result
            st.session_state["tpda_phase1_input"] = workflow_input
            st.session_state["aforos_registrados"] = st.session_state.get("aforos_registrados", 0) + 1
            st.rerun()
        except (TypeError, ValueError, OverflowError) as exc:
            st.error(f"No se pudo calcular: {exc}")

    result = st.session_state.get("tpda_phase1_result")
    if isinstance(result, TPDAWorkflowResult):
        stale = result_is_stale(result, workflow_input)
        st.subheader("4. Resultado formal")
        _render_status(result, stale)
        c1, c2, c3 = st.columns(3)
        c1.metric("TPDA base", f"{result.tpda_base_total:,.1f} veh/día")
        c2.metric(
            f"Proyectado {result.design_year}",
            f"{result.projected_traffic_total:,.1f} veh/día",
        )
        c3.metric("Carril de diseño", f"{result.projected_design_lane_traffic:,.1f} veh/día")

        plot = pd.DataFrame(
            {
                "Categoría": list(result.tpda_by_category),
                "TPDA base": list(result.tpda_by_category.values()),
                "Proyectado": [
                    result.projected_traffic_by_category[c] for c in result.tpda_by_category
                ],
            }
        )
        if not plot.empty:
            st.plotly_chart(
                px.bar(
                    plot.melt(id_vars="Categoría", var_name="Etapa", value_name="veh/día"),
                    x="Categoría",
                    y="veh/día",
                    color="Etapa",
                    barmode="group",
                ),
                use_container_width=True,
            )

        with st.expander("Detalle técnico y trazabilidad", expanded=True):
            st.json(result.as_dict())
            st.markdown(
                "Aforo observado → expansión temporal → TPDA base → proyección → "
                "distribución direccional → distribución por carril"
            )
        st.download_button(
            "Descargar resultado JSON",
            data=json.dumps(result.as_dict(), ensure_ascii=False, indent=2),
            file_name=f"{result.calculation_id}.json",
            mime="application/json",
        )

        st.subheader("5. Transferir resultado a Pesaje")
        st.caption(
            "La transferencia es manual y crea un contrato independiente. "
            "No calcula cargas ni conecta con ESAL."
        )
        st.json(
            {
                "resultado_tpda": result.calculation_id,
                "estado": result.methodological_status,
                "periodo_diseño": result.design_period_years,
                "categorias": result.tpda_by_category,
                "sintetico": result.is_synthetic,
                "advertencias": result.warnings,
            },
            expanded=False,
        )
        existing_weighing = any(
            st.session_state.get(key) is not None
            for key in (
                "weighing_input_from_tpda",
                "weighing_records_current",
                "weighing_phase2_result",
                "pesaje_df",
            )
        )
        decision = "replace"
        if existing_weighing:
            st.warning(
                "Pesaje ya contiene una entrada, muestra o resultado. "
                "Nada será reemplazado sin una decisión explícita."
            )
            decision_label = st.radio(
                "Decisión sobre los datos existentes en Pesaje",
                [
                    "Conservar datos actuales",
                    "Reemplazar y conservar histórico",
                    "Cancelar transferencia",
                ],
            )
            decision = {
                "Conservar datos actuales": "keep",
                "Reemplazar y conservar histórico": "replace",
                "Cancelar transferencia": "cancel",
            }[decision_label]

        demo_transfer = False
        if result.is_synthetic:
            demo_transfer = st.checkbox(
                "Transferir exclusivamente en modo demostrativo",
                key="tpda_weighing_demo_mode",
            )
        transfer_confirmed = st.checkbox(
            "Confirmo que revisé el estado, categorías, periodo, factores y advertencias",
            key="tpda_weighing_transfer_confirmed",
        )
        transfer_disabled = (
            stale
            or not transfer_confirmed
            or (
                not result.methodologically_fit_for_next_phase
                and not (
                    result.methodological_status
                    == MethodologicalStatus.VALID_FOR_DEMONSTRATION.value
                    and demo_transfer
                )
            )
        )
        if stale:
            st.error("No se puede transferir un resultado TPDA desactualizado.")
        if st.button(
            "Usar TPDA validado en Pesaje",
            disabled=transfer_disabled,
            use_container_width=True,
        ):
            try:
                transfer = build_weighing_input_from_tpda(
                    result,
                    allow_demonstration=demo_transfer,
                )
                stored = store_weighing_transfer(
                    st.session_state,
                    transfer,
                    decision=decision,
                )
                if stored:
                    st.success(
                        "Contrato TPDA → Pesaje creado. Abra Pesaje para configurar cargas."
                    )
                else:
                    st.info("Transferencia cancelada; los datos actuales se conservaron.")
            except ValueError as exc:
                st.error(f"Transferencia bloqueada: {exc}")


if __name__ == "__main__":
    render()
