"""
Modelos de dominio para diseño de pavimento flexible AASHTO 93.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DesignLayer:
    """
    Capa estructural del pavimento.
    SN_i = a_i × D_i(pulgadas) × m_i
    Referencia: AASHTO Guide for Design of Pavement Structures (1993), Capítulo 3.
    """
    layer_number: int
    material_name: str
    thickness_cm: float
    structural_coefficient: float
    drainage_coefficient: float
    contribution_to_sn: float
    material_code: Optional[str] = None
    notes: Optional[str] = None

    @property
    def thickness_inches(self) -> float:
        """Espesor en pulgadas."""
        return self.thickness_cm / 2.54


@dataclass
class FlexiblePavementDesign:
    """
    Resultado del diseño de pavimento flexible por método AASHTO 93.
    Ecuación: log₁₀(W₁₈) = Z_R×S₀ + 9.36×log₁₀(SN+1) - 0.20
              + log₁₀(ΔPSI/2.7) / [0.40 + 1094/(SN+1)⁵·¹⁹]
              + 2.32×log₁₀(M_R) - 8.07
    Referencia: AASHTO Guide for Design of Pavement Structures (1993).
    """
    design_esal_w18: float
    reliability_percent: float
    overall_std_dev_so: float
    initial_psi: float
    terminal_psi: float
    delta_psi: float
    subgrade_cbr_percent: float
    design_period_years: int
    mr_source: str
    z_r: float = 0.0
    subgrade_mr_psi: float = 0.0
    required_sn: float = 0.0
    provided_sn: float = 0.0
    design_converged: bool = False
    iterations: int = 0
    layers: list[DesignLayer] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_quality: str = "calculado"

    @property
    def sn_check_ok(self) -> bool:
        """Verifica que el SN provisto supere al requerido."""
        return self.provided_sn >= self.required_sn

    @property
    def total_thickness_cm(self) -> float:
        """Espesor total del paquete estructural en cm."""
        return sum(l.thickness_cm for l in self.layers)

    @property
    def subgrade_mr_mpa(self) -> float:
        """Módulo resiliente de la subrasante en MPa."""
        return round(self.subgrade_mr_psi * 0.006895, 1)
