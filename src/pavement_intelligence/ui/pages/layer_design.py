"""Página independiente Fase 5B: evaluación demostrativa por capas."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import pandas as pd
import streamlit as st

from pavement_intelligence.aashto93.layer_design_workflow import (
    DesignMode,
    LayerDesignResult,
    LayerInput,
    LayerType,
    LayerWorkflowInput,
    MANDATORY_WARNING,
    SearchRange,
    SearchSettings,
    build_layer_transfer,
    calculate_layer_design,
    coefficient_catalog,
    result_is_stale_5b,
    round_up_thickness,
    store_result,
    thickness_to_inches,
    minimum_thickness_statuses,
)
from pavement_intelligence.aashto93.sn_workflow import (
    AASHTO93Input,
    AASHTO93Result,
    result_is_stale as phase5a_result_is_stale,
)
from pavement_intelligence.ui.utils.widget_state import widget_default

st.title("Diseño demostrativo por capas · Fase 5B")
st.warning(MANDATORY_WARNING)
st.caption(
    "No constituye diseño definitivo, especificación constructiva ni selección normativa automática."
)
st.session_state.setdefault("aashto5b_transfer", None)
st.session_state.setdefault("aashto93_phase5b_history", [])
st.session_state.setdefault(
    "aashto5b_contract_date", datetime.now(timezone.utc).isoformat()
)

source_result = st.session_state.get("aashto93_phase5a_result")
source_input = st.session_state.get("aashto93_phase5a_input")
if st.button(
    "Importar manualmente SN vigente desde Fase 5A", icon=":material/download:"
):
    try:
        if not isinstance(source_result, AASHTO93Result) or not isinstance(
            source_input, AASHTO93Input
        ):
            raise ValueError("No existe resultado e input completos de Fase 5A.")
        st.session_state["aashto5b_transfer"] = build_layer_transfer(
            source_result, source_input
        )
        st.rerun()
    except ValueError as exc:
        st.error(f"Transferencia bloqueada: {exc}")
transfer = st.session_state["aashto5b_transfer"]
if transfer is None:
    st.error("BLOQUEADO: importe manualmente un SN vigente de Fase 5A.")
    st.stop()
if (
    not isinstance(source_result, AASHTO93Result)
    or not isinstance(source_input, AASHTO93Input)
    or source_result.input_fingerprint != transfer.phase5a_fingerprint
    or phase5a_result_is_stale(source_result, source_input)
):
    st.error("DESACTUALIZADO: la transferencia ya no coincide con Fase 5A.")
    st.stop()
st.json(transfer.as_dict(), expanded=False)
st.metric("SN requerido transferido", f"{transfer.required_sn:.4f}")

catalog = coefficient_catalog()
catalog_by_layer = {
    kind.value: [x for x in catalog.values() if x.layer_type == kind.value]
    for kind in LayerType
}
mode = st.segmented_control(
    "Modo de diseño",
    [x.value for x in DesignMode],
    **widget_default(
        st.session_state, "5b_mode", DesignMode.MANUAL.value, parameter="default"
    ),
)
responsible = st.text_input("Responsable Fase 5B", key="5b_responsible")
justification = st.text_area(
    "Justificación de la propuesta y parámetros", key="5b_justification"
)
tolerance = st.number_input(
    "Tolerancia de cumplimiento SN",
    min_value=0.0,
    max_value=0.1,
    format="%.4f",
    **widget_default(st.session_state, "5b_tolerance", 0.001),
)
adjusted = st.selectbox(
    "Capa a ajustar",
    [x.value for x in LayerType],
    disabled=mode != DesignMode.ADJUST_ONE.value,
)

layers = []
st.subheader("Capas y parámetros explícitos")
for kind, label in (
    (LayerType.ASPHALT, "Carpeta asfáltica"),
    (LayerType.BASE, "Base"),
    (LayerType.SUBBASE, "Subbase"),
):
    with st.container(border=True):
        st.markdown(f"#### {label}")
        material = st.text_input(
            f"Material — {label}",
            **widget_default(st.session_state, f"5b_mat_{kind.value}", label),
        )
        unit = st.selectbox(
            f"Unidad — {label}", ["in", "cm", "mm"], key=f"5b_unit_{kind.value}"
        )
        thickness = st.number_input(
            f"Espesor propuesto — {label}",
            min_value=0.0,
            **widget_default(
                st.session_state,
                f"5b_d_{kind.value}",
                4.0 if kind == LayerType.ASPHALT else 6.0,
            ),
        )
        st.caption(f"Conversión interna: {thickness_to_inches(thickness, unit):.6f} in")
        coeff_mode = st.segmented_control(
            f"Origen de a — {label}",
            ["CATALOGO", "MANUAL_JUSTIFICADO"],
            default="CATALOGO",
            key=f"5b_amode_{kind.value}",
        )
        entries = catalog_by_layer[kind.value]
        selected_id = st.selectbox(
            f"Coeficiente catalogado — {label}",
            [x.coefficient_id for x in entries],
            key=f"5b_acat_{kind.value}",
        )
        selected = catalog[selected_id]
        a_value = st.number_input(
            f"Coeficiente estructural a — {label}",
            min_value=0.0001,
            disabled=coeff_mode == "CATALOGO",
            **widget_default(
                st.session_state, f"5b_a_{kind.value}", float(selected.value)
            ),
        )
        a_source = st.text_input(
            f"Fuente de a — {label}",
            **widget_default(
                st.session_state,
                f"5b_asource_{kind.value}",
                selected.source if coeff_mode == "CATALOGO" else "",
            ),
        )
        if kind == LayerType.ASPHALT:
            drainage, quality, saturation, drainage_source = (
                1.0,
                "NO_APLICA_M1_FIJO",
                0.0,
                "m1=1 por formulación",
            )
            st.caption("m1 = 1 fijo; no es editable en esta fase.")
        else:
            drainage = st.number_input(
                f"Coeficiente de drenaje — {label}",
                min_value=0.40,
                max_value=1.40,
                **widget_default(st.session_state, f"5b_m_{kind.value}", 1.0),
            )
            quality = st.text_input(
                f"Calidad de drenaje — {label}", key=f"5b_q_{kind.value}"
            )
            saturation = st.number_input(
                f"Tiempo cercano a saturación (%) — {label}",
                min_value=0.0,
                max_value=100.0,
                **widget_default(st.session_state, f"5b_sat_{kind.value}", 5.0),
            )
            drainage_source = st.text_input(
                f"Fuente del drenaje — {label}", key=f"5b_msource_{kind.value}"
            )
        minimum = st.number_input(
            f"Mínimo manual declarado (0 = no declarado) — {label}",
            min_value=0.0,
            **widget_default(st.session_state, f"5b_min_{kind.value}", 0.0),
        )
        layers.append(
            LayerInput(
                kind.value.lower(),
                kind.value,
                material,
                thickness,
                unit,
                selected.value if coeff_mode == "CATALOGO" else a_value,
                a_source,
                coeff_mode,
                drainage,
                quality,
                saturation,
                drainage_source,
                "Selección explícita del usuario",
                minimum or None,
                unit,
            )
        )

search_ranges = ()
order = "MENOR_EXCEDENTE_SN"
if mode == DesignMode.DISCRETE.value:
    st.subheader("Búsqueda discreta demostrativa")
    rows = []
    for kind in LayerType:
        minimum = st.number_input(
            f"Mínimo búsqueda (in) — {kind.value}",
            min_value=0.0,
            **widget_default(st.session_state, f"5b_smin_{kind.value}", 2.0),
        )
        maximum = st.number_input(
            f"Máximo búsqueda (in) — {kind.value}",
            min_value=0.0,
            **widget_default(st.session_state, f"5b_smax_{kind.value}", 8.0),
        )
        increment = st.number_input(
            f"Incremento (in) — {kind.value}",
            min_value=0.01,
            **widget_default(st.session_state, f"5b_sinc_{kind.value}", 1.0),
        )
        rows.append(SearchRange(kind.value, minimum, maximum, increment))
    search_ranges = tuple(rows)
    order = st.selectbox(
        "Orden demostrativo",
        ["MENOR_EXCEDENTE_SN", "MENOR_ESPESOR_TOTAL", "MENOR_ESPESOR_ASFALTICO"],
        key="5b_order",
    )

rounding = []
if st.checkbox("Aplicar redondeo manual hacia arriba a una capa"):
    round_layer = st.selectbox("Capa a redondear", [x.value for x in LayerType])
    increment = st.number_input(
        "Incremento de redondeo (in)", min_value=0.01, value=0.5
    )
    round_reason = st.text_input("Justificación del redondeo")
    selected_layer = next(x for x in layers if x.layer_type == round_layer)
    try:
        rounding.append(
            round_up_thickness(
                thickness_to_inches(
                    selected_layer.thickness, selected_layer.thickness_unit
                ),
                increment,
                layer_type=round_layer,
                responsible=responsible,
                justification=round_reason,
            )
        )
    except ValueError as exc:
        st.info(f"Redondeo pendiente: {exc}")

data = LayerWorkflowInput(
    transfer,
    tuple(layers),
    mode or DesignMode.MANUAL.value,
    tolerance,
    responsible,
    justification,
    adjusted if mode == DesignMode.ADJUST_ONE.value else None,
    SearchSettings(search_ranges, 10_000, order),
    tuple(rounding),
    created_at=st.session_state["aashto5b_contract_date"],
)
previous = st.session_state.get("aashto93_phase5b_result")
if isinstance(previous, LayerDesignResult) and result_is_stale_5b(previous, data):
    st.error(
        "DESACTUALIZADO: cambiaron capas, parámetros, modo o tolerancia; recalcule."
    )
if st.button(
    "Evaluar propuesta por capas", type="primary", icon=":material/calculate:"
):
    try:
        result = calculate_layer_design(data)
        store_result(st.session_state, data, result)
        st.rerun()
    except (TypeError, ValueError, ArithmeticError, OverflowError) as exc:
        st.error(f"Evaluación bloqueada: {exc}")

result = st.session_state.get("aashto93_phase5b_result")
if isinstance(result, LayerDesignResult):
    st.subheader("Resultado demostrativo")
    st.write(f"Estado textual: **{result.status}**")
    st.metric("SN provisto", f"{result.provided_sn:.4f}")
    st.write(
        f"Déficit: `{result.deficit:.4f}` · Excedente: `{result.excess:.4f}` · Cumplimiento: `{result.compliance_percent:.2f} %`"
    )
    st.dataframe(
        pd.DataFrame([x.__dict__ for x in result.contributions]), hide_index=True
    )
    st.subheader("Control de mínimos manuales declarados")
    minimum_rows = minimum_thickness_statuses(data, result)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Capa": row.material,
                    "Espesor adoptado": row.adopted_thickness,
                    "Mínimo manual": row.declared_minimum,
                    "Diferencia": row.difference,
                    "Unidad": row.display_unit,
                    "Estado": row.status,
                }
                for row in minimum_rows
            ]
        ),
        hide_index=True,
        column_config={
            "Espesor adoptado": st.column_config.NumberColumn(format="%.2f"),
            "Mínimo manual": st.column_config.NumberColumn(format="%.2f"),
            "Diferencia": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    for row in minimum_rows:
        if row.status == "NO CUMPLE MÍNIMO MANUAL DECLARADO":
            st.warning(
                f"Capa: {row.material}\n\n"
                f"Espesor adoptado: {row.adopted_thickness:.2f} {row.display_unit}\n\n"
                f"Mínimo manual declarado: {row.declared_minimum:.2f} {row.display_unit}\n\n"
                f"Déficit respecto del mínimo: {row.deficit:.2f} {row.display_unit}\n\n"
                "Este mínimo fue declarado manualmente y no constituye por sí "
                "mismo un mínimo normativo confirmado."
            )
    if result.alternatives:
        st.caption(
            "Alternativas ordenadas por criterio demostrativo, no económico; no se selecciona una automáticamente."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        **x.__dict__,
                        "thicknesses_in": ", ".join(
                            f"{layer}: {thickness:.1f} in"
                            for layer, thickness in x.thicknesses_in
                        ),
                    }
                    for x in result.alternatives
                ]
            ),
            hide_index=True,
        )
        alternative_failures = []
        for index, alternative in enumerate(result.alternatives, 1):
            checks = minimum_thickness_statuses(
                data, result, adopted_by_layer_in=dict(alternative.thicknesses_in)
            )
            alternative_failures.extend(
                {
                    "Alternativa": index,
                    "Capa": row.material,
                    "Espesor adoptado": row.adopted_thickness,
                    "Mínimo manual": row.declared_minimum,
                    "Déficit": row.deficit,
                    "Unidad": row.display_unit,
                    "Estado": row.status,
                }
                for row in checks
                if row.status == "NO CUMPLE MÍNIMO MANUAL DECLARADO"
            )
        if alternative_failures:
            st.write("Incumplimientos de mínimos manuales en alternativas:")
            st.dataframe(pd.DataFrame(alternative_failures), hide_index=True)
    for warning in result.warnings:
        st.warning(warning)
    st.download_button(
        "Descargar resultado 5B JSON",
        json.dumps(result.as_dict(), ensure_ascii=False, indent=2),
        file_name=f"{result.result_id}.json",
        mime="application/json",
        icon=":material/download:",
    )
