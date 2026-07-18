from __future__ import annotations

import inspect

import pytest

from pavement_intelligence.domain.traffic import presentation
from pavement_intelligence.domain.traffic.presentation import (
    DashboardOperationalState, MonitoringSource, OcrSummaryPresentation,
    ReviewStatus, TrafficMetricsPresentation,
)
from pavement_intelligence.ui.utils.demo_data import load_demo_dashboard, validate_dashboard_state
from pavement_intelligence.ui.utils.formatting import format_unit


def test_demo_dashboard_builds_valid_presentation_models():
    state = load_demo_dashboard()
    assert state.demo_mode is True
    assert state.operational_state is DashboardOperationalState.PROCESSING_ACTIVE
    assert state.review.status is ReviewStatus.PENDING_REVIEW
    assert validate_dashboard_state(state) == ()


def test_demo_totals_match_categories_and_directions():
    state = load_demo_dashboard()
    assert state.category_total == state.metrics.accumulated_total == 1556
    assert state.direction_total == state.metrics.accumulated_total


@pytest.mark.parametrize("field,value", [
    ("current_flow_veh_min", -1), ("average_speed_kmh", -1),
    ("vehicles_in_scene", -1), ("accumulated_total", -1),
    ("visual_occupancy_percent", -1),
])
def test_metrics_reject_negative_values(field, value):
    values = dict(current_flow_veh_min=1, average_speed_kmh=1, vehicles_in_scene=1, accumulated_total=1, visual_occupancy_percent=1)
    values[field] = value
    with pytest.raises(ValueError):
        TrafficMetricsPresentation(**values)


def test_disconnected_source_and_operational_state_are_mutually_exclusive():
    state = load_demo_dashboard()
    with pytest.raises(ValueError):
        presentation.TrafficDashboardState(
            **{**vars(state), "source": presentation.MonitoringSourcePresentation(
                source_type=MonitoringSource.DISCONNECTED, label="Sin fuente", point_name="Punto 04",
                configured_direction="Bidireccional", fps=0, resolution="—", latency_ms=0,
            )}
        )


def test_format_unit_is_safe_and_readable():
    assert format_unit(32, "veh/min") == "32 veh/min"
    assert format_unit(21.25, "km/h", 1) == "21.2 km/h"
    assert format_unit(None, "km/h") == "—"
    assert format_unit(float("nan"), "%") == "—"


def test_presentation_models_do_not_depend_on_streamlit():
    assert "streamlit" not in inspect.getsource(presentation)


def test_ocr_summary_is_independent_from_traffic_review_approval():
    pending = load_demo_dashboard().ocr
    approved = OcrSummaryPresentation(**vars(pending))
    assert approved == pending
    assert not hasattr(approved, "review_status")
