"""
Utilidades para registrar y verificar calidad y origen de los datos.

Proporciona la clase ``TracedValue`` para envolver cualquier valor numérico
o de cadena con metadatos de trazabilidad completos (fuente, fórmula, referencia).

Este módulo es fundamental para la auditabilidad del sistema, especialmente
en resultados de ingeniería que pueden ser usados en decisiones de inversión.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DataSource(str, Enum):
    """
    Fuente y calidad del dato.

    Permite clasificar cada valor del sistema según su origen y confiabilidad,
    desde el más confiable (MEASURED) hasta el menos confiable (SIMULATED).
    """

    MEASURED = "medido"       # dato de instrumento, ensayo o sensor calibrado
    ESTIMATED = "estimado"    # cálculo indirecto, correlación empírica o modelo
    IMPORTED = "importado"    # cargado desde archivo externo (CSV, Excel, WIM)
    SIMULATED = "simulado"    # dato sintético o generado para pruebas
    CALCULATED = "calculado"  # resultado de fórmula con trazabilidad completa
    MANUAL = "manual"         # ingresado manualmente por el operador de campo

    @property
    def reliability_rank(self) -> int:
        """
        Rango de confiabilidad (mayor = más confiable).

        Útil para comparar la calidad de dos valores y elegir el mejor.
        """
        ranking = {
            DataSource.MEASURED: 5,
            DataSource.CALCULATED: 4,
            DataSource.IMPORTED: 3,
            DataSource.MANUAL: 2,
            DataSource.ESTIMATED: 1,
            DataSource.SIMULATED: 0,
        }
        return ranking.get(self, 0)


@dataclass
class TracedValue:
    """
    Valor con trazabilidad completa.

    Envuelve cualquier dato (numérico, string, etc.) con metadatos que permiten
    auditar su origen, calidad, fórmula aplicada y referencia normativa.

    Attributes:
        value: El valor en sí (cualquier tipo).
        unit: Unidad del valor (ej: "kN", "psi", "MPa", "%", "km/h").
        source: Fuente/calidad del dato según ``DataSource``.
        confidence: Confianza en el dato, entre 0.0 y 1.0.
        formula: Nombre o expresión de la fórmula usada para calcularlo.
        reference: Referencia normativa o bibliográfica (ej: "AASHTO 93 Eq. 1.1").
        notes: Observaciones adicionales.

    Example:
        >>> mr = TracedValue(
        ...     value=4500.0,
        ...     unit="psi",
        ...     source=DataSource.ESTIMATED,
        ...     confidence=0.7,
        ...     formula="MR = 1500 × CBR",
        ...     reference="AASHTO Guide 1993, Apéndice EE",
        ... )
        >>> print(mr)
        TracedValue(4500.0 psi, fuente=estimado, confianza=70%)
    """

    value: Any
    unit: str
    source: DataSource
    confidence: float = 1.0    # 0.0 a 1.0
    formula: str = ""          # nombre o expresión de la fórmula
    reference: str = ""        # referencia normativa
    notes: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"La confianza debe estar entre 0.0 y 1.0. Recibido: {self.confidence}"
            )

    def __repr__(self) -> str:
        return (
            f"TracedValue({self.value} {self.unit}, "
            f"fuente={self.source.value}, confianza={self.confidence:.0%})"
        )

    def __str__(self) -> str:
        return f"{self.value} {self.unit} [{self.source.value}]"

    @property
    def is_reliable(self) -> bool:
        """Indica si el dato tiene una confianza aceptable (≥ 0.7)."""
        return self.confidence >= 0.7

    @property
    def reliability_label(self) -> str:
        """Etiqueta de confiabilidad para reportes."""
        if self.confidence >= 0.9:
            return "Alta"
        if self.confidence >= 0.7:
            return "Media-Alta"
        if self.confidence >= 0.5:
            return "Media"
        if self.confidence >= 0.3:
            return "Media-Baja"
        return "Baja"

    def to_dict(self) -> dict:
        """Serializa el valor con trazabilidad a diccionario."""
        return {
            "valor": self.value,
            "unidad": self.unit,
            "fuente": self.source.value,
            "confianza": self.confidence,
            "confiabilidad": self.reliability_label,
            "formula": self.formula,
            "referencia": self.reference,
            "notas": self.notes,
        }


def best_value(*traced_values: TracedValue) -> TracedValue:
    """
    Retorna el ``TracedValue`` con mayor confiabilidad.

    En caso de empate en confianza, prefiere el de mayor rango de fuente.

    Args:
        *traced_values: Uno o más ``TracedValue`` a comparar.

    Returns:
        El ``TracedValue`` con mayor confianza y calidad de fuente.

    Raises:
        ValueError: Si no se pasan valores.
    """
    if not traced_values:
        raise ValueError("Debe proporcionar al menos un TracedValue.")
    return max(
        traced_values,
        key=lambda tv: (tv.confidence, tv.source.reliability_rank),
    )
