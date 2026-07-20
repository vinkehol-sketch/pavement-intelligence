"""Controladores neutrales para análisis de fuentes visuales."""

from .controller import (
    AnalysisState, CongestionThresholds, FrameAnalysisResult,
    TrafficAnalysisController, classify_congestion,
)

from .ocr_controller import (
    NormalizedPlateRoi,
    NormalizedRoiExtractor,
    PlateAnalysisConfig,
    PlateAnalysisController,
)
from .ocr_models import (
    PlateAnalysisState,
    PlateBatchResult,
    PlateFrameResult,
    PlateReadingCandidate,
    PlateReadingOrigin,
    PlateReadingStatus,
)

__all__ = [
    "AnalysisState",
    "CongestionThresholds",
    "FrameAnalysisResult",
    "NormalizedPlateRoi",
    "NormalizedRoiExtractor",
    "PlateAnalysisConfig",
    "PlateAnalysisController",
    "PlateAnalysisState",
    "PlateBatchResult",
    "PlateFrameResult",
    "PlateReadingCandidate",
    "PlateReadingOrigin",
    "PlateReadingStatus",
    "TrafficAnalysisController",
    "classify_congestion",
]
