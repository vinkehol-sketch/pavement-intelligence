"""
Modelos de dominio para geotecnia.
Contiene dataclasses para muestras de suelo, ensayos CBR y condición de suelo.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SoilCondition(str, Enum):
    """Condición de saturación para ensayo CBR."""
    SATURATED = "saturado"
    NATURAL = "natural"
    SOAKED = "inmersion"


@dataclass
class CBRTest:
    """
    Resultado de ensayo de Valor de Soporte California (CBR).
    Referencia: AASHTO T 193 / ASTM D1883.
    """
    cbr_value_percent: float
    condition: SoilCondition = SoilCondition.SATURATED
    expansion_percent: float = 0.0
    penetration_mm: float = 2.54
    density_percent: float = 95.0
    notes: Optional[str] = None


@dataclass
class PlasticityData:
    """Límites de Atterberg y plasticidad del suelo."""
    liquid_limit_percent: Optional[float] = None
    plastic_limit_percent: Optional[float] = None

    @property
    def plasticity_index(self) -> Optional[float]:
        """Índice de plasticidad IP = LL - LP."""
        if self.liquid_limit_percent is not None and self.plastic_limit_percent is not None:
            return round(self.liquid_limit_percent - self.plastic_limit_percent, 1)
        return None


@dataclass
class ProctorTest:
    """Resultado de ensayo Proctor."""
    max_dry_density_kn_m3: float
    optimum_moisture_percent: float
    proctor_type: str = "modificado"


@dataclass
class SoilSample:
    """
    Muestra de suelo para diseño de pavimento.
    Agrupa todos los ensayos de laboratorio de una calicata o sondeo.
    """
    sample_id: str
    road_segment_id: Optional[str] = None
    location_description: Optional[str] = None
    chainage_km: Optional[float] = None
    depth_m: float = 1.5
    stratigraphic_description: Optional[str] = None
    natural_moisture_percent: Optional[float] = None
    uscs_classification: Optional[str] = None
    aashto_classification: Optional[str] = None
    group_index: Optional[float] = None
    cbr: Optional[CBRTest] = None
    plasticity: Optional[PlasticityData] = None
    proctor: Optional[ProctorTest] = None
    resilient_modulus_mpa: Optional[float] = None
    water_table_depth_m: Optional[float] = None
    drainage_quality: Optional[str] = None
    is_expansive: bool = False
    is_collapsible: bool = False
    is_organic: bool = False
    data_quality: str = "simulado"
    observations: Optional[str] = None
