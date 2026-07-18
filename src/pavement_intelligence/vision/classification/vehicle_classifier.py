"""
Clasificador de vehículos: mapea clases COCO a categorías ABC Bolivia.
Usa el catálogo configurable de vehicle_catalog.yaml.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional


# Mapeo de clase COCO → categoría ABC Bolivia (aproximación inicial)
# Este mapeo debe refinarse con datos reales bolivianos
DEFAULT_COCO_TO_ABC: dict[str, str] = {
    "car": "AUTO",
    "motorcycle": "MOTO",
    "bus": "BUS",       # Puede ser MINIBUS o BUS; requiere análisis de tamaño
    "truck": "C2",      # Requiere análisis de ejes para clasificar C2/C3/ARTICULADO
}


class VehicleClassifier:
    """
    Clasifica vehículos detectados (clases COCO) en categorías ABC Bolivia.
    La clasificación puede refinarse con:
    - Análisis del tamaño del bbox (area en píxeles)
    - Análisis de la relación de aspecto del bbox
    - Estimación del número de ejes (módulo axles)
    """

    def __init__(self, catalog_path: Optional[str] = None):
        self._catalog: dict = {}
        self._coco_map: dict[str, str] = DEFAULT_COCO_TO_ABC.copy()
        if catalog_path:
            self._load_catalog(catalog_path)

    def _load_catalog(self, catalog_path: str) -> None:
        import yaml
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._catalog = data
        # Reconstruir mapa COCO→ABC desde el catálogo
        for cat in data.get("categories", []):
            for yolo_class in cat.get("yolo_classes", []):
                # Si ya existe, no sobreescribir (el primer mapeo gana)
                if yolo_class not in self._coco_map:
                    self._coco_map[yolo_class] = cat["id"]

    def classify(
        self,
        coco_class_name: str,
        bbox_area_px: float = 0.0,
        aspect_ratio: float = 0.0,
        confidence: float = 1.0,
    ) -> tuple[str, float]:
        """
        Clasifica un vehículo en una categoría ABC Bolivia.
        Retorna (category_id, confidence_ajustada).
        """
        base_category = self._coco_map.get(coco_class_name, "AUTO")

        # Refinamiento basado en tamaño (heurístico)
        adjusted_conf = confidence * 0.85  # penalizar por incertidumbre de mapeo

        # Bus vs Minibus: diferenciar por área relativa del bbox
        if coco_class_name == "bus":
            if bbox_area_px > 0 and bbox_area_px < 15000:
                base_category = "MINIBUS"
            else:
                base_category = "BUS"

        # Camión rígido: clasificar C2 por defecto (requiere módulo de ejes para C3+)
        if coco_class_name == "truck":
            if aspect_ratio > 2.5:  # vehículo muy alargado → posible articulado
                base_category = "ARTICULADO"
                adjusted_conf *= 0.60  # baja confianza: necesita módulo de ejes
            else:
                base_category = "C2"

        return base_category, adjusted_conf

    def get_vehicle_class(self, category_id: str) -> str:
        """Retorna la clase del vehículo (liviano/mediano/pesado/especial)."""
        for cat in self._catalog.get("categories", []):
            if cat["id"] == category_id:
                return cat.get("vehicle_class", "desconocido")
        return "desconocido"

    def is_heavy_vehicle(self, category_id: str) -> bool:
        """Retorna True si el vehículo es considerado pesado."""
        heavy_ids = self._catalog.get("heavy_vehicle_ids", ["BUS", "C2", "C3", "TRACTOCAMION", "ARTICULADO", "OTRO_PESADO"])
        return category_id in heavy_ids
