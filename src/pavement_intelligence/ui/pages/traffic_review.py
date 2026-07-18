"""
Página de Revisión del Aforo Automático — Pavement Intelligence
===============================================================
Permite revisar, corregir y aprobar manualmente los eventos del contador
vial antes de consolidarlos para el aforo técnico.
"""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import uuid
from pathlib import Path
from typing import Any, Mapping
import pandas as pd
import streamlit as st

from pavement_intelligence.integration import (
    TrafficEventContractError,
    adapt_traffic_event_for_review,
    build_traffic_event_batch,
)
from pavement_intelligence.integration.traffic_event_adapter import REQUIRED_EVENT_FIELDS
from pavement_intelligence.utils.catalog_loader import get_vehicle_categories, load_yaml_catalog_cached

_VEHICLE_CATALOG_PATH = Path(__file__).resolve().parents[2] / "config" / "vehicle_catalog.yaml"
CATEGORIAS_ABC = [
    item["id"] for item in get_vehicle_categories(load_yaml_catalog_cached(str(_VEHICLE_CATALOG_PATH)))
]
IMMUTABLE_EVENT_FIELDS = frozenset(REQUIRED_EVENT_FIELDS)
REVIEW_FIELDS = frozenset({
    "validation_status", "corrected_category", "correction_reason", "reviewed",
    "reviewed_by", "reviewed_at", "include_in_final_count",
})

# Mapeo de nombres para visualización en la UI
CATEGORIA_MAP = {
    "AUTO": "Automóvil",
    "MOTO": "Motocicleta",
    "BUS": "Autobús",
    "CAMION": "Camión no confirmado",
    "DESCONOCIDO": "Requiere revisión"
}

# ── 15 Eventos Demostrativos Sintéticos ───────────────────────────────────────
EVENTOS_DEMO = [
    {"event_id": "evt_1712403982000_1", "track_id": 1, "original_class": "car", "category": "AUTO", "confidence": 0.9250, "frame_number": 120, "video_second": 5.0, "direction": 1, "centroid_x": 150.0, "centroid_y": 360.0, "source": "car-detection.mp4", "processing_date": "2026-07-17T16:00:00Z"},
    {"event_id": "evt_1712403982000_2", "track_id": 2, "original_class": "motorcycle", "category": "MOTO", "confidence": 0.8810, "frame_number": 240, "video_second": 10.0, "direction": -1, "centroid_x": 180.0, "centroid_y": 360.0, "source": "car-detection.mp4", "processing_date": "2026-07-17T16:00:00Z"},
    {"event_id": "evt_1712403982000_3", "track_id": 3, "original_class": "bus", "category": "BUS", "confidence": 0.9420, "frame_number": 360, "video_second": 15.0, "direction": 1, "centroid_x": 220.0, "centroid_y": 360.0, "source": "car-detection.mp4", "processing_date": "2026-07-17T16:00:00Z"},
    {"event_id": "evt_1712403982000_4", "track_id": 4, "original_class": "truck", "category": "CAMION", "confidence": 0.9100, "frame_number": 480, "video_second": 20.0, "direction": 1, "centroid_x": 310.0, "centroid_y": 360.0, "source": "car-detection.mp4", "processing_date": "2026-07-17T16:00:00Z"},
    {"event_id": "evt_1712403982000_5", "track_id": 5, "original_class": "car", "category": "AUTO", "confidence": 0.4500, "frame_number": 600, "video_second": 25.0, "direction": -1, "centroid_x": 140.0, "centroid_y": 360.0, "source": "car-detection.mp4", "processing_date": "2026-07-17T16:00:00Z"},  # Baja confianza
    {"event_id": "evt_1712403982000_6", "track_id": 6, "original_class": "truck", "category": "CAMION", "confidence": 0.8900, "frame_number": 720, "video_second": 30.0, "direction": -1, "centroid_x": 305.0, "centroid_y": 360.0, "source": "car-detection.mp4", "processing_date": "2026-07-17T16:00:00Z"},
    {"event_id": "evt_1712403982000_7", "track_id": 7, "original_class": "car", "category": "AUTO", "confidence": 0.9320, "frame_number": 840, "video_second": 35.0, "direction": 1, "centroid_x": 155.0, "centroid_y": 360.0, "source": "car-detection.mp4", "processing_date": "2026-07-17T16:00:00Z"},
    {"event_id": "evt_1712403982000_8", "track_id": 8, "original_class": "car", "category": "AUTO", "confidence": 0.9510, "frame_number": 960, "video_second": 40.0, "direction": 1, "centroid_x": 162.0, "centroid_y": 360.0, "source": "car-detection.mp4", "processing_date": "2026-07-17T16:00:00Z"},
    {"event_id": "evt_1712403982000_9", "track_id": 9, "original_class": "bus", "category": "BUS", "confidence": 0.9150, "frame_number": 1080, "video_second": 45.0, "direction": -1, "centroid_x": 225.0, "centroid_y": 360.0, "source": "car-detection.mp4", "processing_date": "2026-07-17T16:00:00Z"},
    {"event_id": "evt_1712403982000_10", "track_id": 10, "original_class": "truck", "category": "CAMION", "confidence": 0.5200, "frame_number": 1200, "video_second": 50.0, "direction": 1, "centroid_x": 312.0, "centroid_y": 360.0, "source": "car-detection.mp4", "processing_date": "2026-07-17T16:00:00Z"}, # Camión + baja confianza
]
for _demo_event in EVENTOS_DEMO:
    _demo_event["data_origin"] = "SINTETICO_DEMOSTRATIVO"

def initialize_reviewed_events(raw_events: list[Any]) -> list[dict[str, Any]]:
    """Adapta eventos crudos exclusivamente mediante el contrato oficial."""
    reviewed_list = []
    for event in raw_events:
        reviewed = adapt_traffic_event_for_review(event)
        if reviewed["category"] in CATEGORIAS_ABC:
            reviewed["corrected_category"] = reviewed["category"]
        reviewed_list.append(reviewed)
    return reviewed_list


def prepare_review_batch(payload: Any) -> tuple[list[dict], list[dict], dict]:
    """Valida un lote completo sin modificar estado; falla de forma atómica."""
    metadata: dict[str, Any] = {}
    if isinstance(payload, Mapping):
        if "events" not in payload:
            raise TrafficEventContractError("El JSON de lote debe contener 'events'.")
        metadata = dict(payload.get("metadata") or {})
        batch = build_traffic_event_batch(payload["events"], metadata)
        reviewed = initialize_reviewed_events(batch["events"])
        metadata = batch["metadata"]
    elif isinstance(payload, list):
        reviewed = initialize_reviewed_events(payload)
    else:
        raise TrafficEventContractError("El lote debe ser una lista de eventos o un objeto con metadata/events.")

    event_ids = [record["event_id"] for record in reviewed]
    if len(event_ids) != len(set(event_ids)):
        raise TrafficEventContractError("El lote contiene event_id duplicados.")
    raw = [{field: record[field] for field in REQUIRED_EVENT_FIELDS} for record in reviewed]
    return raw, reviewed, metadata


def replace_review_session(
    session: dict[str, Any], payload: Any, *, is_synthetic: bool,
    source_fingerprint: str | None = None,
) -> None:
    """Reemplaza el lote sólo después de validar todo su contenido."""
    raw, reviewed, metadata = prepare_review_batch(payload)
    session["vision_events_raw"] = raw
    session["vision_events_reviewed"] = reviewed
    session["vision_batch_metadata"] = metadata
    session["traffic_counts_corrected"] = {}
    session["traffic_review_approved"] = False
    session["is_synthetic_review"] = is_synthetic
    session["traffic_review_source_fingerprint"] = source_fingerprint


def invalidate_review_approval(session: dict[str, Any]) -> None:
    session["traffic_review_approved"] = False
    session["traffic_counts_corrected"] = {}
    if "tpda_input_from_review" in session:
        session["tpda_input_from_review"] = None


def apply_review_update(
    session: dict[str, Any], event_id: str, changes: Mapping[str, Any], reviewer: str,
) -> None:
    """Aplica sólo campos revisables e invalida cualquier aprobación anterior."""
    if not reviewer.strip():
        raise ValueError("Toda revisión requiere un responsable.")
    forbidden = set(changes) - REVIEW_FIELDS
    if forbidden:
        raise ValueError(f"No se pueden modificar campos técnicos: {sorted(forbidden)}")
    reviewed_events = session["vision_events_reviewed"]
    event = next((item for item in reviewed_events if item["event_id"] == event_id), None)
    if event is None:
        raise KeyError(event_id)
    event.update(dict(changes))
    event["reviewed"] = True
    event["reviewed_by"] = reviewer.strip()
    event["reviewed_at"] = datetime.datetime.now().isoformat()
    invalidate_review_approval(session)


def create_manual_review_event(
    category: str, direction: int, video_second: float, reason: str, reviewer: str,
    *, now: str | None = None, manual_event_id: str | None = None,
) -> dict[str, Any]:
    """Crea un registro manual fuera del namespace de IDs ByteTrack."""
    if category not in CATEGORIAS_ABC:
        raise ValueError("Categoría manual no admitida por vehicle_catalog.yaml.")
    if direction not in {-1, 1}:
        raise ValueError("La dirección manual debe ser 1 o -1.")
    if not reason.strip() or not reviewer.strip():
        raise ValueError("Los eventos manuales requieren justificación y responsable.")
    timestamp = now or datetime.datetime.now().isoformat()
    identifier = manual_event_id or f"manual:{uuid.uuid4()}"
    return {
        "event_id": identifier,
        "manual_event_id": identifier,
        "track_id": None,
        "original_class": None,
        "category": None,
        "confidence": None,
        "frame_number": None,
        "video_second": float(video_second),
        "direction": direction,
        "centroid_x": None,
        "centroid_y": None,
        "source": "manual_review",
        "processing_date": timestamp,
        "data_origin": "manual",
        "validation_status": "agregado_manualmente",
        "corrected_category": category,
        "correction_reason": reason.strip(),
        "reviewed": True,
        "reviewed_by": reviewer.strip(),
        "reviewed_at": timestamp,
        "include_in_final_count": True,
    }


def parse_uploaded_review_data(filename: str, content: bytes) -> Any:
    """Parsea CSV o JSON sin tocar session_state."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        return json.loads(content.decode("utf-8-sig"))
    if suffix == ".csv":
        return pd.read_csv(io.BytesIO(content), encoding="utf-8-sig").to_dict(orient="records")
    raise TrafficEventContractError("Formato no soportado; use CSV o JSON.")


def review_payload_fingerprint(payload: list[Any], namespace: str) -> str:
    serializable = [item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in payload]
    content = json.dumps(serializable, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{namespace}:{hashlib.sha256(content).hexdigest()}"

def calculate_consolidated_transit(reviewed_events: list[dict]) -> tuple[dict[str, int], dict[str, int], int, int]:
    """Calcula los totales de tránsito automáticos y corregidos."""
    counts_auto = {cat: 0 for cat in CATEGORIAS_ABC}
    counts_final = {cat: 0 for cat in CATEGORIAS_ABC}
    
    total_auto = 0
    total_final = 0
    
    for ev in reviewed_events:
        # Automático
        cat_auto = ev.get("category")
        if cat_auto in counts_auto:
            counts_auto[cat_auto] += 1
            total_auto += 1
            
        # Final
        if ev.get("include_in_final_count"):
            cat_corr = ev.get("corrected_category")
            if cat_corr in counts_final:
                counts_final[cat_corr] += 1
                total_final += 1
                
    return counts_auto, counts_final, total_auto, total_final

def validate_approval_criteria(
    reviewed_events: list[dict], 
    is_synthetic: bool, 
    user_accepted_synthetic: bool,
    umbral_confianza_alert: float = 55.0
) -> tuple[bool, list[str]]:
    """Valida los criterios técnicos de aprobación del aforo."""
    warnings_approval = []
    
    # Contadores de estados
    status_counts = {"sin_revisar": 0, "aceptado": 0, "corregido": 0, "descartado": 0, "agregado_manualmente": 0, "requiere_revision": 0}
    for ev in reviewed_events:
        val_status = ev.get("validation_status", "sin_revisar")
        status_counts[val_status] = status_counts.get(val_status, 0) + 1

    # Criterio 1: Ningún evento sin revisar o en requiere_revision
    # Nota: También revisamos si hay eventos de baja confianza sin revisar
    hay_pendientes = False
    for ev in reviewed_events:
        val_status = ev.get("validation_status", "sin_revisar")
        if val_status in ["sin_revisar", "requiere_revision"]:
            hay_pendientes = True

    if hay_pendientes:
        warnings_approval.append("Existen eventos en estado 'sin_revisar' o 'requiere_revision' pendientes de auditoría.")

    # Criterio 2: Ningún camión sin confirmar
    hay_camion_sin_confirmar = any(
        ev.get("category") == "CAMION" and ev.get("corrected_category") not in CATEGORIAS_ABC
        for ev in reviewed_events if ev.get("include_in_final_count")
    )
    if hay_camion_sin_confirmar:
        warnings_approval.append("Existen vehículos 'Camión no confirmado' (truck) pendientes de clasificación vial específica (C2, C3, etc.).")

    # Criterio 3: Ninguna categoría DESCONOCIDO
    hay_desconocidos = any(
        ev.get("category") == "DESCONOCIDO" and ev.get("corrected_category") not in CATEGORIAS_ABC
        for ev in reviewed_events if ev.get("include_in_final_count")
    )
    if hay_desconocidos:
        warnings_approval.append("Existen vehículos con categoría 'DESCONOCIDO' pendientes de clasificar.")

    categorias_finales_invalidas = any(
        ev.get("include_in_final_count")
        and ev.get("corrected_category") not in CATEGORIAS_ABC
        for ev in reviewed_events
    )
    if categorias_finales_invalidas:
        warnings_approval.append(
            "Existen eventos incluidos sin una categoría vial final válida."
        )

    # Criterio 4: Justificaciones completas
    correcciones_completas = True
    for ev in reviewed_events:
        val_status = ev.get("validation_status", "sin_revisar")
        reason = ev.get("correction_reason", "")
        reviewer = ev.get("reviewed_by", "")
        category_changed = (
            ev.get("corrected_category") in CATEGORIAS_ABC
            and ev.get("corrected_category") != ev.get("category")
            and ev.get("data_origin") != "manual"
        )
        if val_status in ["corregido", "descartado"] or category_changed:
            if not str(reason).strip() or not str(reviewer).strip():
                correcciones_completas = False
        if val_status == "corregido" and ev.get("corrected_category") not in CATEGORIAS_ABC:
            correcciones_completas = False

    if not correcciones_completas:
        warnings_approval.append(
            "Existen correcciones o descartes sin categoría válida, justificación o revisor."
        )

    manual_invalido = any(
        ev.get("data_origin") == "manual" and (
            ev.get("track_id") is not None
            or not str(ev.get("event_id", "")).startswith("manual:")
            or ev.get("corrected_category") not in CATEGORIAS_ABC
            or not str(ev.get("correction_reason", "")).strip()
            or not str(ev.get("reviewed_by", "")).strip()
            or not ev.get("reviewed_at")
        )
        for ev in reviewed_events if ev.get("include_in_final_count")
    )
    if manual_invalido:
        warnings_approval.append("Existen eventos manuales incompletos o que usan un identificador de tracker.")

    # Criterio 5: Al menos un evento incluido en conteo final
    _, _, _, total_final = calculate_consolidated_transit(reviewed_events)
    if total_final <= 0:
        warnings_approval.append("El conteo final de vehículos es cero; se requiere al menos un vehículo incluido.")

    # Criterio 6: Datos sintéticos requieren aceptación
    if is_synthetic and not user_accepted_synthetic:
        warnings_approval.append("Debe aceptar y confirmar el entendimiento de que se están utilizando datos sintéticos demostrativos.")

    approval_enabled = len(warnings_approval) == 0
    return approval_enabled, warnings_approval

def render() -> None:
    st.set_page_config(page_title="Revisión del Aforo Automático", layout="wide")
    st.title("🔍 Revisión del Aforo Automático")
    st.markdown(
        "Audite los cruces detectados por la visión computacional YOLO antes de guardarlos. "
        "La revisión manual es obligatoria y el resultado no pasará automáticamente a los cálculos de diseño."
    )

    # ── Inicializar estados en session_state ──────────────────────────────────
    st.session_state.setdefault("vision_events_raw", [])
    st.session_state.setdefault("vision_events_reviewed", [])
    st.session_state.setdefault("vision_batch_metadata", {})
    st.session_state.setdefault("traffic_counts_corrected", {})
    st.session_state.setdefault("traffic_review_approved", False)
    st.session_state.setdefault("is_synthetic_review", False)
    st.session_state.setdefault("traffic_review_source_fingerprint", None)

    counter_events = list(st.session_state.get("events") or [])
    current_source = st.session_state.get("traffic_review_source_fingerprint")
    counter_fingerprint = review_payload_fingerprint(counter_events, "counter") if counter_events else None
    should_load_counter = bool(counter_events) and (
        current_source is None
        or (str(current_source).startswith("counter:") and current_source != counter_fingerprint)
    )
    if should_load_counter:
        try:
            replace_review_session(
                st.session_state, counter_events, is_synthetic=False,
                source_fingerprint=counter_fingerprint,
            )
        except TrafficEventContractError as exc:
            st.error(f"Los eventos del contador no cumplen el contrato: {exc}")

    if st.session_state["vision_events_raw"] and not st.session_state["vision_events_reviewed"]:
        try:
            st.session_state["vision_events_reviewed"] = initialize_reviewed_events(
                st.session_state["vision_events_raw"]
            )
        except TrafficEventContractError as exc:
            st.error(f"El lote activo no cumple el contrato: {exc}")

    # ── Cargar fuentes de datos ───────────────────────────────────────────────
    st.sidebar.header("📂 Fuente de Datos")
    
    if st.sidebar.button("📥 Cargar Caso Demostrativo (Sintético)", use_container_width=True):
        replace_review_session(
            st.session_state, EVENTOS_DEMO, is_synthetic=True,
            source_fingerprint="synthetic-demo-v1",
        )
        st.success("✅ Caso demostrativo sintético cargado.")
        st.rerun()

    uploaded_file = st.sidebar.file_uploader("Subir CSV o JSON de cruces del contador", type=["csv", "json"])
    if uploaded_file is not None:
        content = uploaded_file.getvalue()
        fingerprint = f"upload:{hashlib.sha256(content).hexdigest()}"
        is_new_upload = fingerprint != st.session_state.get("traffic_review_source_fingerprint")
    else:
        is_new_upload = False
    if uploaded_file is not None and is_new_upload:
        try:
            payload = parse_uploaded_review_data(uploaded_file.name, content)
            replace_review_session(
                st.session_state, payload, is_synthetic=False,
                source_fingerprint=fingerprint,
            )
            st.sidebar.success("✅ Lote validado y cargado.")
            st.rerun()
        except (TrafficEventContractError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            st.sidebar.error(f"No se cargó el lote; el estado anterior permanece intacto: {exc}")

    reviewed_events = st.session_state["vision_events_reviewed"]

    if not reviewed_events:
        st.info(
            "📋 **Sin datos cargados.**\n\n"
            "Para comenzar el flujo de revisión, por favor:\n"
            "1. Procese un video en el módulo **🎥 Análisis de Tráfico por Video**.\n"
            "2. Cargue el caso sintético con el botón **Cargar Caso Demostrativo (Sintético)** de la barra lateral.\n"
            "3. O suba un archivo CSV de cruces exportado previamente por el sistema."
        )
        st.stop()

    if st.session_state["is_synthetic_review"]:
        st.error(
            "🔴 **AVISO:** Datos sintéticos de demostración. No representan mediciones "
            "reales y no son válidos para diseño oficial.",
            icon="🚨"
        )

    batch_metadata = st.session_state.get("vision_batch_metadata", {})
    model_label = batch_metadata.get("model_name", "yolov8n.pt")
    line_label = batch_metadata.get("line_y", 360)
    st.markdown(
        f"""
        <div style="background-color:#1e2130; padding: 0.8rem; border-radius: 6px; border-left: 4px solid #4A90D9; margin-bottom: 1rem;">
            <strong>⚙️ Configuración del Pipeline de Medición Registrada:</strong><br>
            <span style="font-size: 0.85rem; color: #ccc;">
                • Modelo YOLO: <code>{model_label}</code> | 
                • Línea Virtual de Aforo: <code>y = {line_label}</code> (Línea del MVP provisional) | 
                • Calibraciones de Línea y=320 e y=300 descartadas.
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Parámetros de Revisión")
    umbral_confianza = st.sidebar.slider(
        "Umbral de Confianza de Alerta (%):",
        min_value=10,
        max_value=100,
        value=55,
        step=5,
        help="Los eventos con confianza menor a este umbral se marcarán para revisión obligatoria."
    )
    
    min_just_len = st.sidebar.number_input(
        "Recomendación de longitud de justificación (caracteres):",
        min_value=0,
        max_value=100,
        value=10,
        help="Longitud de caracteres recomendada para justificar correcciones/descartes."
    )

    st.sidebar.header("🔍 Filtros de Visualización")
    filter_status = st.sidebar.selectbox(
        "Filtrar por Estado:",
        options=["Todos", "sin_revisar", "aceptado", "corregido", "descartado", "agregado_manualmente", "requiere_revision"]
    )
    filter_dir = st.sidebar.selectbox(
        "Filtrar por Sentido:",
        options=["Todos", "Ascendente (1)", "Descendente (-1)"]
    )
    
    only_trucks = st.sidebar.checkbox("Solo camiones no confirmados (truck)")
    only_low_conf = st.sidebar.checkbox("Solo baja confianza")
    only_pending = st.sidebar.checkbox("Solo pendientes de revisión")

    # Agregar vehículo omitido
    with st.expander("➕ Registrar Vehículo Omitido (Inserción Manual)"):
        with st.form("form_manual_add"):
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                m_cat = st.selectbox("Categoría ABC:", options=CATEGORIAS_ABC)
                m_dir = st.selectbox("Sentido:", options=["Ascendente (1)", "Descendente (-1)"], index=0)
            with col_m2:
                m_sec = st.number_input("Segundo aproximado del video:", min_value=0.0, value=0.0, step=1.0)
                m_reason = st.text_input("Justificación de la omisión:", value="Vehículo omitido por oclusión visual.")
                m_reviewer = st.text_input("Responsable de la revisión:", value="Operador")
            
            m_submitted = st.form_submit_button("✅ Agregar Registro Manual")
            if m_submitted:
                m_dir_val = 1 if "Ascendente" in m_dir else -1
                try:
                    nuevo_evt = create_manual_review_event(
                        m_cat, m_dir_val, m_sec, m_reason, m_reviewer
                    )
                    st.session_state["vision_events_reviewed"].append(nuevo_evt)
                    invalidate_review_approval(st.session_state)
                    st.success("✅ Vehículo omitido registrado manualmente.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    # Aplicar filtros
    filtered_events = []
    for ev in reviewed_events:
        if filter_status != "Todos" and ev["validation_status"] != filter_status:
            continue
        if filter_dir != "Todos":
            dir_val = 1 if "Ascendente" in filter_dir else -1
            if ev["direction"] != dir_val:
                continue
        if only_trucks and ev.get("original_class") != "truck":
            continue
        confidence = ev.get("confidence")
        if only_low_conf and confidence is not None and confidence * 100 >= umbral_confianza:
            continue
        if only_pending and ev["reviewed"]:
            continue
            
        filtered_events.append(ev)

    st.subheader("📋 Tabla de Auditoría de Eventos")
    
    data_list = []
    for idx, ev in enumerate(filtered_events):
        conf_pct = ev["confidence"] * 100.0 if ev.get("confidence") is not None else None
        prelim_cat = CATEGORIA_MAP.get(ev.get("category"), ev.get("category") or "Registro manual")
        if ev["original_class"] == "truck":
            prelim_cat = "Camión no confirmado"
            
        data_list.append({
            "Indice": idx,
            "ID Evento": ev["event_id"],
            "Track ID": ev["track_id"],
            "Clase IA": ev["original_class"],
            "Cat. Preliminar (IA)": prelim_cat,
            "Confianza (%)": round(conf_pct, 1),
            "Sentido": "Ascendente (1)" if ev["direction"] == 1 else "Descendente (-1)",
            "Cat. Vial Confirmada (ABC)": ev["corrected_category"] or "",
            "Estado": ev["validation_status"],
            "Justificación (Corrección/Descarte)": ev["correction_reason"],
            "Responsable": ev.get("reviewed_by") or ""
        })

    df_editor = pd.DataFrame(data_list)
    
    if df_editor.empty:
        st.info("No se encontraron registros con los filtros seleccionados.")
        edited_df = df_editor
    else:
        edited_df = st.data_editor(
            df_editor,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Indice": st.column_config.NumberColumn("Indice", disabled=True),
                "ID Evento": st.column_config.TextColumn("ID Evento", disabled=True),
                "Track ID": st.column_config.NumberColumn("Track ID", disabled=True),
                "Clase IA": st.column_config.TextColumn("Clase IA", disabled=True),
                "Cat. Preliminar (IA)": st.column_config.TextColumn("Cat. Preliminar (IA)", disabled=True),
                "Confianza (%)": st.column_config.NumberColumn("Confianza (%)", disabled=True, format="%.1f%%"),
                "Sentido": st.column_config.TextColumn("Sentido", disabled=True),
                "Cat. Vial Confirmada (ABC)": st.column_config.SelectboxColumn(
                    "Cat. Vial Confirmada (ABC)",
                    options=[""] + CATEGORIAS_ABC
                ),
                "Estado": st.column_config.SelectboxColumn(
                    "Estado",
                    options=["sin_revisar", "aceptado", "corregido", "descartado", "requiere_revision", "agregado_manualmente"]
                ),
                "Justificación (Corrección/Descarte)": st.column_config.TextColumn("Justificación (Corrección/Descarte)"),
                "Responsable": st.column_config.TextColumn("Responsable", disabled=True)
            }
        )

    if not df_editor.empty and st.button("💾 Guardar Cambios de Tabla"):
        for _, row in edited_df.iterrows():
            orig_idx = int(row["Indice"])
            target_event = filtered_events[orig_idx]
            real_idx = next(i for i, ev in enumerate(reviewed_events) if ev["event_id"] == target_event["event_id"])
            
            new_cat = row["Cat. Vial Confirmada (ABC)"] or None
            new_status = row["Estado"]
            new_reason = row["Justificación (Corrección/Descarte)"]

            event_ref = reviewed_events[real_idx]
            if (event_ref["corrected_category"] != new_cat or 
                event_ref["validation_status"] != new_status or 
                event_ref["correction_reason"] != new_reason):
                
                apply_review_update(
                    st.session_state,
                    event_ref["event_id"],
                    {
                        "corrected_category": new_cat,
                        "validation_status": new_status,
                        "correction_reason": str(new_reason),
                        "include_in_final_count": new_status != "descartado",
                    },
                    "Auditor",
                )

        st.success("✅ Cambios de auditoría guardados en sesión.")
        st.rerun()

    # Vista Móvil
    st.markdown("---")
    st.subheader("📱 Vista Móvil (Auditoría Rápida por Tarjeta)")
    with st.expander("📱 Mostrar Tarjetas de Auditoría Móvil"):
        for ev in filtered_events:
            event_id = ev["event_id"]
            track_id = ev["track_id"]
            badge_color = {
                "sin_revisar": "grey", "aceptado": "green", "corregido": "blue",
                "descartado": "red", "agregado_manualmente": "orange", "requiere_revision": "yellow"
            }.get(ev["validation_status"], "grey")
            confidence_label = f"{ev['confidence']*100:.1f}%" if ev.get("confidence") is not None else "N/A"
            
            col_t1, col_t2 = st.columns([3, 1])
            with col_t1:
                st.markdown(
                    f"**ID:** `{event_id}` (Track `{track_id}`) | **Clase IA:** `{ev['original_class']}` | "
                    f"**Confianza:** `{confidence_label}` | **Sentido:** `{ev['direction']}`"
                )
                st.markdown(
                    f"• **Cat. Confirmada:** `{ev['corrected_category']}` | "
                    f"• **Estado:** <span style='color:{badge_color}; font-weight:bold;'>{ev['validation_status'].upper()}</span> | "
                    f"• **Revisor:** `{ev.get('reviewed_by') or 'N/A'}`",
                    unsafe_allow_html=True
                )
                if ev["correction_reason"]:
                    st.caption(f"✍️ Nota: {ev['correction_reason']}")
            
            with col_t2:
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    if st.button("👍 Aceptar", key=f"btn_ok_{event_id}"):
                        real_idx = next(i for i, e in enumerate(reviewed_events) if e["event_id"] == event_id)
                        if reviewed_events[real_idx]["category"] == "CAMION":
                            st.error("No se puede aceptar camiones sin clasificación específica.")
                        else:
                            accepted_category = (
                                reviewed_events[real_idx]["corrected_category"]
                                if reviewed_events[real_idx].get("data_origin") == "manual"
                                else reviewed_events[real_idx]["category"]
                            )
                            apply_review_update(
                                st.session_state,
                                event_id,
                                {
                                    "validation_status": "aceptado",
                                    "corrected_category": accepted_category,
                                    "include_in_final_count": True,
                                },
                                "Auditor Móvil",
                            )
                            st.rerun()
                with sub_col2:
                    if st.button("👎 Descartar", key=f"btn_ko_{event_id}"):
                        real_idx = next(i for i, e in enumerate(reviewed_events) if e["event_id"] == event_id)
                        apply_review_update(
                            st.session_state,
                            event_id,
                            {
                                "validation_status": "descartado",
                                "include_in_final_count": False,
                                "correction_reason": "Falso positivo descartado en vista móvil.",
                            },
                            "Auditor Móvil",
                        )
                        st.rerun()
            st.markdown("<hr style='margin:0.5rem 0; border:0; border-top:1px solid #333;'>", unsafe_allow_html=True)

    # Resumen y Totales
    counts_auto, counts_final, total_auto, total_final = calculate_consolidated_transit(reviewed_events)

    if review_approved:
        st.markdown("---")
        st.subheader("📈 Resumen de Tránsito Consolidado")
        
        summary_rows = []
        for cat in CATEGORIAS_ABC:
            auto_val = counts_auto[cat]
            final_val = counts_final[cat]
            diff = final_val - auto_val
            diff_pct = (diff / auto_val * 100) if auto_val > 0 else (100.0 if diff > 0 else 0.0)
            
            summary_rows.append({
                "Categoría ABC": cat,
                "Conteo IA (Preliminar)": auto_val,
                "Conteo Corregido (Final)": final_val,
                "Diferencia Absoluta": f"{diff:+d}" if diff != 0 else "0",
                "Porcentaje Cambio": f"{diff_pct:+.1f}%" if diff != 0 else "0.0%"
            })

        df_summary = pd.DataFrame(summary_rows)
        st.dataframe(df_summary, use_container_width=True, hide_index=True)

    # Tarjetas de Estado
    st.markdown("---")
    st.subheader("📊 Métricas de Control del Aforo")
    
    status_counts = {"sin_revisar": 0, "aceptado": 0, "corregido": 0, "descartado": 0, "agregado_manualmente": 0, "requiere_revision": 0}
    for ev in reviewed_events:
        val_status = ev.get("validation_status", "sin_revisar")
        status_counts[val_status] = status_counts.get(val_status, 0) + 1

    c_c1, c_c2, c_c3, c_c4, c_c5, c_c6 = st.columns(6)
    c_c1.metric("🤖 Total IA", total_auto)
    c_c2.metric("✅ Aceptados", status_counts["aceptado"])
    c_c3.metric("✍️ Corregidos", status_counts["corregido"])
    c_c4.metric("❌ Descartados", status_counts["descartado"])
    c_c5.metric("➕ Agregados", status_counts["agregado_manualmente"])
    c_c6.metric("⏳ Pendientes", status_counts["sin_revisar"] + status_counts["requiere_revision"])

    # Aprobación Final
    st.markdown("---")
    st.subheader("🔒 Aprobación y Consolidación del Tránsito")

    is_synthetic = st.session_state["is_synthetic_review"]
    usuario_acepta_sintetico = False
    
    if is_synthetic:
        st.error("🚨 Los datos actuales provienen del caso de simulación demostrativo y están marcados como sintéticos.")
        usuario_acepta_sintetico = st.checkbox("Confirmo que entiendo que este reporte utiliza datos sintéticos demostrativos y no es apto para diseño vial oficial.")

    # Validar criterios
    approval_enabled, warnings_approval = validate_approval_criteria(
        reviewed_events, 
        is_synthetic, 
        usuario_acepta_sintetico,
        umbral_confianza_alert=umbral_confianza
    )

    if warnings_approval:
        st.markdown("##### 🚧 Requisitos de integridad pendientes para aprobar:")
        for warn in warnings_approval:
            st.error(warn)
    else:
        st.success("✅ Todos los requisitos de integridad técnica de aforo se han cumplido correctamente.")

    # Aprobación de Totales Checkbox
    user_approved_totals = st.checkbox("Acepto y apruebo los totales resultantes del conteo consolidado.")

    aprobar_btn = st.button(
        "🔒 Aprobar Aforo Revisado",
        disabled=not (approval_enabled and user_approved_totals),
        type="primary",
        use_container_width=True,
        help="Guarda el conteo consolidado y marca el aforo como aprobado en la sesión."
    )

    if aprobar_btn:
        st.session_state["vision_events_reviewed"] = reviewed_events
        st.session_state["traffic_counts_corrected"] = counts_final
        st.session_state["traffic_review_approved"] = True
        
        st.success("🎉 **ÉXITO:** Aforo aprobado y consolidado. Los conteos viales corregidos se han guardado en la sesión.")
        st.info("💡 **Nota:** La integración con el módulo de TPDA requerirá la confirmación manual y guardado de los factores ABC en el siguiente paso.")
        st.rerun()

    # ── 3. Acción Manual hacia TPDA y 7. Invalidation ──────────────────────────
    st.markdown("---")
    st.subheader("📤 Traspaso Manual a la Pantalla de Aforo y TPDA")
    
    review_approved = st.session_state.get("traffic_review_approved", False)
    
    if not review_approved:
        st.info("ℹ️ Para habilitar el traspaso de datos, complete la revisión y presione 'Aprobar Aforo Revisado' arriba.")
    else:
        # Detectar si hay discrepancias después de haber aprobado (mecanismo de invalidación)
        current_counts = counts_final
        saved_counts = st.session_state.get("traffic_counts_corrected")
        
        counts_match = True
        if saved_counts is not None:
            for cat in CATEGORIAS_ABC:
                if current_counts.get(cat, 0) != saved_counts.get(cat, 0):
                    counts_match = False
                    break
        else:
            counts_match = False
            
        if not counts_match:
            # Los conteos cambiaron, invalidar envío previo
            st.session_state["tpda_input_from_review"] = None
            st.session_state["traffic_review_approved"] = False
            st.warning("⚠️ La revisión de eventos ha sido modificada después de la aprobación. El traspaso anterior ha sido invalidado. Vuelva a aprobar para habilitar el traspaso.")
            st.rerun()

        st.success("✅ Aforo aprobado listo para traspaso manual.")
        
        # Formulario de confirmación y envío
        col_tr1, col_tr2 = st.columns([2, 1])
        with col_tr1:
            st.markdown(
                "Esta acción preparará los datos del aforo auditado para ser cargados en el módulo "
                "**📊 Aforo y TPDA** de forma controlada y reversible. No modificará los cálculos de TPDA existentes."
            )
            confirmar_envio = st.checkbox("Confirmo que deseo transferir este lote de aforo aprobado al módulo de TPDA.")
            
        with col_tr2:
            traspaso_btn = st.button(
                "📤 Usar conteo aprobado en Aforo y TPDA",
                disabled=not confirmar_envio,
                type="primary",
                use_container_width=True,
                help="Prepara la entrada para la pantalla de TPDA."
            )
            
        if traspaso_btn:
            source_video = reviewed_events[0].get("source", "video.mp4") if reviewed_events else "video.mp4"
            
            tpda_input = {
                "counts_by_category": counts_final.copy(),
                "total": total_final,
                "source": source_video,
                "data_origin": "OBSERVADO_POR_VIDEO",
                "vision_batch": [ev["event_id"] for ev in reviewed_events],
                "model_name": "yolov8n.pt",
                "line_y": 360,
                "review_date": datetime.datetime.now().isoformat(),
                "reviewer": "Auditor Vial",
                "is_synthetic": is_synthetic,
                "warnings": warnings_approval.copy(),
                "batch_hash": review_payload_fingerprint(reviewed_events, "review")
            }
            
            st.session_state["tpda_input_from_review"] = tpda_input
            st.success("🎉 **Lote de Aforo listo!** Vaya a la página **Aforo y TPDA** para cargar los datos manualmente.")
            st.rerun()

if __name__ == "__main__":
    render()
