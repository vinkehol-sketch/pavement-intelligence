"""
Cargador de catálogos YAML para Pavement Intelligence.

Proporciona funciones para cargar los catálogos de configuración del sistema
(vehículos, ejes, factores ESAL) desde archivos YAML.

Requiere ``PyYAML`` como dependencia (declarada en ``pyproject.toml``).
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

# PyYAML se usa SOLO en esta capa de utilidades (no en domain/)
try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


class CatalogLoadError(Exception):
    """Error al cargar un catálogo YAML."""
    pass


def load_yaml_catalog(path: str | Path) -> dict[str, Any]:
    """
    Carga y parsea un archivo YAML de catálogo.

    Args:
        path: Ruta al archivo YAML (absoluta o relativa al directorio de trabajo).

    Returns:
        Diccionario con el contenido del catálogo.

    Raises:
        CatalogLoadError: Si el archivo no existe, no puede leerse o tiene
                          errores de sintaxis YAML.
        ImportError: Si PyYAML no está instalado.

    Example:
        >>> catalog = load_yaml_catalog("src/pavement_intelligence/config/vehicle_catalog.yaml")
        >>> categories = catalog["categories"]
    """
    if not _YAML_AVAILABLE:
        raise ImportError(
            "PyYAML no está instalado. Instalar con: pip install pyyaml"
        )

    catalog_path = Path(path)

    if not catalog_path.exists():
        raise CatalogLoadError(
            f"Catálogo no encontrado: {catalog_path.resolve()}\n"
            "Verificar la ruta en la configuración (settings.py) o en el archivo .env."
        )

    if not catalog_path.is_file():
        raise CatalogLoadError(
            f"La ruta no corresponde a un archivo: {catalog_path.resolve()}"
        )

    try:
        with catalog_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise CatalogLoadError(
            f"Error de sintaxis YAML en {catalog_path}: {exc}"
        ) from exc
    except OSError as exc:
        raise CatalogLoadError(
            f"No se pudo leer el archivo {catalog_path}: {exc}"
        ) from exc

    if data is None:
        logger.warning("El catálogo '%s' está vacío.", catalog_path)
        return {}

    if not isinstance(data, dict):
        raise CatalogLoadError(
            f"El catálogo '{catalog_path}' debe ser un YAML de tipo dict (mapping), "
            f"pero se obtuvo: {type(data).__name__}"
        )

    logger.debug("Catálogo cargado exitosamente: %s", catalog_path.name)
    return data


@lru_cache(maxsize=16)
def load_yaml_catalog_cached(path: str) -> dict[str, Any]:
    """
    Versión cacheada de ``load_yaml_catalog``.

    Carga el catálogo desde disco solo la primera vez; las siguientes
    llamadas con la misma ruta retornan el resultado desde memoria.

    .. note::
        El caché no detecta cambios en el archivo. Usar ``invalidate_catalog_cache()``
        si el archivo fue modificado durante la ejecución.

    Args:
        path: Ruta al archivo YAML (como string para compatibilidad con lru_cache).

    Returns:
        Diccionario con el contenido del catálogo (cacheado).
    """
    return load_yaml_catalog(path)


def invalidate_catalog_cache() -> None:
    """
    Invalida el caché de catálogos.

    Útil en tests o cuando los archivos de catálogo son modificados
    durante la ejecución del sistema.
    """
    load_yaml_catalog_cached.cache_clear()
    logger.debug("Caché de catálogos invalidado.")


def get_vehicle_categories(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extrae la lista de categorías vehiculares del catálogo.

    Args:
        catalog: Diccionario cargado desde ``vehicle_catalog.yaml``.

    Returns:
        Lista de diccionarios, uno por categoría vehicular.

    Raises:
        CatalogLoadError: Si el catálogo no tiene la clave ``categories``.
    """
    if "categories" not in catalog:
        raise CatalogLoadError(
            "El catálogo de vehículos no contiene la clave 'categories'. "
            "Verificar el formato de vehicle_catalog.yaml."
        )
    return catalog["categories"]


def get_vehicle_category_by_id(
    catalog: dict[str, Any],
    category_id: str,
) -> dict[str, Any] | None:
    """
    Busca una categoría vehicular por su ID.

    Args:
        catalog: Diccionario cargado desde ``vehicle_catalog.yaml``.
        category_id: ID de la categoría (ej: ``"C2"``, ``"BUS"``).

    Returns:
        Diccionario de la categoría, o ``None`` si no se encuentra.
    """
    for category in get_vehicle_categories(catalog):
        if category.get("id") == category_id:
            return category
    return None


def get_axle_types(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extrae la lista de tipos de eje del catálogo de ejes.

    Args:
        catalog: Diccionario cargado desde ``axle_catalog.yaml``.

    Returns:
        Lista de diccionarios, uno por tipo de eje.

    Raises:
        CatalogLoadError: Si el catálogo no tiene la clave ``axle_types``.
    """
    if "axle_types" not in catalog:
        raise CatalogLoadError(
            "El catálogo de ejes no contiene la clave 'axle_types'. "
            "Verificar el formato de axle_catalog.yaml."
        )
    return catalog["axle_types"]


def get_vehicle_fec(
    esal_catalog: dict[str, Any],
    category_id: str,
) -> float | None:
    """
    Obtiene el Factor de Equivalencia de Carga (FEC) para una categoría vehicular.

    Args:
        esal_catalog: Diccionario cargado desde ``esal_factors.yaml``.
        category_id: ID de la categoría vehicular (ej: ``"C2"``).

    Returns:
        FEC total del vehículo, o ``None`` si la categoría no está en el catálogo.
    """
    vehicle_fec = esal_catalog.get("vehicle_fec", {})
    return vehicle_fec.get(category_id)
