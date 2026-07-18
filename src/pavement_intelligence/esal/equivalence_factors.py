"""Factores de Equivalencia de Carga (FEC)."""

# ==============================================================================
# ⚠️ ADVERTENCIA DE VALIDACIÓN
# La metodología y fórmulas de este módulo están pendientes de validación documental.
# Las ecuaciones deben contrastarse con las fuentes técnicas (normativa boliviana/AASHTO).
# NO DEBEN utilizarse todavía para resultados oficiales ni diseños reales.
# Las unidades y supuestos deberán quedar debidamente documentados.
# Se requerirá validación posterior mediante ejercicios resueltos manualmente.
# ==============================================================================

def calculate_fec(load_kn: float, std_kn: float = 80.0) -> float:
    return (load_kn / std_kn) ** 4.0 if std_kn > 0 else 0.0
