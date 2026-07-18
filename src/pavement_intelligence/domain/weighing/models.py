"""
Modelos de dominio para datos de pesaje vehicular.

Clases principales:
- ``AxleLoad``: Carga de un eje individual medido en balanza.
- ``WIMRecord``: Registro completo de pesaje de un vehículo.

No dependen de ninguna librería externa. Solo stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


# ===========================================================================
# Enumeraciones
# ===========================================================================

class WeighingSource(str, Enum):
    """Fuente del dato de pesaje."""

    WIM_STATION = "estacion_wim"         # balanza dinámica permanente (WIM)
    PORTABLE_SCALE = "balanza_portatil"   # balanza portátil estática
    CSV_FILE = "archivo_csv"             # importado desde archivo CSV
    EXCEL_FILE = "archivo_excel"         # importado desde archivo Excel
    MANUAL_ENTRY = "ingreso_manual"      # ingresado manualmente por operador
    SIMULATED = "simulado"               # dato sintético para pruebas


# ===========================================================================
# Modelos de datos
# ===========================================================================

@dataclass
class AxleLoad:
    """
    Carga de un eje individual medido en balanza.

    Attributes:
        axle_number: Número de eje (1 = frontal).
        axle_type: ID del tipo de eje según ``axle_catalog.yaml``.
        load_kn: Carga medida del eje en kN.
        is_legal: ``True`` si no supera el límite legal boliviano,
                  ``False`` si lo supera, ``None`` si no se verificó.
        notes: Observaciones del pesaje.
    """

    axle_number: int
    axle_type: str              # ID del axle_catalog (ej: "simple_dual", "tandem")
    load_kn: float              # carga en kN
    is_legal: Optional[bool] = None  # None = desconocido / no verificado
    notes: str = ""

    def __post_init__(self) -> None:
        if self.load_kn < 0:
            raise ValueError(
                f"La carga del eje {self.axle_number} no puede ser negativa. "
                f"Recibido: {self.load_kn} kN"
            )

    @property
    def load_kip(self) -> float:
        """Carga del eje en kip (para uso con tablas AASHTO en unidades imperiales)."""
        return self.load_kn * 0.22481


@dataclass
class WIMRecord:
    """
    Registro de pesaje de un vehículo.

    Representa la información completa capturada por una estación WIM
    (Weigh-In-Motion) o balanza portátil para un vehículo individual.
    Es la fuente de datos más confiable para el cálculo de ESALs.

    Attributes:
        id: Identificador único (UUID v4).
        source: Fuente del dato de pesaje.
        timestamp: Fecha y hora del pesaje.
        vehicle_category_id: Categoría vehicular ABC Bolivia.
        vehicle_id: ID del vehículo detectado por visión (si se asoció).
        plate_hash: Hash SHA-256 truncado de la placa (anonimizado).
        gross_weight_kn: Peso bruto total del vehículo en kN.
        axle_loads: Lista de cargas por eje.
        speed_kmh: Velocidad del vehículo en el punto de pesaje.
        lane: Carril en que fue pesado.
        road_segment_id: ID del tramo vial.
        confidence: Confianza en el dato (1.0 = WIM calibrado; < 1.0 = estimado).
        data_quality: Calidad del dato.
        original_file: Nombre del archivo de origen (si fue importado).
        notes: Observaciones.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: WeighingSource = WeighingSource.SIMULATED
    timestamp: Optional[datetime] = None
    vehicle_category_id: Optional[str] = None
    vehicle_id: Optional[str] = None      # ID del vehículo detectado (si se asoció)
    plate_hash: Optional[str] = None
    gross_weight_kn: float = 0.0
    axle_loads: list[AxleLoad] = field(default_factory=list)
    speed_kmh: Optional[float] = None
    lane: Optional[int] = None
    road_segment_id: Optional[str] = None
    confidence: float = 1.0              # 1.0 = WIM real; < 1.0 = estimado
    data_quality: str = "simulado"
    original_file: Optional[str] = None
    notes: str = ""

    @property
    def total_axle_load_kn(self) -> float:
        """Suma de cargas por eje en kN."""
        return sum(a.load_kn for a in self.axle_loads)

    @property
    def axle_count(self) -> int:
        """Número de ejes registrados."""
        return len(self.axle_loads)

    @property
    def gross_weight_ton(self) -> float:
        """Peso bruto total en toneladas métricas (1 ton = 9.80665 kN)."""
        return self.gross_weight_kn / 9.80665

    @property
    def is_overloaded(self) -> Optional[bool]:
        """
        Indica si el vehículo supera los límites legales bolivianos (ABC).

        Límites verificados:
        - Eje frontal (simple_single): máx. 53 kN
        - Eje trasero simple_dual: máx. 80 kN
        - Eje tándem: máx. 160 kN
        - Eje trídem: máx. 215 kN
        - Peso bruto total: máx. 450 kN

        Retorna ``None`` si no hay datos de ejes.

        .. warning::
            Verificar con normativa ABC vigente antes de uso legal.
        """
        if not self.axle_loads:
            return None

        # Verificar peso bruto total
        if self.gross_weight_kn > 450.0:
            return True

        # Verificar eje frontal (primer eje = frontal por convención)
        if self.axle_loads[0].load_kn > 53.0:
            return True

        # Verificar ejes traseros según tipo
        legal_limits = {
            "simple_single": 53.0,
            "simple_dual": 80.0,
            "tandem": 160.0,
            "tridem": 215.0,
            "unknown": 80.0,  # valor conservador por defecto
        }
        for axle in self.axle_loads[1:]:
            limit = legal_limits.get(axle.axle_type, 80.0)
            if axle.load_kn > limit:
                return True

        return False

    @property
    def overloaded_axles(self) -> list[AxleLoad]:
        """Lista de ejes que superan los límites legales bolivianos."""
        legal_limits = {
            "simple_single": 53.0,
            "simple_dual": 80.0,
            "tandem": 160.0,
            "tridem": 215.0,
            "unknown": 80.0,
        }
        return [
            axle for axle in self.axle_loads
            if axle.load_kn > legal_limits.get(axle.axle_type, 80.0)
        ]

    def to_dict(self) -> dict:
        """Serializa el registro WIM a diccionario."""
        return {
            "id": self.id,
            "fuente": self.source.value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "categoria": self.vehicle_category_id,
            "vehiculo_id": self.vehicle_id,
            "peso_bruto_kn": self.gross_weight_kn,
            "peso_bruto_ton": round(self.gross_weight_ton, 2),
            "num_ejes": self.axle_count,
            "velocidad_kmh": self.speed_kmh,
            "carril": self.lane,
            "sobrecargado": self.is_overloaded,
            "confianza": self.confidence,
            "calidad_dato": self.data_quality,
            "notas": self.notes,
        }
