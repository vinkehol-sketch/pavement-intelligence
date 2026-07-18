"""
Validadores de parámetros de entrada para el sistema Pavement Intelligence.

Todos los validadores retornan un ``ValidationResult`` que puede contener
errores (que bloquean el cálculo) y advertencias (que no bloquean pero
informan al usuario sobre posibles problemas con los datos).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ===========================================================================
# Resultado de validación
# ===========================================================================

@dataclass
class ValidationResult:
    """
    Resultado de una validación de parámetro.

    Attributes:
        is_valid: ``True`` si no hay errores (puede haber advertencias).
        errors: Lista de mensajes de error (bloquean el cálculo).
        warnings: Lista de mensajes de advertencia (no bloquean).
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls) -> "ValidationResult":
        """Crea un resultado válido sin errores ni advertencias."""
        return cls(is_valid=True, errors=[], warnings=[])

    def add_error(self, msg: str) -> None:
        """
        Agrega un error y marca el resultado como inválido.

        Args:
            msg: Mensaje descriptivo del error.
        """
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        """
        Agrega una advertencia (no cambia ``is_valid``).

        Args:
            msg: Mensaje descriptivo de la advertencia.
        """
        self.warnings.append(msg)

    def merge(self, other: "ValidationResult") -> None:
        """
        Combina otro ``ValidationResult`` en este.

        Útil para validar múltiples parámetros y acumular todos los errores.
        """
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False

    def __str__(self) -> str:
        lines = []
        if self.errors:
            lines.append(f"ERRORES ({len(self.errors)}):")
            lines.extend(f"  ✗ {e}" for e in self.errors)
        if self.warnings:
            lines.append(f"ADVERTENCIAS ({len(self.warnings)}):")
            lines.extend(f"  ⚠ {w}" for w in self.warnings)
        if not lines:
            return "Válido ✓"
        return "\n".join(lines)


# ===========================================================================
# Validadores individuales
# ===========================================================================

def validate_cbr(cbr: float) -> ValidationResult:
    """
    Valida un valor de CBR de subrasante.

    Args:
        cbr: Valor de CBR en porcentaje (%).

    Returns:
        ``ValidationResult`` con errores y advertencias.
    """
    result = ValidationResult.ok()

    if cbr <= 0:
        result.add_error(
            f"El CBR debe ser mayor que 0%. Valor recibido: {cbr}%"
        )
    elif cbr > 100:
        result.add_error(
            f"El CBR no puede superar el 100%. Valor recibido: {cbr}%"
        )

    if result.is_valid:
        if cbr < 3.0:
            result.add_warning(
                f"CBR muy bajo ({cbr}%): subrasante muy débil (S0). "
                "Considerar estabilización o mejoramiento del suelo."
            )
        elif cbr < 5.0:
            result.add_warning(
                f"CBR bajo ({cbr}%): subrasante mala (S1). "
                "Verificar datos y considerar mejoramiento."
            )
        if cbr > 30.0:
            result.add_warning(
                f"CBR alto ({cbr}%): verificar si corresponde a subrasante "
                "o a un material de capa superior (subbase/base)."
            )

    return result


def validate_reliability(reliability: float) -> ValidationResult:
    """
    Valida el nivel de confiabilidad para diseño AASHTO 93.

    Los valores válidos van del 50% al 99.9% según las tablas de Z_R de AASHTO.

    Args:
        reliability: Nivel de confiabilidad en porcentaje (%).

    Returns:
        ``ValidationResult`` con errores y advertencias.
    """
    result = ValidationResult.ok()

    if reliability < 50.0 or reliability > 99.9:
        result.add_error(
            f"La confiabilidad debe estar entre 50% y 99.9% (AASHTO 93). "
            f"Valor recibido: {reliability}%"
        )

    if result.is_valid:
        if reliability < 75.0:
            result.add_warning(
                f"Confiabilidad baja ({reliability}%): apropiada solo para "
                "vías locales o de bajo volumen de tránsito."
            )
        if reliability > 99.0:
            result.add_warning(
                f"Confiabilidad muy alta ({reliability}%): usualmente reservada "
                "para autopistas o vías de primer orden con alto TPDA."
            )

    return result


def validate_design_period(years: int) -> ValidationResult:
    """
    Valida el periodo de diseño en años.

    Args:
        years: Periodo de diseño en años.

    Returns:
        ``ValidationResult`` con errores y advertencias.
    """
    result = ValidationResult.ok()

    if years < 5:
        result.add_error(
            f"Periodo de diseño demasiado corto: {years} años (mínimo 5 años)."
        )
    if years > 50:
        result.add_warning(
            f"Periodo de diseño muy largo ({years} años). "
            "AASHTO 93 es válido típicamente para periodos de 15 a 30 años."
        )
    if 30 < years <= 50:
        result.add_warning(
            f"Periodo de diseño de {years} años: la proyección de tránsito a "
            "largo plazo introduce mayor incertidumbre. Documentar supuestos."
        )

    return result


def validate_growth_rate(rate_percent: float) -> ValidationResult:
    """
    Valida la tasa de crecimiento vehicular anual.

    Args:
        rate_percent: Tasa de crecimiento en porcentaje anual (%).

    Returns:
        ``ValidationResult`` con errores y advertencias.
    """
    result = ValidationResult.ok()

    if rate_percent < 0:
        result.add_error(
            f"La tasa de crecimiento no puede ser negativa en este módulo. "
            f"Valor recibido: {rate_percent}%"
        )
    if rate_percent == 0:
        result.add_warning(
            "Tasa de crecimiento cero: el tránsito se mantiene constante durante todo el periodo. "
            "Verificar con la fuente del dato."
        )
    if rate_percent > 15:
        result.add_warning(
            f"Tasa de crecimiento muy alta ({rate_percent}%): "
            "verificar la fuente. Tasas > 10% anuales son inusuales en Bolivia."
        )

    return result


def validate_esal(esal_w18: float) -> ValidationResult:
    """
    Valida el número de ESALs de diseño (W18).

    Args:
        esal_w18: ESALs de diseño acumulados en el periodo.

    Returns:
        ``ValidationResult`` con errores y advertencias.
    """
    result = ValidationResult.ok()

    if esal_w18 <= 0:
        result.add_error(
            f"Los ESALs de diseño deben ser mayores que 0. Valor: {esal_w18}"
        )

    if result.is_valid:
        if esal_w18 < 1e4:
            result.add_warning(
                f"ESALs muy bajos ({esal_w18:.0f}): vía de muy bajo volumen. "
                "Verificar el cálculo del TPDA y el factor camión."
            )
        if esal_w18 > 5e7:
            result.add_warning(
                f"ESALs muy altos ({esal_w18:.2e}): verificar parámetros de entrada. "
                "Valores > 50 millones son propios de autopistas de alto tráfico."
            )

    return result


def validate_structural_number(sn: float) -> ValidationResult:
    """
    Valida el número estructural (SN) de diseño AASHTO 93.

    Args:
        sn: Número estructural (adimensional).

    Returns:
        ``ValidationResult`` con errores y advertencias.
    """
    result = ValidationResult.ok()

    if sn <= 0:
        result.add_error(f"El número estructural debe ser positivo. Valor: {sn}")

    if result.is_valid:
        if sn < 1.5:
            result.add_warning(
                f"SN muy bajo ({sn:.2f}): paquete estructural muy delgado. "
                "Verificar parámetros de entrada."
            )
        if sn > 7.0:
            result.add_warning(
                f"SN muy alto ({sn:.2f}): verificar parámetros de entrada. "
                "SN > 7 es inusual incluso para autopistas de alto tráfico."
            )

    return result


def validate_survey_duration(hours: float) -> ValidationResult:
    """
    Valida la duración de un aforo vehicular.

    Args:
        hours: Duración del aforo en horas.

    Returns:
        ``ValidationResult`` con errores y advertencias.
    """
    result = ValidationResult.ok()

    if hours <= 0:
        result.add_error(f"La duración del aforo debe ser positiva. Valor: {hours} horas.")
    if hours > 168:  # 7 días
        result.add_error(
            f"Duración de aforo muy larga ({hours} horas). "
            "El máximo soportado es 168 horas (7 días)."
        )

    if result.is_valid:
        if hours < 12:
            result.add_warning(
                f"Aforo corto ({hours} horas): el factor de expansión a TPDA "
                "introduce mayor incertidumbre. Usar con cautela."
            )
        if hours not in (8, 12, 16, 24, 48, 72, 168):
            result.add_warning(
                f"Duración de aforo no estándar ({hours} horas). "
                "Se recomienda usar duraciones de 8, 12, 16, 24, 48 o 72 horas."
            )

    return result
