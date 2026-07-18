"""Contratos desacoplados entre el backend técnico y sus consumidores."""

from .traffic_event_adapter import (
    TrafficEventContractError,
    adapt_traffic_event_for_review,
    build_traffic_event_batch,
)

__all__ = [
    "TrafficEventContractError",
    "adapt_traffic_event_for_review",
    "build_traffic_event_batch",
]
