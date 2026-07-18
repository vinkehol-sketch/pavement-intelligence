"""Revisión experimental y aislada de placas OCR sintéticas."""
from __future__ import annotations

import base64

import pandas as pd
import streamlit as st

from pavement_intelligence.domain.traffic.ocr_presentation import (
    PlateCorrectionRequest, PlateReviewStatus,
)
from pavement_intelligence.ui.utils.demo_data import PROJECT_ROOT
from pavement_intelligence.ui.utils.ocr_privacy import (
    confirm_correction, confirm_unchanged, export_reviewed_csv, initialize_ocr_session,
    load_demo_plate_readings, mark_status, mask_plate, render_plate_crop, save_review,
    select_reading, summarize_readings, toggle_plate_visibility,
)
from pavement_intelligence.ui.utils.styles import load_dashboard_css, render_status_chip

st.set_page_config(page_title="Lecturas de placas", page_icon=":material/license:", layout="wide")
load_dashboard_css()

REVIEWERS = ("jperez", "mrodriguez", "dvelasco")
REASONS = (
    "Seleccione un motivo...", "Carácter confundido por OCR", "Imagen obstruida / sucia",
    "Reflejo o iluminación deficiente", "Recorte incorrecto", "Lectura duplicada", "Otro",
)


@st.cache_data(max_entries=1)
def _load_readings():
    return load_demo_plate_readings()


def _protected_data_url(text: str) -> str:
    payload = base64.b64encode(render_plate_crop(text, protected=True)).decode("ascii")
    return f"data:image/png;base64,{payload}"


readings = _load_readings()
initialize_ocr_session(st.session_state, readings)

heading, actions = st.columns([7, 5], vertical_alignment="center")
with heading:
    st.title("Lecturas de placas")
    st.markdown(
        render_status_chip("Experimental", "info") + " " +
        render_status_chip("Datos sintéticos", "neutral"),
        unsafe_allow_html=True,
    )
with actions:
    with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
        if st.button("Volver al monitoreo", icon=":material/arrow_back:", width="content"):
            st.switch_page("pages/traffic_monitoring.py")
        st.download_button(
            "Exportar lecturas revisadas",
            data=export_reviewed_csv(readings, st.session_state["ocr_review_records"]),
            file_name="lecturas_ocr_sinteticas_revisadas.csv", mime="text/csv",
            icon=":material/download:", type="primary", width="content",
        )

st.info("Las lecturas requieren validación humana.", icon=":material/privacy_tip:")

summary = summarize_readings(readings, st.session_state["ocr_review_records"])
with st.container(horizontal=True):
    st.metric("Detectadas", summary.detected, border=True)
    st.metric("Válidas", summary.valid, border=True)
    st.metric("Dudosas", summary.doubtful, border=True)
    st.metric("Pendientes", summary.pending, border=True)
    st.metric("Ilegibles", summary.illegible, border=True)
    st.metric("Confianza media", f"{summary.average_confidence_percent:.0f}%", border=True)

with st.container(border=True, gap="small"):
    st.markdown("**Filtros**")
    f_date, f_status, f_category, f_direction, f_conf = st.columns(5)
    selected_date = f_date.date_input("Fecha", value=readings[0].timestamp.date(), key="ocr_filter_date")
    status_filter = f_status.selectbox("Estado", ["Todos", *[item.value for item in PlateReviewStatus]], key="ocr_filter_status")
    category_filter = f_category.selectbox("Categoría", ["Todas", *sorted({item.vehicle_category for item in readings})], key="ocr_filter_category")
    direction_filter = f_direction.selectbox("Sentido", ["Todos", *sorted({item.direction for item in readings})], key="ocr_filter_direction")
    min_confidence = f_conf.slider("Confianza mínima", 0, 100, 0, 5, key="ocr_filter_confidence")
    search = st.text_input("Buscar lectura", placeholder="reading_id, track_id o placa anonimizada", key="ocr_filter_search")
    st.session_state["ocr_filters"] = {
        "date": selected_date.isoformat(), "status": status_filter,
        "category": category_filter, "direction": direction_filter,
        "minimum_confidence": min_confidence, "search": search,
    }

filtered = [item for item in readings if item.timestamp.date() == selected_date]
if status_filter != "Todos":
    filtered = [item for item in filtered if item.status.value == status_filter]
if category_filter != "Todas":
    filtered = [item for item in filtered if item.vehicle_category == category_filter]
if direction_filter != "Todos":
    filtered = [item for item in filtered if item.direction == direction_filter]
filtered = [item for item in filtered if item.confidence * 100 >= min_confidence]
needle = search.strip().upper()
if needle:
    filtered = [item for item in filtered if needle in f"{item.reading_id} {item.track_id} {item.masked_text}".upper()]

left, right = st.columns([8, 4], gap="medium")
with left:
    with st.container(border=True, gap="small"):
        st.markdown(f"**Lecturas protegidas** · {len(filtered)} registros")
        if filtered:
            selection_ids = [item.reading_id for item in filtered]
            current = st.session_state.get("ocr_selected_reading_id")
            selected_index = selection_ids.index(current) if current in selection_ids else 0
            chosen = st.selectbox("Revisar lectura", selection_ids, index=selected_index, key="ocr_selected_widget_id")
            select_reading(st.session_state, chosen)
            table = pd.DataFrame([{
                "Hora": item.timestamp.strftime("%H:%M:%S"), "Lectura ID": item.reading_id,
                "Track ID": item.track_id, "Miniatura protegida": _protected_data_url(item.original_text),
                "Placa anonimizada": item.masked_text, "Confianza": item.confidence,
                "Categoría": item.vehicle_category, "Sentido": item.direction,
                "Estado": st.session_state["ocr_review_records"].get(item.reading_id, item).status.value,
            } for item in filtered])
            st.dataframe(
                table, hide_index=True, height=390,
                column_config={
                    "Miniatura protegida": st.column_config.ImageColumn("Miniatura"),
                    "Confianza": st.column_config.ProgressColumn("Confianza", min_value=0, max_value=1, format="percent"),
                },
            )
        else:
            chosen = None
            st.warning("No hay lecturas para los filtros seleccionados.")

with right:
    with st.container(border=True, gap="small"):
        st.markdown("**Revisión manual**")
        selected_id = st.session_state.get("ocr_selected_reading_id") if chosen else None
        selected = next((item for item in readings if item.reading_id == selected_id), None)
        if selected is None:
            st.info("Seleccione una lectura para revisar.")
        else:
            frame_path = PROJECT_ROOT / selected.frame_image_path
            if frame_path.is_file():
                st.image(str(frame_path), caption="Fotograma sintético de referencia", width="stretch")
            reviewer = st.selectbox("Revisor", REVIEWERS, key="ocr_reviewer")
            visible = st.session_state.get("ocr_visible_reading_id") == selected.reading_id
            if st.button(
                "Ocultar placa" if visible else "Mostrar placa",
                icon=":material/visibility_off:" if visible else ":material/visibility:",
                key="ocr_toggle_visibility", width="stretch",
            ):
                toggle_plate_visibility(st.session_state, selected.reading_id, reviewer)
                st.rerun()
            visible = st.session_state.get("ocr_visible_reading_id") == selected.reading_id
            st.image(
                render_plate_crop(selected.original_text, protected=not visible),
                caption="Recorte legible auditado" if visible else "Recorte protegido",
                width="stretch",
            )
            shown_text = selected.original_text if visible else selected.masked_text
            st.text_input("Lectura original OCR (inmutable)", value=shown_text, disabled=True, key=f"ocr_original_{selected.reading_id}")
            st.caption(f"Confianza: {selected.confidence:.0%} · Alternativas: {', '.join(selected.suggested_alternatives) or 'Ninguna'}")
            corrected = st.text_input("Lectura corregida", value=selected.original_text, key=f"ocr_corrected_{selected.reading_id}")
            reason = st.selectbox("Motivo de corrección", REASONS, key=f"ocr_reason_{selected.reading_id}")
            notes = st.text_area("Observaciones", key=f"ocr_notes_{selected.reading_id}")

            action_a, action_b = st.columns(2)
            if action_a.button("Confirmar sin cambios", key="ocr_confirm_unchanged", width="stretch"):
                try:
                    save_review(st.session_state, confirm_unchanged(selected, reviewer, notes))
                    st.success("Lectura confirmada sin cambios.")
                except ValueError as exc:
                    st.error(str(exc))
            if action_b.button("Guardar corrección", type="primary", key="ocr_confirm_correction", width="stretch"):
                try:
                    request = PlateCorrectionRequest(selected.reading_id, corrected, "" if reason == REASONS[0] else reason, notes, reviewer)
                    save_review(st.session_state, confirm_correction(selected, request))
                    st.success("Corrección guardada y confirmada.")
                except ValueError as exc:
                    st.error(str(exc))
            state_a, state_b = st.columns(2)
            if state_a.button("Marcar como dudosa", key="ocr_mark_doubtful", width="stretch"):
                save_review(st.session_state, mark_status(selected, PlateReviewStatus.DOUBTFUL, reviewer, notes))
                st.warning("Lectura marcada como dudosa.")
            if state_b.button("Marcar como ilegible", key="ocr_mark_illegible", width="stretch"):
                save_review(st.session_state, mark_status(selected, PlateReviewStatus.ILLEGIBLE, reviewer, notes))
                st.warning("Lectura marcada como ilegible.")
            with st.expander("Historial y auditoría"):
                review = st.session_state["ocr_review_records"].get(selected.reading_id)
                if review:
                    st.write(f"Estado: {review.status.value} · Revisor: {review.reviewed_by} · {review.reviewed_at.isoformat()}")
                reveal_events = [item for item in st.session_state["ocr_reveal_audit"] if item.reading_id == selected.reading_id]
                for event in reveal_events:
                    st.caption(f"{event.action} · {event.reviewed_by} · {event.revealed_at.isoformat()}")
