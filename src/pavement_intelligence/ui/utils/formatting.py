"""Formateo seguro para valores técnicos del dashboard."""
from __future__ import annotations

from math import isfinite


def format_unit(value: float | int | None, unit: str, decimals: int = 0) -> str:
    """Formatea una magnitud finita o devuelve un marcador neutral."""
    if value is None or isinstance(value, bool) or not isfinite(float(value)):
        return "—"
    rendered = f"{float(value):,.{decimals}f}"
    return f"{rendered} {unit}".strip()
