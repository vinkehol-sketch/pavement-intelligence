"""Centro de monitoreo de tráfico con datos exclusivamente simulados."""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd
import streamlit as st

from pavement_intelligence.domain.traffic.presentation import DashboardOperationalState
from pavement_intelligence.ui.utils.demo_data import PROJECT_ROOT, load_demo_dashboard, validate_dashboard_state
from pavement_intelligence.ui.utils.formatting import format_unit
from pavement_intelligence.ui.utils.styles import load_dashboard_css, render_status_chip

st.set_page_config(page_title="Centro de monitoreo de tráfico", page_icon=":material/traffic:", layout="wide")
load_dashboard_css()

MONITORING_FRAME = PROJECT_ROOT / "data" / "samples" / "ui" / "assets" / "traffic_monitoring_urban_avenue.png"


@st.cache_data(max_entries=1)
def _load_state():
    return load_demo_dashboard()


def _export_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["origen", "categoría", "conteo"])
    for item in state.categories:
        writer.writerow(["SYNTHETIC_UI_DEMO", item.label, item.count])
    return buffer.getvalue().encode("utf-8-sig")


state = _load_state()
issues = validate_dashboard_state(state)
if issues:
    for issue in issues:
        st.error(issue, icon=":material/error:")
    st.stop()

title_col, action_col = st.columns([7, 4], vertical_alignment="bottom")
with title_col:
    st.title("Centro de monitoreo de tráfico")
    st.caption("Supervisión operativa del flujo vehicular y del estado del lote en tiempo casi real.")
    st.caption(
        f":material/location_on: {state.source.point_name}  ·  "
        f":material/videocam: Fuente: {state.source.label}  ·  "
        f":material/swap_horiz: Dirección: {state.source.configured_direction}"
    )
with action_col:
    st.markdown(render_status_chip("Modo demostración", "info"), unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
        if st.button("Revisar conteo", icon=":material/fact_check:", width="content"):
            st.switch_page("pages/traffic_review.py")
        st.download_button(
            "Exportar datos", data=_export_csv(), file_name="monitoreo_demo.csv",
            mime="text/csv", icon=":material/download:", type="primary", width="content",
        )

main_col, side_col = st.columns([9, 3], gap="medium")
with main_col:
    with st.container(border=True, gap="small"):
        header_left, header_right = st.columns([2, 3], vertical_alignment="center")
        header_left.markdown("**:material/videocam: Conteo automático simulado**")
        header_right.markdown(
            render_status_chip("Fuente simulada", "success") + " " +
            render_status_chip("Procesamiento activo", "success"),
            unsafe_allow_html=True,
        )
        frame = MONITORING_FRAME
        if frame.is_file():
            st.image(str(frame), width="stretch")
            st.caption("Fotograma urbano demostrativo con overlays preprocesados; no ejecuta YOLO ni ByteTrack.")
        else:
            st.warning("No se encontró el fotograma demostrativo.", icon=":material/image_not_supported:")
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            if st.button("Reproducir", icon=":material/play_arrow:", key="monitor_play", width="content"):
                st.session_state["traffic_monitor_state"] = DashboardOperationalState.PROCESSING_ACTIVE.value
            if st.button("Pausar", icon=":material/pause:", key="monitor_pause", width="content"):
                st.session_state["traffic_monitor_state"] = DashboardOperationalState.PROCESSING_PAUSED.value
            if st.button("Reiniciar", icon=":material/replay:", key="monitor_replay", width="content"):
                st.session_state["traffic_monitor_state"] = DashboardOperationalState.PROCESSING_ACTIVE.value
            st.caption(
                f"FPS {state.source.fps:.2f} · {state.source.resolution} · "
                f"Latencia {format_unit(state.source.latency_ms, 'ms')} · Simulación"
            )

    st.markdown("**Clasificación vehicular** · Total acumulado")
    category_cols = st.columns(5, gap="small")
    for column, category in zip(category_cols, state.categories):
        column.metric(category.label, f"{category.count:,}", f"{category.trend_percent:+.1f}%", border=True)

    direction_cols = st.columns(3, gap="small")
    for column, direction in zip(direction_cols, state.directions):
        column.metric(direction.label, f"{direction.count:,}", border=True)
    direction_cols[2].metric("Total", f"{state.direction_total:,}", border=True)

    with st.container(border=True, gap="small"):
        st.markdown("**Flujo vehicular** · Ambos sentidos (veh/min)")
        flow_df = pd.DataFrame(state.time_series).set_index("time")
        st.line_chart(
            flow_df, x_label="Hora", y_label="veh/min",
            color=["#1A56DB", "#CA8A04"], height=230,
        )

with side_col:
    with st.container(border=True, gap="small"):
        st.markdown("**Estado actual**")
        chip_col, lot_col = st.columns([3, 2], vertical_alignment="center")
        chip_col.markdown(render_status_chip(state.congestion.label, "warning"), unsafe_allow_html=True)
        lot_col.markdown(render_status_chip(state.review.label, "warning"), unsafe_allow_html=True)
        status_left, status_right = st.columns(2, gap="small")
        status_left.metric("Flujo", format_unit(state.metrics.current_flow_veh_min, "veh/min"), border=True)
        status_right.metric("Velocidad", format_unit(state.metrics.average_speed_kmh, "km/h"), border=True)
        status_left.metric("Ocupación est.", format_unit(state.metrics.visual_occupancy_percent, "%"), border=True)
        status_right.metric("En escena", f"{state.metrics.vehicles_in_scene:,}", border=True)
        st.metric("Total acumulado", f"{state.metrics.accumulated_total:,}", border=True)

    with st.container(border=True, gap="small"):
        st.markdown("**Reconocimiento de placas** :blue-badge[Experimental]")
        ocr_left, ocr_mid, ocr_right = st.columns(3, gap="small")
        ocr_left.metric("Detectadas", state.ocr.detected)
        ocr_mid.metric("Válidas", state.ocr.valid)
        ocr_right.metric("Pendientes", state.ocr.pending)
        doubtful_col, confidence_col = st.columns(2, gap="small")
        doubtful_col.metric("Dudosas", state.ocr.doubtful)
        confidence_col.metric("Confianza", format_unit(state.ocr.average_confidence_percent, "%"))
        if st.button("Ver lecturas", icon=":material/visibility:", width="stretch"):
            st.info("La pantalla completa de revisión OCR está pendiente de implementación.")

    with st.container(border=True, gap="small"):
        st.markdown("**Alertas recientes**")
        alert_df = pd.DataFrame([vars(item) for item in state.alerts]).rename(columns={
            "time": "Hora", "alert_type": "Tipo", "description": "Descripción",
            "level": "Nivel", "status": "Estado",
        })
        st.dataframe(
            alert_df[["Hora", "Tipo", "Nivel", "Estado"]],
            hide_index=True, height=145,
        )
        with st.expander("Ver descripción de alertas"):
            for alert in state.alerts:
                st.caption(f"**{alert.time} · {alert.alert_type}:** {alert.description}")
