"""Modelos de dominio para vehículos."""
from dataclasses import dataclass, field
from enum import Enum
import uuid

class DataQuality(str, Enum):
    MEASURED = "medido"
    ESTIMATED = "estimado"
    SIMULATED = "simulado"

@dataclass
class Vehicle:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    vehicle_category_id: str = "AUTO"
    data_source: DataQuality = DataQuality.ESTIMATED
