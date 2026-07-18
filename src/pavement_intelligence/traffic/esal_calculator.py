"""
Cálculo de Ejes Equivalentes (ESALs) para diseño de pavimento AASHTO 93.

Fórmula general:
    W₁₈ = Σᵢ [TPDAᵢ × 365 × FD × FC × FECᵢ × GF]
donde:
    GF = [(1+r)^n - 1] / r  (factor de crecimiento acumulado)
    FD = factor de distribución direccional
    FC = factor de distribución por carril
    FEC = factor de equivalencia de carga por categoría

Referencia: AASHTO Guide (1993), Capítulo 4;
            ABC Bolivia - Manual de Diseño Vial (2021), Sección 3.5.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .factors import get_vehicle_fec
from ..utils.validators import validate_growth_rate, validate_design_period


@dataclass
class ESALInput:
    """Parámetros de entrada para el cálculo de ESALs."""
    tpda_by_category: dict[str, float]
    """TPDA por categoría vehicular (vehículos/día)."""
    design_period_years: int = 20
    growth_rate_percent: float = 4.0
    directional_factor: float = 0.50
    lane_distribution_factor: float = 1.00
    custom_fec: Optional[dict[str, float]] = None
    data_quality: str = "estimado"
    notes: Optional[str] = None


@dataclass
class ESALResult:
    """Resultado del cálculo de ESALs (W₁₈)."""
    total_esal_w18: float
    esal_by_category: dict[str, float] = field(default_factory=dict)
    growth_factor: float = 0.0
    warnings: list[str] = field(default_factory=list)
    data_quality: str = "estimado"
    formula_applied: str = ""


def calculate_growth_factor(growth_rate_percent: float, years: int) -> float:
    """
    Calcula el factor de crecimiento acumulado de tráfico.
    Para r > 0: GF = [(1 + r)^n - 1] / r
    Para r = 0: GF = n (tráfico constante)
    Referencia: AASHTO Guide (1993), Ec. 4.1.
    """
    r = growth_rate_percent / 100.0
    if abs(r) < 1e-9:
        return float(years)
    return round(((1 + r) ** years - 1) / r, 4)


def calculate_esals(esal_input: ESALInput) -> ESALResult:
    """
    Calcula los ESALs acumulados de diseño W₁₈.
    W₁₈ = Σᵢ [TPDAᵢ × 365 × FD × FC × FECᵢ × GF]
    Referencia: AASHTO Guide (1993), Capítulo 4;
                ABC Bolivia - Manual de Diseño Vial (2021), Sección 3.5.
    """
    warnings: list[str] = []
    gr_val = validate_growth_rate(esal_input.growth_rate_percent)
    dp_val = validate_design_period(esal_input.design_period_years)
    warnings.extend(gr_val.warnings)
    warnings.extend(dp_val.warnings)
    if not dp_val.is_valid:
        return ESALResult(total_esal_w18=0.0, warnings=dp_val.errors + warnings, data_quality="error")

    gf = calculate_growth_factor(esal_input.growth_rate_percent, esal_input.design_period_years)
    esal_by_category: dict[str, float] = {}
    total_w18 = 0.0

    for category, tpda in esal_input.tpda_by_category.items():
        if tpda < 0:
            warnings.append(f"TPDA negativo para categoría '{category}': {tpda}. Se ignora.")
            continue
        fec = (
            esal_input.custom_fec[category]
            if esal_input.custom_fec and category in esal_input.custom_fec
            else get_vehicle_fec(category)
        )
        w18_i = tpda * 365 * esal_input.directional_factor * esal_input.lane_distribution_factor * fec * gf
        esal_by_category[category] = round(w18_i, 0)
        total_w18 += w18_i

    if total_w18 == 0:
        warnings.append("El total de ESALs es cero. Verificar el TPDA y FEC por categoría.")

    formula = (
        f"W₁₈ = Σᵢ [TPDAᵢ × 365 × {esal_input.directional_factor} × "
        f"{esal_input.lane_distribution_factor} × FECᵢ × {gf:.2f}]; "
        f"GF={gf:.2f} (r={esal_input.growth_rate_percent}%, n={esal_input.design_period_years}a). "
        "Ref: AASHTO 93, Cap. 4"
    )
    return ESALResult(
        total_esal_w18=round(total_w18, 0),
        esal_by_category=esal_by_category,
        growth_factor=gf,
        warnings=warnings,
        data_quality=esal_input.data_quality,
        formula_applied=formula,
    )


def esal_sensitivity_analysis(base_input: ESALInput, growth_rates: list[float]) -> dict[float, float]:
    """
    Análisis de sensibilidad de ESALs ante diferentes tasas de crecimiento.
    Útil para evaluar el impacto del crecimiento vehicular en el diseño.
    """
    results: dict[float, float] = {}
    for rate in growth_rates:
        modified = ESALInput(
            tpda_by_category=base_input.tpda_by_category,
            design_period_years=base_input.design_period_years,
            growth_rate_percent=rate,
            directional_factor=base_input.directional_factor,
            lane_distribution_factor=base_input.lane_distribution_factor,
            custom_fec=base_input.custom_fec,
            data_quality=base_input.data_quality,
        )
        result = calculate_esals(modified)
        results[rate] = result.total_esal_w18
    return results
