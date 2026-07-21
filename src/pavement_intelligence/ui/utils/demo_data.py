"""Carga y validación de fixtures exclusivamente demostrativos."""
from __future__ import annotations

import json
from pathlib import Path

from pavement_intelligence.domain.traffic.presentation import (
    CongestionLevel, CongestionPresentation, DashboardOperationalState,
    DirectionCountPresentation, MonitoringSource, MonitoringSourcePresentation,
    OcrSummaryPresentation, ReviewStatus, ReviewStatusPresentation,
    TrafficAlertPresentation, TrafficDashboardState, TrafficMetricsPresentation,
    VehicleCategoryCountPresentation,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEMO_DATA_DIR = PROJECT_ROOT / "data" / "samples" / "ui"


def _read_json(name: str) -> dict:
    with (DEMO_DATA_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_demo_dashboard() -> TrafficDashboardState:
    dashboard = _read_json("traffic_dashboard_demo.json")
    alert_payload = _read_json("traffic_alerts_demo.json")
    ocr_payload = _read_json("ocr_summary_demo.json")
    if dashboard.get("data_origin") != "synthetic_demo" or not dashboard.get("is_demo"):
        raise ValueError("El fixture debe estar identificado como demostrativo.")
    if (
        alert_payload.get("data_origin") != "synthetic_demo"
        or ocr_payload.get("data_origin") != "synthetic_demo"
    ):
        raise ValueError("Todos los fixtures auxiliares deben tener origen demostrativo.")
    alerts = alert_payload["alerts"]
    ocr = {
        key: value
        for key, value in ocr_payload.items()
        if key not in {"data_origin", "is_demo"}
    }
    metrics = TrafficMetricsPresentation(**dashboard["metrics"])
    return TrafficDashboardState(
        operational_state=DashboardOperationalState(dashboard["operational_state"]),
        demo_mode=True,
        source=MonitoringSourcePresentation(source_type=MonitoringSource(dashboard["source"]["source_type"]), **{k: v for k, v in dashboard["source"].items() if k != "source_type"}),
        metrics=metrics,
        congestion=CongestionPresentation(level=CongestionLevel(dashboard["congestion"]["level"]), label=dashboard["congestion"]["label"], detail=dashboard["congestion"]["detail"]),
        categories=tuple(VehicleCategoryCountPresentation(**item) for item in dashboard["categories"]),
        directions=tuple(DirectionCountPresentation(**item) for item in dashboard["directions"]),
        time_series=tuple(dashboard["time_series"]),
        alerts=tuple(TrafficAlertPresentation(**item) for item in alerts),
        review=ReviewStatusPresentation(status=ReviewStatus(dashboard["review"]["status"]), label=dashboard["review"]["label"], detail=dashboard["review"].get("detail", "")),
        ocr=OcrSummaryPresentation(**ocr),
        frame_path=dashboard["frame_path"],
    )


def validate_dashboard_state(state: TrafficDashboardState) -> tuple[str, ...]:
    issues: list[str] = []
    if not state.demo_mode:
        issues.append("La pantalla de esta fase solo admite modo demostración.")
    if not state.time_series:
        issues.append("No existe serie temporal para representar.")
    return tuple(issues)
