"""
Factores de carga y confiabilidad para diseño de pavimento AASHTO 93.
Contiene:
    - Factores de equivalencia de carga (LEF/FEC) por tipo de eje
    - Factores de distribución Z_R por nivel de confiabilidad
    - Factor de equivalencia por categoría vehicular
"""
from __future__ import annotations

# TABLA DE FACTORES Z_R — AASHTO 93 Tabla 2.2
# Nivel de confiabilidad R (%) → Factor estadístico Z_R
_ZR_TABLE: dict[float, float] = {
    50.0:  0.000,
    60.0: -0.253,
    70.0: -0.524,
    75.0: -0.674,
    80.0: -0.841,
    85.0: -1.037,
    90.0: -1.282,
    91.0: -1.340,
    92.0: -1.405,
    93.0: -1.476,
    94.0: -1.555,
    95.0: -1.645,
    96.0: -1.751,
    97.0: -1.881,
    98.0: -2.054,
    99.0: -2.327,
    99.9: -3.090,
}


def get_zr_factor(reliability_percent: float) -> float:
    """
    Obtiene el factor Z_R para una confiabilidad dada (interpolación lineal).
    Referencia: AASHTO Guide (1993), Tabla 2.2;
                Huang, Y.H. (2004). Pavement Analysis and Design, p. 265.
    Args:
        reliability_percent: Nivel de confiabilidad R (%)
    Returns:
        Factor Z_R (valor negativo para R > 50%)
    """
    keys = sorted(_ZR_TABLE.keys())
    if reliability_percent in _ZR_TABLE:
        return _ZR_TABLE[reliability_percent]
    for i in range(len(keys) - 1):
        r1, r2 = keys[i], keys[i + 1]
        if r1 < reliability_percent < r2:
            z1, z2 = _ZR_TABLE[r1], _ZR_TABLE[r2]
            t = (reliability_percent - r1) / (r2 - r1)
            return round(z1 + t * (z2 - z1), 4)
    if reliability_percent <= keys[0]:
        return _ZR_TABLE[keys[0]]
    return _ZR_TABLE[keys[-1]]


# FEC por categoría vehicular (fuente: ABC Bolivia - Manual de Diseño Vial)
_VEHICLE_FEC: dict[str, float] = {
    "automovil":         0.0004,
    "taxi":              0.0004,
    "bus_mediano":       1.5,
    "bus_grande":        3.2,
    "camion_2ejes":      2.5,
    "camion_3ejes":      4.0,
    "camion_4ejes":      5.5,
    "semirremolque_5e":  7.0,
    "semirremolque_6e":  9.0,
    "tractor_remolque":  12.0,
    "moto":              0.0001,
    "pickup":            0.002,
    "desconocido":       1.0,
}


def get_vehicle_fec(vehicle_category_id: str) -> float:
    """
    Obtiene el Factor de Equivalencia de Carga (FEC/LEF) para una categoría vehicular.
    Referencia: ABC Bolivia - Manual de Diseño Vial (2021).
    """
    return _VEHICLE_FEC.get(vehicle_category_id.lower(), _VEHICLE_FEC["desconocido"])


def lef_simple_axle(load_kn: float) -> float:
    """
    Aproximación demostrativa para eje simple: ``(P / 80 kN)^4``.

    No es un LEF formal AASHTO 93 dependiente de parámetros estructurales.
    """
    std_load_kn = 80.0  # 18,000 lb
    if load_kn <= 0:
        return 0.0
    return round((load_kn / std_load_kn) ** 4, 4)


def lef_tandem_axle(load_kn: float) -> float:
    """
    Aproximación demostrativa para tándem: ``(P / 142 kN)^4``.

    No es un LEF formal AASHTO 93 dependiente de parámetros estructurales.
    """
    if load_kn <= 0:
        return 0.0
    return round((load_kn / 142.0) ** 4, 4)


def lef_tridem_axle(load_kn: float) -> float:
    """
    Aproximación demostrativa para trídem: ``(P / 213 kN)^4``.

    No es un LEF formal AASHTO 93 dependiente de parámetros estructurales.
    """
    if load_kn <= 0:
        return 0.0
    return round((load_kn / 213.0) ** 4, 4)


def list_vehicle_categories() -> dict[str, float]:
    """Retorna el diccionario completo de categorías y sus FEC."""
    return dict(_VEHICLE_FEC)
