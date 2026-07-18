"""Servicio de geotecnia."""

# ==============================================================================
# ⚠️ ADVERTENCIA DE VALIDACIÓN
# La metodología y fórmulas de este módulo están pendientes de validación documental.
# Las ecuaciones deben contrastarse con las fuentes técnicas (normativa boliviana/AASHTO).
# NO DEBEN utilizarse todavía para resultados oficiales ni diseños reales.
# Las unidades y supuestos deberán quedar debidamente documentados.
# Se requerirá validación posterior mediante ejercicios resueltos manualmente.
# ==============================================================================

def get_design_cbr(samples: list[float], percentile: float = 75.0) -> float:
    if not samples: return 0.0
    samples.sort()
    return samples[int(len(samples) * (percentile/100.0))]
