"""Interfaz independiente para caracterización CBR y módulo resiliente — Fase 4A."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
import uuid

import pandas as pd
import streamlit as st

from pavement_intelligence.geotechnics.cbr_workflow import (
    CATALOG_VERSION, METHODOLOGY_WARNING, CBRRecord, CBRWorkflowInput,
    DataOrigin, DesignCBRMode, GeotechnicalResult, calculate_cbr_workflow,
    correlation_catalog, result_is_stale, store_geotechnical_result,
)
from pavement_intelligence.ui.pages.resilient_modulus_review_section import render_review_section


def _demo_records() -> tuple[CBRRecord, ...]:
    return tuple(CBRRecord(
        record_id=f"demo-cbr-{index}", study_id="DEMO-4A", project_segment="Tramo demostrativo",
        location=f"km {index - 1}+000", depth_m=1.5, sample_type="Muestra alterada",
        sample_condition="Preparada", cbr_2_5_mm_percent=value, cbr_5_0_mm_percent=None,
        reported_cbr_percent=value, selection_criterion="CBR final demostrativo",
        compaction_percent=95, dry_density_kn_m3=18, moisture_condition="Saturada",
        saturated=True, compaction_energy="Proctor modificado", test_date="2026-07-18",
        laboratory_or_source="Caso demostrativo interno", responsible="Operador demostrativo",
        declared_standard="Procedimiento no oficial; demostración", data_origin=DataOrigin.SYNTHETIC.value,
        observations="DATO SINTÉTICO", warnings=("No representa ensayo real de laboratorio.",),
    ) for index, value in enumerate((4.0, 6.0, 8.0), 1))


def render() -> None:
    st.title("Caracterización geotécnica CBR — Fase 4A")
    st.warning(METHODOLOGY_WARNING)
    st.caption("Este flujo no escribe en Diseño, AASHTO 93, ESAL ni reportes globales.")
    st.session_state.setdefault("geotechnical_cbr_records", ())
    st.session_state.setdefault("geotechnical_phase4a_input", None)
    st.session_state.setdefault("geotechnical_phase4a_result", None)
    st.session_state.setdefault("geotechnical_phase4a_history", [])

    if st.button("Cargar registros demostrativos", icon=":material/science:"):
        st.session_state["geotechnical_cbr_records"] = _demo_records()
        st.session_state["geotechnical_phase4a_result"] = None
        st.rerun()

    st.subheader("Registrar resultado CBR")
    with st.form("cbr_record_form", border=True):
        study_id = st.text_input("Identificador del estudio")
        segment = st.text_input("Proyecto o tramo")
        location = st.text_input("Ubicación o progresiva")
        depth = st.number_input("Profundidad (m)", min_value=0.0, value=1.5)
        sample_type = st.text_input("Tipo de muestra", value="Muestra alterada")
        sample_condition = st.text_input("Condición de la muestra", value="Preparada")
        cbr_reported = st.number_input("CBR reportado o seleccionado (%)", min_value=0.01, value=5.0)
        cbr_25 = st.number_input("CBR a 2,5 mm (%) — 0 si no disponible", min_value=0.0, value=0.0)
        cbr_50 = st.number_input("CBR a 5,0 mm (%) — 0 si no disponible", min_value=0.0, value=0.0)
        selection = st.text_input("Criterio de selección del CBR reportado", value="Valor final informado")
        compaction = st.number_input("Compactación (%)", min_value=0.01, max_value=100.0, value=95.0)
        density = st.number_input("Densidad seca (kN/m³) — 0 si no disponible", min_value=0.0, value=0.0)
        moisture = st.text_input("Condición de humedad", value="Saturada")
        saturated = st.checkbox("Muestra saturada", value=True)
        energy = st.text_input("Energía de compactación", value="Proctor modificado")
        test_date = st.date_input("Fecha del ensayo", value=date.today())
        source = st.text_input("Laboratorio o fuente")
        responsible = st.text_input("Responsable")
        standard = st.text_input("Norma o procedimiento declarado", value="ASTM D1883 / AASHTO T 193 declarado")
        origin = st.selectbox("Origen del dato", list(DataOrigin), format_func=lambda item: item.value)
        observations = st.text_area("Observaciones")
        submitted = st.form_submit_button("Registrar CBR", icon=":material/add:")
    if submitted:
        record = CBRRecord(
            str(uuid.uuid4()), study_id, segment, location, depth, sample_type, sample_condition,
            cbr_25 or None, cbr_50 or None, cbr_reported, selection, compaction,
            density or None, moisture, saturated, energy or None, test_date.isoformat(), source,
            responsible, standard, origin.value, observations,
        )
        st.session_state["geotechnical_cbr_records"] += (record,)
        st.rerun()

    records = st.session_state["geotechnical_cbr_records"]
    if not records:
        st.info("Sin registros CBR. Registre un resultado o cargue el caso demostrativo.")
        return
    st.subheader("Registros y exclusiones")
    st.dataframe(pd.DataFrame([{
        "ID": item.record_id, "Tramo": item.project_segment, "Ubicación": item.location,
        "CBR (%)": item.reported_cbr_percent, "Origen": item.data_origin,
        "Humedad": item.moisture_condition, "Compactación (%)": item.compaction_percent,
        "Válido": item.is_valid, "Advertencias": " | ".join(item.warnings),
    } for item in records]), hide_index=True, width="stretch")
    edit_id = st.selectbox("Registro a editar", [item.record_id for item in records], key="geotech_edit_id")
    selected_record = next(item for item in records if item.record_id == edit_id)
    edited_cbr = st.number_input("CBR corregido (%)", min_value=0.01,
                                 value=float(selected_record.reported_cbr_percent),
                                 key="geotech_edited_cbr")
    edit_reason = st.text_input("Motivo de edición", key="geotech_edit_reason")
    if st.button("Aplicar edición trazable", icon=":material/edit:"):
        if not edit_reason.strip():
            st.error("La edición exige un motivo.")
        else:
            updated = replace(
                selected_record, reported_cbr_percent=edited_cbr,
                selection_criterion=f"Edición trazable: {edit_reason.strip()}",
                warnings=selected_record.warnings + (f"CBR editado: {edit_reason.strip()}",),
            )
            st.session_state["geotechnical_cbr_records"] = tuple(
                updated if item.record_id == edit_id else item for item in records
            )
            st.rerun()
    excluded = st.multiselect("Excluir registros explícitamente", [item.record_id for item in records])
    effective = tuple(replace(item, is_valid=False, rejection_reason="Exclusión explícita del usuario")
                      if item.record_id in excluded else item for item in records)

    st.subheader("CBR de diseño y correlación")
    mode = st.selectbox("Criterio de CBR de diseño", list(DesignCBRMode), format_func=lambda item: item.value)
    percentile = st.number_input("Percentil (%)", min_value=0.0, max_value=100.0, value=10.0,
                                 disabled=mode != DesignCBRMode.PERCENTILE)
    manual_id = st.selectbox("Registro para selección manual", [""] + [item.record_id for item in records],
                             disabled=mode != DesignCBRMode.JUSTIFIED_MANUAL)
    justification = st.text_input("Justificación de selección manual",
                                  disabled=mode != DesignCBRMode.JUSTIFIED_MANUAL)
    catalog = correlation_catalog()
    correlation_id = st.selectbox("Correlación CBR → MR", list(catalog),
                                  format_func=lambda key: catalog[key].name)
    correlation = catalog[correlation_id]
    st.code(correlation.equation)
    st.caption(f"Intervalo: {correlation.minimum_cbr_percent}–{correlation.maximum_cbr_percent} % CBR | "
               f"Salida nativa: {correlation.native_output_unit} | {correlation.status}")
    st.info(correlation.reference)
    output_unit = st.selectbox("Unidad de visualización del módulo resiliente", ["MPa", "kPa", "psi", "ksi"])
    reviewer = st.text_input("Responsable de Fase 4A")
    synthetic_ack = st.checkbox("Reconozco expresamente los datos sintéticos como demostrativos")
    data = CBRWorkflowInput(
        study_id=records[0].study_id, project_segment=records[0].project_segment, records=effective,
        design_mode=mode.value, percentile=percentile if mode == DesignCBRMode.PERCENTILE else None,
        manual_record_id=manual_id or None, manual_justification=justification,
        correlation_id=correlation_id, reviewer=reviewer, synthetic_acknowledged=synthetic_ack,
        output_unit=output_unit, catalog_version=CATALOG_VERSION,
    )
    previous = st.session_state.get("geotechnical_phase4a_result")
    if isinstance(previous, GeotechnicalResult) and result_is_stale(previous, data):
        st.error("DESACTUALIZADO: cambiaron registros, criterio, correlación, unidad o reconocimientos.")
    if st.button("Calcular módulo resiliente estimado", type="primary", icon=":material/calculate:"):
        try:
            result = calculate_cbr_workflow(data)
            store_geotechnical_result(st.session_state, data, result)
            st.rerun()
        except (TypeError, ValueError, OverflowError) as exc:
            st.error(f"Cálculo bloqueado: {exc}")
    result = st.session_state.get("geotechnical_phase4a_result")
    if not isinstance(result, GeotechnicalResult):
        return
    st.subheader("Resultado geotécnico trazable")
    st.metric("CBR de diseño", f"{result.design_cbr_percent:.3f} %")
    st.metric("Módulo resiliente estimado", f"{result.displayed_resilient_modulus:,.3f} {result.displayed_unit}")
    st.write(f"Estado textual: `{result.methodological_status}`")
    st.write(f"Registros usados: {', '.join(result.used_record_ids)}")
    st.write(f"Registros excluidos: {', '.join(result.excluded_record_ids) or 'ninguno'}")
    for warning in result.warnings:
        st.warning(warning)
    st.download_button("Descargar resultado JSON", json.dumps(result.as_dict(), ensure_ascii=False, indent=2),
                       file_name=f"{result.result_id}.json", mime="application/json",
                       icon=":material/download:")
    render_review_section(result, source_current=not result_is_stale(result, data))


if __name__ == "__main__":
    render()
