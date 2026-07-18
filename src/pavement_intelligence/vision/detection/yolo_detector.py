"""Implementación del detector YOLOv8 con seguimiento ByteTrack integrado."""
from pathlib import Path
from typing import List, Any, Optional, Dict
import logging
from ultralytics import YOLO

from .base import AbstractDetectorTracker, Detection

logger = logging.getLogger(__name__)

class YOLODetectorTracker(AbstractDetectorTracker):
    """Detector y Tracker basado en Ultralytics YOLOv8.

    Utiliza el modo `track` nativo que implementa ByteTrack o BoT-SORT
    directamente desde la librería y admite configuración para calibración.
    """

    COCO_CLASSES_OF_INTEREST = {
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck"
    }

    CATEGORY_MAPPING = {
        "car": "AUTO",
        "motorcycle": "MOTO",
        "bus": "BUS",
        "truck": "CAMION"
    }

    def __init__(self, model_path: str = "yolov8n.pt", device: str = "cpu", conf_threshold: float = 0.45,
                 image_size: int = 640, allowed_classes: Optional[List[str]] = None, tracker_config: str = "default"):
        resolved_model = self._resolve_model_path(model_path)
        logger.info(f"Cargando modelo YOLO {resolved_model} en {device}")
        self.model = YOLO(resolved_model)
        self.device = device
        self.conf_threshold = conf_threshold
        self.image_size = image_size
        self.allowed_classes = allowed_classes or ["car", "motorcycle", "bus", "truck"]
        self.tracker_config = tracker_config
        self.classes = self._resolve_class_ids(self.allowed_classes)
        self.last_diagnostics: List[Dict[str, Any]] = []

    @staticmethod
    def _resolve_model_path(model_path: str) -> str:
        candidates = []
        if model_path:
            candidates.append(model_path)
            if not Path(model_path).exists():
                candidates.append(Path("data") / "models" / model_path)
                candidates.append(Path("models") / model_path)
                candidates.append(Path.cwd() / model_path)
                candidates.append(Path.cwd() / "data" / "models" / model_path)
        for candidate in candidates:
            if isinstance(candidate, Path):
                if candidate.exists():
                    return str(candidate)
            elif candidate and Path(candidate).exists():
                return str(Path(candidate))
        if model_path and not Path(model_path).exists():
            return str(Path.cwd() / model_path)
        return model_path

    def _resolve_class_ids(self, allowed_classes: List[str]) -> List[int]:
        class_ids = []
        for class_name in allowed_classes:
            for class_id, name in self.COCO_CLASSES_OF_INTEREST.items():
                if name == class_name:
                    class_ids.append(class_id)
                    break
        return class_ids

    def map_class_to_category(self, class_name: str) -> str:
        return self.CATEGORY_MAPPING.get(class_name, "DESCONOCIDO")

    def get_last_diagnostics(self) -> List[Dict[str, Any]]:
        return list(self.last_diagnostics)

    def process_frame(self, frame: Any) -> List[Detection]:
        results = self.model.track(
            frame,
            persist=True,
            conf=self.conf_threshold,
            imgsz=self.image_size,
            device=self.device,
            tracker="bytetrack.yaml" if self.tracker_config == "default" else "bytetrack.yaml",
            classes=self.classes,
            verbose=False
        )

        detections = []
        self.last_diagnostics = []
        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            for i in range(len(boxes)):
                track_id = int(boxes.id[i].item()) if boxes.id is not None else -1
                class_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                class_name = self.model.names[class_id]

                det = Detection(
                    track_id=track_id,
                    class_id=class_id,
                    class_name=class_name,
                    confidence=conf,
                    bbox=(x1, y1, x2, y2)
                )
                detections.append(det)
                self.last_diagnostics.append({
                    "track_id": track_id,
                    "class_name": class_name,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                    "frame_number": None,
                    "reason": "detected"
                })

        return detections
