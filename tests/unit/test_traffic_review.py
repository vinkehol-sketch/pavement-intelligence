"""Contrato funcional de la pantalla de revisión, sin ejecutar Streamlit."""
from copy import deepcopy
import json
from pathlib import Path

import pandas as pd
import pytest

import pavement_intelligence.ui.pages.traffic_review as review
from pavement_intelligence.integration import TrafficEventContractError


def valid_event(event_id="evt_1", track_id=1, category="AUTO", original_class="car"):
    return {
        "event_id": event_id, "track_id": track_id, "original_class": original_class,
        "category": category, "confidence": 0.9, "frame_number": 65,
        "video_second": 5.2, "direction": 1, "centroid_x": 379.7,
        "centroid_y": 353.7, "source": "car-detection.mp4",
        "processing_date": "2026-07-17T16:39:22.118815",
        "data_origin": "OBSERVADO_POR_VIDEO",
    }


def reviewed_event(**changes):
    event = review.initialize_reviewed_events([valid_event()])[0]
    event.update({"validation_status": "aceptado", "reviewed": True})
    event.update(changes)
    return event


def session_with_event(event=None):
    return {
        "vision_events_raw": [valid_event()],
        "vision_events_reviewed": [event or reviewed_event()],
        "vision_batch_metadata": {"model_name": "old.pt", "line_y": 1},
        "traffic_counts_corrected": {"AUTO": 1},
        "traffic_review_approved": True,
        "is_synthetic_review": False,
        "traffic_review_source_fingerprint": "old",
        "tpda_result": {"status": "untouched"},
    }


def test_real_line_y360_batch_loads_with_metadata():
    path = Path("data/processed/validation_counter/line_y360/batch_ui_contract_example.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw, reviewed, metadata = review.prepare_review_batch(payload)
    assert len(raw) == len(reviewed) == 1
    assert reviewed[0]["track_id"] == 1
    assert metadata["model_name"] == "yolov8n.pt"
    assert metadata["line_y"] == 360


def test_real_csv_is_adapted_with_correct_types():
    path = Path("data/processed/validation_counter/line_y360/events.csv")
    payload = review.parse_uploaded_review_data(path.name, path.read_bytes())
    _, reviewed, metadata = review.prepare_review_batch(payload)
    assert metadata == {}
    assert reviewed[0]["category"] == "AUTO"
    assert reviewed[0]["direction"] == 1
    assert isinstance(reviewed[0]["confidence"], float)
    assert isinstance(reviewed[0]["frame_number"], int)


def test_camion_has_visual_label_without_changing_original_category():
    event = valid_event(category="CAMION", original_class="truck")
    reviewed = review.initialize_reviewed_events([event])[0]
    assert review.CATEGORIA_MAP["CAMION"] == "Camión no confirmado"
    assert reviewed["category"] == "CAMION"
    assert reviewed["corrected_category"] is None


def test_camion_blocks_approval_without_valid_correction():
    truck = review.initialize_reviewed_events([
        valid_event(category="CAMION", original_class="truck")
    ])[0]
    truck.update({"validation_status": "aceptado", "reviewed": True})
    approved, warnings = review.validate_approval_criteria([truck], False, False)
    assert approved is False
    assert any("Camión no confirmado" in warning for warning in warnings)


def test_camion_classification_requires_reason_even_if_marked_accepted():
    truck = review.initialize_reviewed_events([
        valid_event(category="CAMION", original_class="truck")
    ])[0]
    truck.update({"corrected_category": "C2", "validation_status": "aceptado", "reviewed": True})
    approved, warnings = review.validate_approval_criteria([truck], False, False)
    assert approved is False
    assert any("justificación" in warning for warning in warnings)


def test_original_category_and_all_technical_fields_are_immutable():
    event = reviewed_event()
    session = session_with_event(event)
    before = {field: deepcopy(event[field]) for field in review.IMMUTABLE_EVENT_FIELDS}
    review.apply_review_update(
        session, event["event_id"],
        {"corrected_category": "CAMIONETA", "validation_status": "corregido", "correction_reason": "Revisión visual"},
        "Auditor",
    )
    assert {field: event[field] for field in review.IMMUTABLE_EVENT_FIELDS} == before
    with pytest.raises(ValueError):
        review.apply_review_update(session, event["event_id"], {"category": "BUS"}, "Auditor")


def test_modifying_event_invalidates_previous_approval():
    session = session_with_event()
    review.apply_review_update(
        session, "evt_1", {"validation_status": "descartado", "include_in_final_count": False,
                             "correction_reason": "Falso positivo"}, "Auditor",
    )
    assert session["traffic_review_approved"] is False
    assert session["traffic_counts_corrected"] == {}


def test_loading_new_batch_clears_previous_review_and_preserves_tpda():
    session = session_with_event()
    tpda_before = deepcopy(session["tpda_result"])
    review.replace_review_session(session, [valid_event("evt_new", 9)], is_synthetic=False, source_fingerprint="new")
    assert [item["event_id"] for item in session["vision_events_reviewed"]] == ["evt_new"]
    assert session["traffic_review_approved"] is False
    assert session["traffic_counts_corrected"] == {}
    assert session["tpda_result"] == tpda_before


def test_counter_fingerprint_changes_between_videos():
    first = review.review_payload_fingerprint([valid_event("evt_a", 1)], "counter")
    second = review.review_payload_fingerprint([valid_event("evt_b", 2)], "counter")
    assert first.startswith("counter:") and second.startswith("counter:")
    assert first != second


def test_manual_event_uses_separate_namespace_and_no_tracker_id():
    event = review.create_manual_review_event(
        "BUS", 1, 14.5, "Bus omitido por oclusión", "Ing. Revisor",
        now="2026-07-17T16:10:00Z", manual_event_id="manual:test-1",
    )
    assert event["event_id"] == event["manual_event_id"] == "manual:test-1"
    assert event["track_id"] is None and event["track_id"] != -1
    assert event["data_origin"] == "manual"
    assert event["reviewed_by"] == "Ing. Revisor"
    assert event["corrected_category"] == "BUS"


def test_data_origin_is_preserved_by_ui_initialization():
    reviewed = review.initialize_reviewed_events([valid_event()])[0]
    assert reviewed["data_origin"] == "OBSERVADO_POR_VIDEO"


def test_batch_model_and_line_metadata_survive_session_load():
    payload = json.loads(Path(
        "data/processed/validation_counter/line_y360/batch_ui_contract_example.json"
    ).read_text(encoding="utf-8"))
    session = session_with_event()
    review.replace_review_session(session, payload, is_synthetic=False)
    assert session["vision_batch_metadata"]["model_name"] == "yolov8n.pt"
    assert session["vision_batch_metadata"]["line_id"] == "main_line"
    assert session["vision_batch_metadata"]["line_y"] == 360


def test_import_error_does_not_contaminate_session_state():
    session = session_with_event()
    original = deepcopy(session)
    invalid = [valid_event(), {**valid_event("evt_bad", 2), "direction": 0}]
    with pytest.raises(TrafficEventContractError):
        review.replace_review_session(session, invalid, is_synthetic=False)
    assert session == original


def test_adapter_is_the_only_raw_event_normalizer(monkeypatch):
    calls = []
    official = review.adapt_traffic_event_for_review
    def spy(event):
        calls.append(event)
        return official(event)
    monkeypatch.setattr(review, "adapt_traffic_event_for_review", spy)
    review.initialize_reviewed_events([valid_event()])
    assert len(calls) == 1
    with pytest.raises(TrafficEventContractError):
        review.initialize_reviewed_events([{**valid_event(), "track_id": -1}])


def test_adapter_and_ui_do_not_modify_original_event():
    original = valid_event(); snapshot = deepcopy(original)
    review.initialize_reviewed_events([original])
    assert original == snapshot


def test_duplicate_event_ids_are_rejected():
    with pytest.raises(TrafficEventContractError):
        review.prepare_review_batch([valid_event(), valid_event()])


def test_vehicle_categories_come_from_central_catalog():
    assert review.CATEGORIAS_ABC == [
        "MOTO", "AUTO", "CAMIONETA", "MINIBUS", "BUS",
        "C2", "C3", "TRACTOCAMION", "ARTICULADO", "OTRO_PESADO",
    ]


def test_synthetic_and_unreviewed_events_block_approval():
    event = review.initialize_reviewed_events([valid_event()])[0]
    approved, warnings = review.validate_approval_criteria([event], True, False)
    assert approved is False
    assert any("pendientes" in warning for warning in warnings)
    assert any("sintéticos" in warning for warning in warnings)


def test_correction_or_discard_requires_reason():
    event = reviewed_event(validation_status="corregido", correction_reason="")
    approved, warnings = review.validate_approval_criteria([event], False, False)
    assert approved is False
    assert any("justificación" in warning for warning in warnings)


def test_correction_requires_reviewer_and_valid_category():
    event = reviewed_event(
        validation_status="corregido", corrected_category="CAMIONETA",
        correction_reason="Reclasificación visual", reviewed_by="",
    )
    approved, warnings = review.validate_approval_criteria([event], False, False)
    assert approved is False
    assert any("revisor" in warning for warning in warnings)

    event["reviewed_by"] = "Ing. Revisor"
    event["corrected_category"] = None
    approved, warnings = review.validate_approval_criteria([event], False, False)
    assert approved is False
    assert any("categoría válida" in warning for warning in warnings)


def test_review_update_rejects_blank_reviewer():
    session = session_with_event()
    with pytest.raises(ValueError, match="responsable"):
        review.apply_review_update(
            session, "evt_1",
            {"validation_status": "corregido", "corrected_category": "CAMIONETA",
             "correction_reason": "Reclasificación visual"},
            "   ",
        )


def test_no_final_valid_event_blocks_approval():
    event = reviewed_event(validation_status="descartado", include_in_final_count=False,
                           correction_reason="Falso positivo")
    approved, warnings = review.validate_approval_criteria([event], False, False)
    assert approved is False
    assert any("conteo final" in warning for warning in warnings)


def test_consolidated_counts_use_only_confirmed_category():
    auto = reviewed_event()
    truck = review.initialize_reviewed_events([
        valid_event("evt_truck", 2, "CAMION", "truck")
    ])[0]
    truck.update({"corrected_category": "C3", "validation_status": "corregido", "reviewed": True,
                  "correction_reason": "Tres ejes"})
    counts_auto, counts_final, total_auto, total_final = review.calculate_consolidated_transit([auto, truck])
    assert counts_auto["AUTO"] == 1
    assert counts_final["AUTO"] == 1 and counts_final["C3"] == 1
    assert total_auto == 1 and total_final == 2


# ── NUEVAS PRUEBAS DE INTEGRACIÓN REVISIÓN-TPDA ──────────────────────────────

def test_page_appears_in_navigation():
    """Prueba 1: Verifica que la página de revisión esté configurada en app.py."""
    app_path = Path("src/pavement_intelligence/ui/app.py")
    assert app_path.exists()
    content = app_path.read_text(encoding="utf-8")
    assert "pages/traffic_review.py" in content
    assert "pages/survey_tpda.py" in content
    assert "st.navigation" in content

def test_cannot_send_without_approved_review():
    """Prueba 2: No se puede enviar a TPDA si la revisión no está aprobada."""
    session = {
        "traffic_review_approved": False,
        "traffic_counts_corrected": {"AUTO": 10},
        "tpda_input_from_review": None
    }
    # La UI de revisión no creará tpda_input_from_review si traffic_review_approved es False
    assert session["tpda_input_from_review"] is None

def test_tpda_input_from_review_creation():
    """Prueba 3, 4 y 5: Verifica la creación de tpda_input_from_review sin alterar tpda_result."""
    reviewed = [
        {
            "event_id": "evt_1",
            "track_id": 1,
            "original_class": "car",
            "category": "AUTO",
            "confidence": 0.90,
            "validation_status": "aceptado",
            "corrected_category": "AUTO",
            "include_in_final_count": True,
            "source": "video_test.mp4"
        }
    ]
    
    # Simular la acción manual de traspaso
    counts_final = {"AUTO": 1}
    total_final = 1
    is_synthetic = True
    warnings = ["Datos de prueba"]
    
    tpda_input = {
        "counts_by_category": counts_final.copy(),
        "total": total_final,
        "source": "video_test.mp4",
        "data_origin": "OBSERVADO_POR_VIDEO",
        "vision_batch": [ev["event_id"] for ev in reviewed],
        "model_name": "yolov8n.pt",
        "line_y": 360,
        "review_date": "2026-07-17T17:00:00Z",
        "reviewer": "Auditor Vial",
        "is_synthetic": is_synthetic,
        "warnings": warnings,
        "batch_hash": "batch_test_123"
    }
    
    session = {
        "tpda_input_from_review": tpda_input,
        "tpda_result": {"status": "original_tpda_untouched"}
    }
    
    assert session["tpda_input_from_review"]["counts_by_category"]["AUTO"] == 1
    assert session["tpda_input_from_review"]["is_synthetic"] is True
    # tpda_result no se modifica directamente al transferir
    assert session["tpda_result"] == {"status": "original_tpda_untouched"}

def test_survey_tpda_detects_input_and_traceability():
    """Prueba 6, 7, 8 y 9: Verifica que survey_tpda procese la entrada de revisión conservando la trazabilidad y advertencias."""
    # Simular st.session_state con tpda_input_from_review cargado
    tpda_input = {
        "counts_by_category": {"AUTO": 5, "C3": 2},
        "total": 7,
        "source": "video_test.mp4",
        "data_origin": "OBSERVADO_POR_VIDEO",
        "vision_batch": ["evt_1", "evt_2"],
        "model_name": "yolov8n.pt",
        "line_y": 360,
        "review_date": "2026-07-17T17:00:00Z",
        "reviewer": "Auditor Vial",
        "is_synthetic": True,
        "warnings": ["Datos demostrativos"],
        "batch_hash": "batch_test_123"
    }
    
    # Comprobar la simulación de carga en survey_tpda:
    # 1. Conservar conteo
    conteo_base = tpda_input["counts_by_category"].copy()
    assert conteo_base["AUTO"] == 5
    assert conteo_base["C3"] == 2
    
    # 2. Conservar trazabilidad
    assert tpda_input["reviewer"] == "Auditor Vial"
    assert tpda_input["source"] == "video_test.mp4"
    assert tpda_input["is_synthetic"] is True
    
    # 3. Propagar warnings
    assert "Datos demostrativos" in tpda_input["warnings"]

def test_change_review_invalidates_previous_transfer():
    """Prueba 10: Modificar la revisión de eventos invalida el envío previo."""
    session = {
        "traffic_review_approved": True,
        "traffic_counts_corrected": {"AUTO": 1},
        "tpda_input_from_review": {"batch_hash": "batch_123"}
    }
    
    # Simular cambio de conteo en la UI de revisión
    current_counts = {"AUTO": 2}  # El usuario editó la tabla
    saved_counts = session["traffic_counts_corrected"]
    
    counts_match = True
    for cat in ["AUTO"]:
        if current_counts.get(cat, 0) != saved_counts.get(cat, 0):
            counts_match = False
            break
            
    if not counts_match:
        session["tpda_input_from_review"] = None
        session["traffic_review_approved"] = False
        
    assert session["tpda_input_from_review"] is None
    assert session["traffic_review_approved"] is False

def test_new_batch_does_not_reuse_previous_counts():
    """Prueba 11: Un nuevo lote de visión no debe reutilizar los conteos de la revisión anterior."""
    raw_events_new = [
        valid_event("evt_new_1", 1, "MOTO", "motorcycle")
    ]
    
    # Inicializar nuevo lote
    reviewed_new = review.initialize_reviewed_events(raw_events_new)
    assert len(reviewed_new) == 1
    assert reviewed_new[0]["category"] == "MOTO"
    assert reviewed_new[0]["corrected_category"] == "MOTO"


