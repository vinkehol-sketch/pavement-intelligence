"""
Modelos de dominio para aforos y tránsito vehicular.

Clases principales:
- ``HourlyCount``: Conteo vehicular por hora y categoría.
- ``TrafficSurvey``: Aforo vehicular completo.
- ``TrafficProjection``: Proyección de tránsito para periodo de diseño.

No dependen de ninguna librería externa. Solo stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional
import uuid


# ===========================================================================
# Enumeraciones
# ===========================================================================

class SurveyType(str, Enum):
    """Tipo de aforo vehicular."""

    VIDEO = "video"             # análisis automático de video
    MANUAL = "manual"           # conteo manual en campo
    COMBINED = "combinado"      # combinación de video + manual
    SIMULATED = "simulado"      # datos sintéticos (para desarrollo/pruebas)


class CountingDirection(str, Enum):
    """Sentidos contados en el aforo."""

    BOTH = "ambos_sentidos"
    ASCENDING_ONLY = "solo_ascendente"
    DESCENDING_ONLY = "solo_descendente"


# ===========================================================================
# Modelos de datos
# ===========================================================================

@dataclass
class HourlyCount:
    """
    Conteo vehicular por hora, categoría y sentido.

    Representa una celda de la matriz de aforo horario. Utilizada para
    construir la distribución temporal del tráfico a lo largo del día.

    Attributes:
        hour: Hora del día (0–23, donde 0 = 00:00–01:00).
        category_id: ID de categoría vehicular del catálogo ABC.
        direction: Sentido de circulación ("ascendente", "descendente", etc.).
        count: Número de vehículos contados.
        data_quality: Calidad/origen del dato.
    """

    hour: int                        # 0–23
    category_id: str
    direction: str
    count: int
    data_quality: str = "simulado"

    def __post_init__(self) -> None:
        if not (0 <= self.hour <= 23):
            raise ValueError(f"La hora debe estar entre 0 y 23. Recibido: {self.hour}")
        if self.count < 0:
            raise ValueError(f"El conteo no puede ser negativo. Recibido: {self.count}")


@dataclass
class TrafficSurvey:
    """
    Aforo vehicular completo.

    Representa un estudio de conteo vehicular con toda la información necesaria
    para calcular el TPDA (Tráfico Promedio Diario Anual) y los ESALs de diseño.

    Attributes:
        id: Identificador único del aforo (UUID v4).
        road_segment_id: ID del tramo vial donde se realizó el aforo.
        name: Nombre descriptivo del aforo (ej: "Aforo AV. Montes - Julio 2026").
        start_datetime: Fecha y hora de inicio del conteo.
        end_datetime: Fecha y hora de finalización del conteo.
        survey_duration_hours: Duración del conteo en horas.
        survey_type: Tipo de aforo (video, manual, combinado).
        counting_direction: Sentidos contados.
        location_description: Descripción textual del punto de aforo.
        hourly_counts: Lista de conteos horarios desagregados por categoría.
        total_by_category: Conteo total por categoría vehicular (agregado).
        tpda: Tráfico Promedio Diario Anual (calculado o estimado).
        tpda_method: Método de cálculo del TPDA.
        expansion_factor: Factor de expansión horaria a diaria.
        directional_factor: Factor de distribución direccional (D).
        lane_distribution_factor: Factor de distribución por carril (L).
        growth_rate_percent: Tasa de crecimiento vehicular anual (%).
        data_quality: Calidad global del dato del aforo.
        notes: Observaciones del estudio.
        created_at: Fecha de creación del registro.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    road_segment_id: Optional[str] = None
    name: str = ""
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    survey_duration_hours: float = 24.0
    survey_type: SurveyType = SurveyType.SIMULATED
    counting_direction: CountingDirection = CountingDirection.BOTH
    location_description: str = ""
    hourly_counts: list[HourlyCount] = field(default_factory=list)
    total_by_category: dict[str, int] = field(default_factory=dict)
    tpda: Optional[float] = None
    tpda_method: str = ""
    expansion_factor: float = 1.0
    directional_factor: float = 0.50     # D: fracción del tráfico en el carril de diseño
    lane_distribution_factor: float = 1.0  # L: fracción del tráfico en el carril de diseño
    growth_rate_percent: float = 4.0
    data_quality: str = "simulado"
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def total_vehicles(self) -> int:
        """Total de vehículos contados en todas las categorías."""
        return sum(self.total_by_category.values())

    @property
    def heavy_vehicle_count(self) -> int:
        """
        Total de vehículos pesados (BUS, C2, C3, TRACTOCAMION, ARTICULADO, OTRO_PESADO).
        """
        heavy_ids = {"BUS", "C2", "C3", "TRACTOCAMION", "ARTICULADO", "OTRO_PESADO"}
        return sum(
            count for cat_id, count in self.total_by_category.items()
            if cat_id in heavy_ids
        )

    @property
    def heavy_vehicle_percent(self) -> float:
        """Porcentaje de vehículos pesados sobre el total."""
        total = self.total_vehicles
        if total == 0:
            return 0.0
        return (self.heavy_vehicle_count / total) * 100.0

    @property
    def design_lane_tpda(self) -> Optional[float]:
        """
        TPDA en el carril de diseño.

        TPDA_diseño = TPDA × D × L

        Retorna ``None`` si el TPDA no ha sido calculado.
        """
        if self.tpda is None:
            return None
        return self.tpda * self.directional_factor * self.lane_distribution_factor

    def get_hourly_total(self, hour: int) -> int:
        """
        Retorna el total de vehículos en una hora específica (todos los sentidos y categorías).

        Args:
            hour: Hora del día (0–23).

        Returns:
            Número total de vehículos en esa hora.
        """
        return sum(hc.count for hc in self.hourly_counts if hc.hour == hour)

    def get_peak_hour(self) -> Optional[int]:
        """Retorna la hora pico (con mayor volumen). ``None`` si no hay datos."""
        if not self.hourly_counts:
            return None
        totals = {h: self.get_hourly_total(h) for h in range(24)}
        return max(totals, key=lambda h: totals[h])

    def to_dict(self) -> dict:
        """Serializa el aforo a diccionario para reportes y exportación."""
        return {
            "id": self.id,
            "nombre": self.name,
            "tramo_id": self.road_segment_id,
            "tipo": self.survey_type.value,
            "duracion_h": self.survey_duration_hours,
            "total_vehiculos": self.total_vehicles,
            "pesados_percent": round(self.heavy_vehicle_percent, 1),
            "tpda": self.tpda,
            "tasa_crecimiento_pct": self.growth_rate_percent,
            "calidad_dato": self.data_quality,
            "notas": self.notes,
        }


@dataclass
class TrafficProjection:
    """
    Proyección de tránsito para el periodo de diseño.

    Calcula el TPDA proyectado año a año y el TPDA de diseño al final del periodo,
    usando crecimiento compuesto. Usado como entrada para el cálculo de ESALs acumulados.

    Attributes:
        id: Identificador único (UUID v4).
        survey_id: ID del aforo base.
        base_tpda: TPDA base (año 0).
        growth_rate_percent: Tasa de crecimiento anual (%).
        design_period_years: Periodo de diseño (años).
        projected_tpda_by_year: TPDA proyectado por año {año: tpda}.
        design_tpda: TPDA al final del periodo de diseño.
        method: Método de proyección utilizado.
        notes: Observaciones.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    survey_id: str = ""
    base_tpda: float = 0.0
    growth_rate_percent: float = 4.0
    design_period_years: int = 20
    projected_tpda_by_year: dict[int, float] = field(default_factory=dict)
    design_tpda: float = 0.0        # TPDA al final del periodo
    method: str = "tasa_crecimiento_compuesto"
    notes: str = ""

    def calculate_projection(self) -> None:
        """
        Calcula la proyección de TPDA año a año con tasa de crecimiento compuesto.

        Fórmula: TPDA_n = TPDA_0 × (1 + r/100)^n

        donde r es la tasa de crecimiento en porcentaje.
        """
        r = self.growth_rate_percent / 100.0
        self.projected_tpda_by_year = {}
        for year in range(self.design_period_years + 1):
            self.projected_tpda_by_year[year] = self.base_tpda * ((1 + r) ** year)
        self.design_tpda = self.projected_tpda_by_year[self.design_period_years]

    @property
    def growth_factor(self) -> float:
        """
        Factor de crecimiento acumulado (para cálculo de ESALs totales).

        Fórmula: G = [(1 + r)^n - 1] / r  (si r > 0)
                 G = n                      (si r = 0)
        """
        r = self.growth_rate_percent / 100.0
        n = self.design_period_years
        if r == 0:
            return float(n)
        return ((1 + r) ** n - 1) / r
