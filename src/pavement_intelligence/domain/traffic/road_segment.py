"""
Modelo de tramo vial homogéneo.

Un tramo vial es la unidad de análisis espacial del sistema. Todas las mediciones,
aforos, estudios geotécnicos y diseños de pavimento se asocian a un tramo vial.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class RoadSegment:
    """
    Tramo vial homogéneo.

    Representa un tramo de vía con características geométricas y de tránsito
    homogéneas. Es la unidad espacial de referencia para aforos, estudios
    geotécnicos y diseños de pavimento.

    Attributes:
        id: Identificador único (UUID v4).
        name: Nombre descriptivo del tramo.
        description: Descripción ampliada del tramo.
        road_name: Nombre oficial de la vía (ej: "Av. del Ejército", "Ruta 1").
        start_chainage_km: Progresiva inicial (km).
        end_chainage_km: Progresiva final (km).
        length_km: Longitud del tramo en km (0 = calculada desde progresivas).
        lanes_per_direction: Número de carriles por sentido.
        total_lanes: Número total de carriles.
        speed_limit_kmh: Velocidad máxima permitida (km/h). ``None`` = no definida.
        road_class: Clasificación funcional (ej: "primaria", "secundaria", "urbana").
        location_city: Ciudad donde se ubica el tramo.
        location_department: Departamento boliviano.
        location_country: País (por defecto Bolivia).
        latitude_start: Latitud del inicio del tramo.
        longitude_start: Longitud del inicio del tramo.
        latitude_end: Latitud del final del tramo.
        longitude_end: Longitud del final del tramo.
        notes: Observaciones generales.
        created_at: Fecha de creación del registro.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    road_name: str = ""
    start_chainage_km: float = 0.0
    end_chainage_km: float = 0.0
    length_km: float = 0.0
    lanes_per_direction: int = 1
    total_lanes: int = 2
    speed_limit_kmh: Optional[float] = None
    road_class: str = ""              # "primaria" | "secundaria" | "colectora" | "urbana"
    location_city: str = "La Paz"
    location_department: str = "La Paz"
    location_country: str = "Bolivia"
    latitude_start: Optional[float] = None
    longitude_start: Optional[float] = None
    latitude_end: Optional[float] = None
    longitude_end: Optional[float] = None
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def segment_length(self) -> float:
        """
        Longitud del tramo en km.

        Usa ``length_km`` si fue definido explícitamente (> 0),
        de lo contrario calcula desde las progresivas.
        """
        if self.length_km > 0:
            return self.length_km
        return abs(self.end_chainage_km - self.start_chainage_km)

    @property
    def has_coordinates(self) -> bool:
        """Indica si el tramo tiene coordenadas geográficas definidas."""
        return all(
            coord is not None
            for coord in [
                self.latitude_start,
                self.longitude_start,
                self.latitude_end,
                self.longitude_end,
            ]
        )

    @property
    def design_lane_count(self) -> int:
        """
        Número de carriles de diseño.

        Para vías de dos carriles (uno por sentido), el carril de diseño = 1.
        Para vías multilane, se diseña por el carril más cargado.
        """
        return self.lanes_per_direction  # simplificación MVP

    def to_dict(self) -> dict:
        """Serializa el tramo vial a diccionario."""
        return {
            "id": self.id,
            "nombre": self.name,
            "via": self.road_name,
            "progresiva_inicio_km": self.start_chainage_km,
            "progresiva_fin_km": self.end_chainage_km,
            "longitud_km": self.segment_length,
            "carriles_por_sentido": self.lanes_per_direction,
            "carriles_total": self.total_lanes,
            "clasificacion": self.road_class,
            "ciudad": self.location_city,
            "departamento": self.location_department,
            "pais": self.location_country,
            "notas": self.notes,
        }
