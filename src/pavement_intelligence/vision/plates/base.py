"""
Interfaz abstracta para reconocimiento de placas vehiculares (ANPR).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class PlateResult:
    """Resultado de lectura de placa."""
    text_raw: Optional[str]       # texto OCR crudo (NUNCA almacenar sin consentimiento)
    text_hash: Optional[str]      # hash SHA-256 truncado (para almacenamiento)
    confidence: float             # confianza de lectura OCR (0.0 a 1.0)
    bbox: Optional[tuple[float, float, float, float]]  # bbox de la placa
    is_anonymized: bool = True    # siempre True por defecto


class AbstractPlateReader(ABC):
    """
    Contrato para lectores de placas.
    Implementaciones: PaddleOCRPlateReader.
    ADVERTENCIA: Las placas son datos personales. Almacenar solo hashes.
    """

    @abstractmethod
    def detect_and_read(
        self,
        frame: np.ndarray,
        vehicle_bbox: tuple[float, float, float, float],
    ) -> Optional[PlateResult]:
        """Detecta y lee la placa en la región del vehículo."""
        ...
