"""Catálogo central y validación pura de categoría vehicular contra ejes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pavement_intelligence.weighing.workflow import AxleGroupLoad


AXLE_CONFIGURATION_CATALOG_VERSION = "BO-ABC-DS24327-DEMO-1.0"
AXLE_CONFIGURATION_CATALOG_SOURCE = (
    "docs/clasificacion_abc_ejes.md; docs/configuraciones_ejes.md; "
    "vehicle_catalog.yaml 1.0.0 (catálogo configurable, pendiente de fuente primaria)"
)

# Los patrones representan grupos ordenados, no ejes físicos individuales.
CONFIRMED_CONFIGURATION_PATTERNS: dict[str, tuple[tuple[str, ...], ...]] = {
    "C2": (
        ("simple_single", "simple_dual"),
        ("simple_single", "simple_single"),
    ),
    "C3": (
        ("simple_single", "tandem"),
        ("simple_single", "simple_dual", "simple_dual"),
    ),
    "TRACTOCAMION": (("simple_single", "tandem"),),
    "ARTICULADO": (
        ("simple_single", "simple_dual", "tandem"),  # T2-S2
        ("simple_single", "tandem", "tandem"),       # T3-S2
        ("simple_single", "tandem", "tridem"),       # T3-S3
    ),
}
UNCONFIRMED_STRUCTURAL_CATEGORIES = frozenset({"BUS", "OTRO_PESADO"})
NON_STRUCTURAL_CATEGORIES = frozenset({"MOTO", "AUTO", "CAMIONETA", "MINIBUS"})


@dataclass(frozen=True)
class AxleConfigurationValidation:
    is_valid: bool
    category: str
    received_configuration: tuple[str, ...]
    expected_configurations: tuple[tuple[str, ...], ...]
    error_codes: tuple[str, ...]
    messages: tuple[str, ...]
    warnings: tuple[str, ...]
    catalog_version: str = AXLE_CONFIGURATION_CATALOG_VERSION
    catalog_source: str = AXLE_CONFIGURATION_CATALOG_SOURCE


def validate_category_axle_configuration(
    category: str, axle_groups: Iterable[AxleGroupLoad]
) -> AxleConfigurationValidation:
    """Valida grupos ordenados y distingue su multiplicidad de ejes físicos."""
    groups = tuple(axle_groups)
    received = tuple(group.axle_type for group in groups)
    expected = CONFIRMED_CONFIGURATION_PATTERNS.get(category, ())
    errors: list[str] = []
    messages: list[str] = []
    warnings: list[str] = []

    positions = tuple(group.position for group in groups)
    if not groups:
        errors.append("CONFIGURACION_VACIA")
        messages.append("No se registraron grupos de ejes.")
    elif positions != tuple(range(1, len(groups) + 1)):
        errors.append("ORDEN_DE_GRUPOS_INVALIDO")
        messages.append(
            f"{category}: posiciones recibidas {positions}; se esperaba orden consecutivo desde 1."
        )

    if category == "CAMION":
        errors.append("CAMION_NO_RECLASIFICADO")
        messages.append("CAMION no es una categoría estructural confirmada.")
    elif category in NON_STRUCTURAL_CATEGORIES:
        errors.append("CATEGORIA_NO_ESTRUCTURAL")
        messages.append(f"{category} no está habilitada para consolidar ESAL estructural.")
    elif category in UNCONFIRMED_STRUCTURAL_CATEGORIES:
        errors.append("CONFIGURACION_NO_CONFIRMADA")
        messages.append(
            f"{category}: la documentación disponible no define una configuración única segura."
        )
        warnings.append("Se requiere verificación física y fuente normativa primaria.")
    elif not expected:
        errors.append("CATEGORIA_DESCONOCIDA")
        messages.append(f"{category}: no existe una regla confirmada en el catálogo {AXLE_CONFIGURATION_CATALOG_VERSION}.")
    elif received not in expected:
        errors.append("CONFIGURACION_INCOMPATIBLE")
        messages.append(
            f"{category}: configuración recibida {received}; esperada una de {expected}. "
            "La cantidad de grupos no sustituye el total de ejes físicos."
        )

    return AxleConfigurationValidation(
        is_valid=not errors,
        category=category,
        received_configuration=received,
        expected_configurations=expected,
        error_codes=tuple(errors),
        messages=tuple(messages),
        warnings=tuple(warnings),
    )
