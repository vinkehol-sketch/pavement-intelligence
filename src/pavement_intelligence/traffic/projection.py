"""Proyección de tránsito."""

import math
from numbers import Real

# ==============================================================================
# ⚠️ ADVERTENCIA DE VALIDACIÓN
# La metodología y fórmulas de este módulo están pendientes de validación documental.
# Las ecuaciones deben contrastarse con las fuentes técnicas (normativa boliviana/AASHTO).
# NO DEBEN utilizarse todavía para resultados oficiales ni diseños reales.
# Las unidades y supuestos deberán quedar debidamente documentados.
# Se requerirá validación posterior mediante ejercicios resueltos manualmente.
# ==============================================================================

def _validate_projection_inputs(
    base_tpda: float, growth_rate: float, years: int, expansion_factor: float = 1.0
) -> tuple[float, float, int, float]:
    values = {
        "base_tpda": base_tpda,
        "growth_rate": growth_rate,
        "expansion_factor": expansion_factor,
    }
    normalized: dict[str, float] = {}
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{name} debe ser un número real.")
        normalized[name] = float(value)
        if not math.isfinite(normalized[name]):
            raise ValueError(f"{name} debe ser finito.")
    if isinstance(years, bool) or not isinstance(years, int):
        raise TypeError("years debe ser un número entero de años.")
    if normalized["base_tpda"] < 0:
        raise ValueError("El TPDA base no puede ser negativo.")
    if normalized["growth_rate"] < 0:
        raise ValueError("La tasa de crecimiento no puede ser negativa.")
    if years < 0:
        raise ValueError("Los años de diseño no pueden ser negativos.")
    if normalized["expansion_factor"] <= 0:
        raise ValueError("El factor de expansión debe ser mayor que cero.")
    return (
        normalized["base_tpda"],
        normalized["growth_rate"],
        years,
        normalized["expansion_factor"],
    )


def _finite_result(value: float) -> float:
    if not math.isfinite(value):
        raise OverflowError("La proyección excede el rango numérico finito.")
    return value


def project_traffic(base_tpda: float, growth_rate: float, years: int) -> float:
    """Calcula el TPDA final usando crecimiento compuesto (exponencial)."""
    base_tpda, growth_rate, years, _ = _validate_projection_inputs(
        base_tpda, growth_rate, years
    )
    try:
        return _finite_result(base_tpda * ((1 + growth_rate / 100.0) ** years))
    except OverflowError as exc:
        raise OverflowError("La proyección excede el rango numérico finito.") from exc

def project_traffic_linear(
    base_tpda: float,
    growth_rate: float,
    years: int,
    expansion_factor: float = 1.0,
    variant: str = "B"
) -> dict[str, float]:
    """
    Proyección lineal de tránsito para reproducir ejercicios académicos.
    Retorna:
        v_f: Tránsito final
        v_m: Tránsito medio diario
        v_t: Tránsito total acumulado
    """
    base_tpda, growth_rate, years, expansion_factor = _validate_projection_inputs(
        base_tpda, growth_rate, years, expansion_factor
    )
    if variant not in {"A", "B"}:
        raise ValueError("variant debe ser 'A' o 'B'.")
    
    t = growth_rate / 100.0
    
    if variant == "A":
        # Variante A: METODO_REPRODUCCION_DOCUMENTAL
        v_f = (base_tpda * (1.0 + years * t)) * expansion_factor
        v_m = (v_f + base_tpda) / 2.0
    else:
        # Variante B: METODO_BASE_HOMOGENEA (Recomendado)
        v_0c = base_tpda * expansion_factor
        v_f = v_0c * (1.0 + years * t)
        v_m = (v_f + v_0c) / 2.0
        
    v_t = 365.0 * years * v_m
    _finite_result(v_f)
    _finite_result(v_m)
    _finite_result(v_t)
    return {
        "v_f": round(v_f, 4),
        "v_m": round(v_m, 4),
        "v_t": round(v_t, 4)
    }

def project_traffic_exponential(
    base_tpda: float,
    growth_rate: float,
    years: int,
    expansion_factor: float = 1.0
) -> dict[str, float]:
    """
    Proyección exponencial/compuesta estándar AASHTO 93.
    Retorna:
        v_f: Tránsito final
        v_m: Tránsito medio diario (para concordancia de interfaz, igual a v_f)
        v_t: Tránsito total acumulado
    """
    base_tpda, growth_rate, years, expansion_factor = _validate_projection_inputs(
        base_tpda, growth_rate, years, expansion_factor
    )
    
    r = growth_rate / 100.0
    v_0c = base_tpda * expansion_factor
    try:
        growth_multiplier = (1.0 + r) ** years
    except OverflowError as exc:
        raise OverflowError("La proyección excede el rango numérico finito.") from exc
    v_f = v_0c * growth_multiplier
    
    if abs(r) < 1e-9:
        v_t = 365.0 * v_0c * years
    else:
        v_t = 365.0 * v_0c * ((growth_multiplier - 1) / r)

    _finite_result(v_f)
    _finite_result(v_t)
        
    return {
        "v_f": round(v_f, 4),
        "v_m": round(v_f, 4),
        "v_t": round(v_t, 4)
    }
