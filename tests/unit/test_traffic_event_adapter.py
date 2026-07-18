"""Pruebas del contrato entre el contador y la revisión manual."""
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from pavement_intelligence.integration.traffic_event_adapter import (
    TrafficEventContractError,
    adapt_traffic_event_for_review,
    build_traffic_event_batch,
)
from pavement_intelligence.vision.pipeline import TrafficEvent, export_corrected_records


def valid_event():
    return TrafficEvent(
        event_id="evt_1_7", track_id=7, original_class="car", category="AUTO",
        confidence=0.8123, frame_number=65, video_second=5.2, direction=1,
        centroid_x=379.7, centroid_y=353.7, source="car-detection.mp4",
        processing_date="2026-07-17T16:39:22.118815",
    )


def valid_dict():
    return valid_event().to_dict()


def batch_metadata():
    return {
        "model_name": "yolov8n.pt", "line_id": "main_line", "line_y": 360,
        "source_video": "car-detection.mp4", "processing_date": "2026-07-17T16:39:22.118815",
        "configuration_version": "mvp-yolov8n-line360-v1",
    }


def test_valid_traffic_event_serializes_and_adapts():
    adapted = adapt_traffic_event_for_review(valid_event())
    assert adapted["event_id"] == "evt_1_7"
    assert adapted["data_origin"] == "OBSERVADO_POR_VIDEO"


@pytest.mark.parametrize("track_id", [-1, None])
def test_invalid_track_id_is_rejected(track_id):
    event = valid_dict(); event["track_id"] = track_id
    with pytest.raises(TrafficEventContractError):
        adapt_traffic_event_for_review(event)


def test_original_class_and_preliminary_category_are_preserved():
    adapted = adapt_traffic_event_for_review(valid_event())
    assert adapted["original_class"] == "car"
    assert adapted["category"] == "AUTO"


def test_confidence_remains_numeric():
    adapted = adapt_traffic_event_for_review(valid_event())
    assert isinstance(adapted["confidence"], float)
    assert adapted["confidence"] == pytest.approx(0.8123)


def test_invalid_direction_is_rejected():
    event = valid_dict(); event["direction"] = 0
    with pytest.raises(TrafficEventContractError):
        adapt_traffic_event_for_review(event)


@pytest.mark.parametrize("frame_number", [-1, 2.5, None])
def test_invalid_frame_number_is_rejected(frame_number):
    event = valid_dict(); event["frame_number"] = frame_number
    with pytest.raises(TrafficEventContractError):
        adapt_traffic_event_for_review(event)


def test_adapter_does_not_modify_original_event_or_dict():
    event = valid_dict(); original = deepcopy(event)
    adapt_traffic_event_for_review(event)
    assert event == original


def test_review_fields_are_initialized_without_overwriting_event_data():
    adapted = adapt_traffic_event_for_review(valid_event())
    assert adapted["validation_status"] == "sin_revisar"
    assert adapted["corrected_category"] is None
    assert adapted["reviewed"] is False
    assert adapted["include_in_final_count"] is True
    assert adapted["category"] == "AUTO"


def test_exported_csv_can_be_loaded_without_important_type_loss(tmp_path):
    adapted = adapt_traffic_event_for_review(valid_event())
    paths = export_corrected_records([adapted], tmp_path)
    loaded = pd.read_csv(paths["csv"])
    assert int(loaded.loc[0, "track_id"]) == 7
    assert int(loaded.loc[0, "frame_number"]) == 65
    assert int(loaded.loc[0, "direction"]) == 1
    assert float(loaded.loc[0, "confidence"]) == pytest.approx(0.8123)
    assert loaded.loc[0, "category"] == "AUTO"


def test_batch_contract_does_not_modify_tpda_or_calculation_keys():
    session_like = {"tpda_result": {"tpda_total": 123.0}, "esal_result": {"total": 4.5}}
    original = deepcopy(session_like)
    batch = build_traffic_event_batch([valid_event()], batch_metadata())
    assert session_like == original
    assert set(batch) == {"metadata", "events"}
    assert "tpda_result" not in batch and "esal_result" not in batch


def test_real_line_y360_csv_is_contract_compatible():
    csv_path = Path("data/processed/validation_counter/line_y360/events.csv")
    records = pd.read_csv(csv_path).to_dict(orient="records")
    assert records
    adapted = [adapt_traffic_event_for_review(record) for record in records]
    assert all(record["track_id"] >= 0 for record in adapted)
    assert {record["category"] for record in adapted} == {"AUTO"}
    assert {record["direction"] for record in adapted} == {1}
