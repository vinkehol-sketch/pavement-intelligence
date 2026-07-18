"""Adaptador puro entre ``TrafficEvent`` y la revisión manual.

No contiene estado de UI, no modifica el evento recibido y no envía conteos a TPDA.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from math import isfinite
from numbers import Integral, Real
from typing import Any, Iterable, Mapping


REQUIRED_EVENT_FIELDS = (
    "event_id",
    "track_id",
    "original_class",
    "category",
    "confidence",
    "frame_number",
    "video_second",
    "direction",
    "centroid_x",
    "centroid_y",
    "source",
    "processing_date",
    "data_origin",
)
ALLOWED_ORIGINAL_CLASSES = {"car", "motorcycle", "bus", "truck"}
ALLOWED_PRELIMINARY_CATEGORIES = {"AUTO", "MOTO", "BUS", "CAMION", "DESCONOCIDO"}
REQUIRED_BATCH_METADATA = (
    "model_name",
    "line_id",
    "line_y",
    "source_video",
    "processing_date",
    "configuration_version",
)


class TrafficEventContractError(ValueError):
    """Indica que un evento o lote no satisface el contrato técnico."""


def _event_mapping(event: Any) -> dict[str, Any]:
    if isinstance(event, Mapping):
        return dict(event)
    if hasattr(event, "to_dict"):
        value = event.to_dict()
        if isinstance(value, Mapping):
            return dict(value)
    if is_dataclass(event):
        return asdict(event)
    raise TrafficEventContractError("El evento debe ser TrafficEvent o un mapping.")


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrafficEventContractError(f"{field} debe ser una cadena no vacía.")
    return value


def _require_integer(value: Any, field: str, minimum: int = 0) -> int:
    if not isinstance(value, Integral) or isinstance(value, bool) or int(value) < minimum:
        raise TrafficEventContractError(f"{field} debe ser un entero >= {minimum}.")
    return int(value)


def _require_number(value: Any, field: str, minimum: float | None = None, maximum: float | None = None) -> float:
    if not isinstance(value, Real) or isinstance(value, bool) or not isfinite(float(value)):
        raise TrafficEventContractError(f"{field} debe ser numérico y finito.")
    result = float(value)
    if minimum is not None and result < minimum:
        raise TrafficEventContractError(f"{field} debe ser >= {minimum}.")
    if maximum is not None and result > maximum:
        raise TrafficEventContractError(f"{field} debe ser <= {maximum}.")
    return result


def _require_iso_datetime(value: Any, field: str) -> str:
    text = _require_nonempty_string(value, field)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrafficEventContractError(f"{field} debe usar formato ISO 8601.") from exc
    return text


def validate_traffic_event(event: Any) -> dict[str, Any]:
    """Valida y normaliza una copia del evento sin cambiar el original."""
    record = _event_mapping(event)
    missing = [field for field in REQUIRED_EVENT_FIELDS if field not in record]
    if missing:
        raise TrafficEventContractError(f"Faltan campos obligatorios: {', '.join(missing)}")

    normalized = dict(record)
    normalized["event_id"] = _require_nonempty_string(record["event_id"], "event_id")
    normalized["track_id"] = _require_integer(record["track_id"], "track_id")
    normalized["original_class"] = _require_nonempty_string(record["original_class"], "original_class")
    if normalized["original_class"] not in ALLOWED_ORIGINAL_CLASSES:
        raise TrafficEventContractError("original_class no pertenece a las clases COCO vehiculares admitidas.")
    normalized["category"] = _require_nonempty_string(record["category"], "category")
    if normalized["category"] not in ALLOWED_PRELIMINARY_CATEGORIES:
        raise TrafficEventContractError("category no pertenece a las categorías preliminares admitidas.")
    normalized["confidence"] = _require_number(record["confidence"], "confidence", 0.0, 1.0)
    normalized["frame_number"] = _require_integer(record["frame_number"], "frame_number")
    normalized["video_second"] = _require_number(record["video_second"], "video_second", 0.0)
    if not isinstance(record["direction"], Integral) or isinstance(record["direction"], bool) or int(record["direction"]) not in {-1, 1}:
        raise TrafficEventContractError("direction debe ser 1 o -1.")
    normalized["direction"] = int(record["direction"])
    normalized["centroid_x"] = _require_number(record["centroid_x"], "centroid_x")
    normalized["centroid_y"] = _require_number(record["centroid_y"], "centroid_y")
    normalized["source"] = _require_nonempty_string(record["source"], "source")
    normalized["processing_date"] = _require_iso_datetime(record["processing_date"], "processing_date")
    normalized["data_origin"] = _require_nonempty_string(record["data_origin"], "data_origin")
    return normalized


def adapt_traffic_event_for_review(event: Any) -> dict[str, Any]:
    """Produce una copia validada con campos iniciales de revisión manual."""
    review_record = validate_traffic_event(event)
    review_record.update({
        "validation_status": "sin_revisar",
        "corrected_category": None,
        "correction_reason": "",
        "reviewed": False,
        "reviewed_by": "",
        "reviewed_at": None,
        "include_in_final_count": True,
    })
    return review_record


def build_traffic_event_batch(events: Iterable[Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Agrupa eventos adaptados con metadatos técnicos del lote."""
    batch_metadata = dict(metadata)
    missing = [field for field in REQUIRED_BATCH_METADATA if field not in batch_metadata]
    if missing:
        raise TrafficEventContractError(f"Faltan metadatos de lote: {', '.join(missing)}")
    batch_metadata["model_name"] = _require_nonempty_string(batch_metadata["model_name"], "model_name")
    batch_metadata["line_id"] = _require_nonempty_string(batch_metadata["line_id"], "line_id")
    batch_metadata["line_y"] = _require_integer(batch_metadata["line_y"], "line_y")
    batch_metadata["source_video"] = _require_nonempty_string(batch_metadata["source_video"], "source_video")
    batch_metadata["processing_date"] = _require_iso_datetime(batch_metadata["processing_date"], "processing_date")
    batch_metadata["configuration_version"] = _require_nonempty_string(
        batch_metadata["configuration_version"], "configuration_version"
    )
    adapted_events = [adapt_traffic_event_for_review(event) for event in events]
    return {"metadata": batch_metadata, "events": adapted_events}
