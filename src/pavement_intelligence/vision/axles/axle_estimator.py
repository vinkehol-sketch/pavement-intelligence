"""
Estimador de configuración de ejes por análisis geométrico del bbox.
IMPORTANTE: Esta es una ESTIMACIÓN VISUAL, no una medición real.
Los resultados deben marcarse como DataQuality.ESTIMATED.
"""
from __future__ import annotations
from typing import Optional

from ...domain.vehicles.models import AxleConfig, AxleInfo, AxleType, EstimationMethod, DataQuality


# Mapa category_id → configuración de ejes por defecto (del catálogo)
DEFAULT_AXLE_BY_CATEGORY: dict[str, tuple[int, list[str]]] = {
    "MOTO": (2, ["simple_single", "simple_single"]),
    "AUTO": (2, ["simple_single", "simple_single"]),
    "CAMIONETA": (2, ["simple_single", "simple_dual"]),
    "MINIBUS": (2, ["simple_single", "simple_dual"]),
    "BUS": (2, ["simple_single", "simple_dual"]),
    "C2": (2, ["simple_single", "simple_dual"]),
    "C3": (3, ["simple_single", "simple_dual", "simple_dual"]),
    "TRACTOCAMION": (3, ["simple_single", "tandem", "tandem"]),
    "ARTICULADO": (5, ["simple_single", "tandem", "tandem", "tandem", "tandem"]),
    "OTRO_PESADO": (2, ["simple_single", "simple_dual"]),
}


class AxleEstimator:
    """
    Estima la configuración de ejes a partir de la categoría vehicular.
    En Fase 1 se puede mejorar con análisis geométrico del bbox.
    """

    def estimate_from_category(
        self,
        category_id: str,
        confidence: float = 0.60,
    ) -> AxleConfig:
        """
        Retorna la configuración de ejes por defecto para la categoría.
        Fuente: catálogo vehicle_catalog.yaml
        Calidad: ESTIMATED (del catálogo, no medido)
        """
        if category_id not in DEFAULT_AXLE_BY_CATEGORY:
            category_id = "C2"  # fallback

        axle_count, axle_types = DEFAULT_AXLE_BY_CATEGORY[category_id]
        axles = [
            AxleInfo(
                axle_number=i + 1,
                axle_type=AxleType(atype),
                load_kn=None,  # no disponible sin WIM
                load_quality=DataQuality.ESTIMATED,
                estimation_method=EstimationMethod.CATALOG,
                confidence=confidence,
                notes="Configuración por defecto del catálogo ABC Bolivia",
            )
            for i, atype in enumerate(axle_types)
        ]

        return AxleConfig(
            axle_count=axle_count,
            axles=axles,
            estimation_method=EstimationMethod.CATALOG,
            confidence=confidence,
            data_quality=DataQuality.ESTIMATED,
            notes="Estimado desde catálogo por categoría. No es medición directa.",
        )
