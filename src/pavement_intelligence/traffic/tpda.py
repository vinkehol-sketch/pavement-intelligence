"""Cálculo trazable de TPD y TPDA base.

Este módulo no calcula ESAL. Los factores direccional y de carril se conservan
separados del TPDA base para evitar confundir demanda total con tránsito del
carril de diseño.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from numbers import Real


@dataclass(frozen=True)
class TPDAResult:
    """Resultado del aforo, antes de cualquier proyección de crecimiento."""

    tpda_total: float
    design_tpda: float
    tpda_by_category: dict[str, float] = field(default_factory=dict)
    temporal_expansion_factor: float = 1.0
    seasonal_factor: float = 1.0
    directional_factor: float = 0.5
    lane_distribution_factor: float = 1.0


def _finite_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} debe ser un número real.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} debe ser finito.")
    return number


def calculate_tpda(
    counts_by_category: dict[str, int | float],
    duration_hours: float,
    fdd: float = 0.5,
    *,
    lane_distribution_factor: float = 1.0,
    nocturnity_factor: float | None = None,
    seasonal_factor: float = 1.0,
) -> TPDAResult:
    """Convierte un conteo observado en TPDA base, una sola vez.

    ``counts_by_category`` representa el conteo bruto durante
    ``duration_hours``. Si no se proporciona ``nocturnity_factor``, se adopta
    una expansión uniforme ``24 / duration_hours`` (o el promedio diario para
    aforos de varios días). Si se proporciona, ese factor *sustituye* a
    ``24 / duration_hours``: nunca se multiplican ambos porque ``f_n`` se
    define como ``Q_24h / Q_nh``.

    ``seasonal_factor`` transforma el TPD estimado en TPDA. FDD y FDC solo se
    aplican después para producir ``design_tpda``.
    """
    if not isinstance(counts_by_category, dict):
        raise TypeError("counts_by_category debe ser un diccionario.")

    hours = _finite_number(duration_hours, "duration_hours")
    if hours <= 0:
        raise ValueError("duration_hours debe ser mayor que cero.")

    direction = _finite_number(fdd, "fdd")
    lane = _finite_number(lane_distribution_factor, "lane_distribution_factor")
    seasonal = _finite_number(seasonal_factor, "seasonal_factor")
    if not 0 < direction <= 1:
        raise ValueError("fdd debe estar en el intervalo (0, 1].")
    if not 0 < lane <= 1:
        raise ValueError("lane_distribution_factor debe estar en (0, 1].")
    if seasonal <= 0:
        raise ValueError("seasonal_factor debe ser mayor que cero.")

    if nocturnity_factor is None:
        temporal = 24.0 / hours
    else:
        temporal = _finite_number(nocturnity_factor, "nocturnity_factor")
        if temporal <= 0:
            raise ValueError("nocturnity_factor debe ser mayor que cero.")
        if hours >= 24 and not math.isclose(temporal, 1.0):
            raise ValueError(
                "nocturnity_factor no puede expandir un aforo de 24 horas o más."
            )
        if hours >= 24:
            temporal = 24.0 / hours

    factor = temporal * seasonal
    by_category: dict[str, float] = {}
    for category, raw_count in counts_by_category.items():
        if not isinstance(category, str) or not category.strip():
            raise ValueError("Cada categoría debe tener un identificador no vacío.")
        count = _finite_number(raw_count, f"conteo[{category}]")
        if count < 0:
            raise ValueError(f"El conteo de {category} no puede ser negativo.")
        by_category[category] = count * factor

    total = sum(by_category.values())
    return TPDAResult(
        tpda_total=total,
        design_tpda=total * direction * lane,
        tpda_by_category=by_category,
        temporal_expansion_factor=temporal,
        seasonal_factor=seasonal,
        directional_factor=direction,
        lane_distribution_factor=lane,
    )
