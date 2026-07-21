"""Caso demostrativo sintético, aislado y reproducible."""

from .case import (
    DEMO_CASE_ID,
    DEMO_DATA_ORIGIN,
    DEMO_NOTICE,
    DEMO_SEED,
    DemoCase,
    build_demo_case,
    build_demo_plate_readings,
    build_demo_tpda_input,
    build_demo_traffic_events,
)
from .session import (
    DEMO_MANAGED_SESSION_KEYS,
    DemoSessionConflict,
    load_demo_session,
    reset_demo_session,
)
from .metadata import (
    DEMO_PROJECT_METADATA,
    DEMO_REPORT_METADATA,
    DEMO_REQUIRED_FIELDS,
    DEMO_RESPONSIBLE_PARTIES,
    DEMO_STUDY_DATE,
    DemoProjectMetadata,
    DemoRequiredField,
    DemoResponsibleParties,
    demo_widget_defaults,
)

__all__ = (
    "DEMO_CASE_ID",
    "DEMO_DATA_ORIGIN",
    "DEMO_MANAGED_SESSION_KEYS",
    "DEMO_NOTICE",
    "DEMO_PROJECT_METADATA",
    "DEMO_REPORT_METADATA",
    "DEMO_REQUIRED_FIELDS",
    "DEMO_RESPONSIBLE_PARTIES",
    "DEMO_SEED",
    "DEMO_STUDY_DATE",
    "DemoCase",
    "DemoProjectMetadata",
    "DemoRequiredField",
    "DemoResponsibleParties",
    "DemoSessionConflict",
    "build_demo_case",
    "build_demo_plate_readings",
    "build_demo_tpda_input",
    "build_demo_traffic_events",
    "demo_widget_defaults",
    "load_demo_session",
    "reset_demo_session",
)
