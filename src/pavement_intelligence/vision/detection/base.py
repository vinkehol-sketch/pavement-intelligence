"""Interfaces base para los módulos de detección y seguimiento de visión."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Any, Optional

@dataclass
class Detection:
    """Representa una detección u objeto rastreado en un fotograma."""
    track_id: Optional[int]
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[float, float, float, float] # x_min, y_min, x_max, y_max
    
    @property
    def centroid(self) -> Tuple[float, float]:
        """Calcula el centro geométrico de la caja delimitadora."""
        x_min, y_min, x_max, y_max = self.bbox
        return (x_min + x_max) / 2.0, (y_min + y_max) / 2.0

class AbstractDetectorTracker(ABC):
    """Interfaz unificada para detección y seguimiento.
    
    Dado que librerías como Ultralytics YOLOv8 integran ambas cosas
    en un solo paso de inferencia (mode=track), es más eficiente 
    tener una interfaz combinada para esta etapa del MVP.
    """
    
    @abstractmethod
    def __init__(self, model_path: str, device: str = "cpu", conf_threshold: float = 0.45):
        pass
        
    @abstractmethod
    def process_frame(self, frame: Any) -> List[Detection]:
        """Procesa un fotograma y devuelve una lista de detecciones con track_id."""
        pass
        
    @abstractmethod
    def map_class_to_category(self, class_name: str) -> str:
        """Mapea una clase del detector (ej. 'car') a la categoría del proyecto (ej. 'AUTO')."""
        pass
