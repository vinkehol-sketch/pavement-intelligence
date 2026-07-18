"""Modelos puros de presentación para el centro de monitoreo de tráfico."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CongestionLevel(str, Enum):
    NORMAL = "NORMAL"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class MonitoringSource(str, Enum):
    UPLOADED_VIDEO = "UPLOADED_VIDEO"
    LIVE_CAMERA = "LIVE_CAMERA"
    SIMULATED = "SIMULATED"
    DISCONNECTED = "DISCONNECTED"


class ReviewStatus(str, Enum):
    UNPROCESSED = "UNPROCESSED"
    PENDING_REVIEW = "PENDING_REVIEW"
    REQUIRES_CORRECTION = "REQUIRES_CORRECTION"
    APPROVED = "APPROVED"


class DashboardOperationalState(str, Enum):
    NO_DATA = "NO_DATA"
    LOADING = "LOADING"
    PROCESSING_ACTIVE = "PROCESSING_ACTIVE"
    PROCESSING_PAUSED = "PROCESSING_PAUSED"
    ERROR = "ERROR"
    SOURCE_DISCONNECTED = "SOURCE_DISCONNECTED"


def _non_negative(value: float | int, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} no puede ser negativo.")


@dataclass(frozen=True)
class TrafficMetricsPresentation:
    current_flow_veh_min: float
    average_speed_kmh: float
    vehicles_in_scene: int
    accumulated_total: int
    visual_occupancy_percent: float

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            _non_negative(value, name)
        if self.visual_occupancy_percent > 100:
            raise ValueError("visual_occupancy_percent debe estar entre 0 y 100.")


@dataclass(frozen=True)
class VehicleCategoryCountPresentation:
    category: str
    label: str
    count: int
    trend_percent: float = 0.0

    def __post_init__(self) -> None:
        _non_negative(self.count, "count")


@dataclass(frozen=True)
class DirectionCountPresentation:
    direction: str
    label: str
    count: int

    def __post_init__(self) -> None:
        _non_negative(self.count, "count")


@dataclass(frozen=True)
class CongestionPresentation:
    level: CongestionLevel
    label: str
    detail: str


@dataclass(frozen=True)
class TrafficAlertPresentation:
    time: str
    alert_type: str
    description: str
    level: str
    status: str


@dataclass(frozen=True)
class MonitoringSourcePresentation:
    source_type: MonitoringSource
    label: str
    point_name: str
    configured_direction: str
    fps: float
    resolution: str
    latency_ms: int

    def __post_init__(self) -> None:
        _non_negative(self.fps, "fps")
        _non_negative(self.latency_ms, "latency_ms")


@dataclass(frozen=True)
class OcrSummaryPresentation:
    detected: int
    valid: int
    doubtful: int
    pending: int
    average_confidence_percent: float
    illegible: int = 0
    experimental: bool = True

    def __post_init__(self) -> None:
        for name in ("detected", "valid", "doubtful", "pending", "illegible", "average_confidence_percent"):
            _non_negative(getattr(self, name), name)
        if self.average_confidence_percent > 100:
            raise ValueError("average_confidence_percent debe estar entre 0 y 100.")
        if self.valid + self.doubtful + self.pending + self.illegible != self.detected:
            raise ValueError("El desglose OCR debe coincidir con el total detectado.")


@dataclass(frozen=True)
class ReviewStatusPresentation:
    status: ReviewStatus
    label: str
    detail: str = ""


@dataclass(frozen=True)
class TrafficDashboardState:
    operational_state: DashboardOperationalState
    demo_mode: bool
    source: MonitoringSourcePresentation
    metrics: TrafficMetricsPresentation
    congestion: CongestionPresentation
    categories: tuple[VehicleCategoryCountPresentation, ...]
    directions: tuple[DirectionCountPresentation, ...]
    time_series: tuple[dict[str, object], ...]
    alerts: tuple[TrafficAlertPresentation, ...]
    review: ReviewStatusPresentation
    ocr: OcrSummaryPresentation
    frame_path: str

    @property
    def category_total(self) -> int:
        return sum(item.count for item in self.categories)

    @property
    def direction_total(self) -> int:
        return sum(item.count for item in self.directions)

    def __post_init__(self) -> None:
        if self.operational_state is DashboardOperationalState.SOURCE_DISCONNECTED:
            if self.source.source_type is not MonitoringSource.DISCONNECTED:
                raise ValueError("Una fuente desconectada requiere source_type DISCONNECTED.")
        elif self.source.source_type is MonitoringSource.DISCONNECTED:
            raise ValueError("DISCONNECTED requiere el estado SOURCE_DISCONNECTED.")
        if self.category_total != self.metrics.accumulated_total:
            raise ValueError("El total por categorías no coincide con el acumulado.")
        if self.direction_total != self.metrics.accumulated_total:
            raise ValueError("El total por sentidos no coincide con el acumulado.")
