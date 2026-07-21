"""Caso demostrativo sintético, aislado y reproducible."""

from .case import (
    DEMO_CASE_ID,
    DEMO_DATA_ORIGIN,
    DEMO_NOTICE,
    DEMO_SEED,
    DemoCase,
    build_demo_case,
    build_demo_plate_readings,
    build_demo_traffic_events,
)
from .session import (
    DEMO_MANAGED_SESSION_KEYS,
    DemoSessionConflict,
    load_demo_session,
    reset_demo_session,
)

__all__ = (
    "DEMO_CASE_ID",
    "DEMO_DATA_ORIGIN",
    "DEMO_MANAGED_SESSION_KEYS",
    "DEMO_NOTICE",
    "DEMO_SEED",
    "DemoCase",
    "DemoSessionConflict",
    "build_demo_case",
    "build_demo_plate_readings",
    "build_demo_traffic_events",
    "load_demo_session",
    "reset_demo_session",
)
