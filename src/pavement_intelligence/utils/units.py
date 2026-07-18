"""Conversión de unidades."""
def cbr_to_mr_psi(cbr_percent: float) -> float:
    if cbr_percent <= 10.0:
        return 1500.0 * cbr_percent
    return 3000.0 * (cbr_percent ** 0.65)
