"""Orquestador del pipeline de visión para análisis de tráfico."""
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from numbers import Integral
import time
import datetime
import csv
import json
import cv2
import numpy as np
import pandas as pd

from .detection.base import AbstractDetectorTracker
from .counting.virtual_line import VirtualLineCounter, Point

@dataclass
class TrafficEvent:
    """Evento registrado cuando un vehículo cruza la línea."""
    event_id: str
    track_id: int
    original_class: str
    category: str
    confidence: float
    frame_number: int
    video_second: float
    direction: int
    centroid_x: float
    centroid_y: float
    source: str
    processing_date: str
    data_origin: str = "OBSERVADO_POR_VIDEO"
    
    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "track_id": self.track_id,
            "original_class": self.original_class,
            "category": self.category,
            "confidence": round(self.confidence, 4),
            "frame_number": self.frame_number,
            "video_second": round(self.video_second, 2),
            "direction": self.direction,
            "centroid_x": round(self.centroid_x, 1),
            "centroid_y": round(self.centroid_y, 1),
            "source": self.source,
            "processing_date": self.processing_date,
            "data_origin": self.data_origin
        }

class VisionPipeline:
    """Pipeline principal para procesar video y contar tráfico."""

    def __init__(self, detector: AbstractDetectorTracker, line_p1: tuple, line_p2: tuple,
                 tolerance: float = 0.0, cooldown_frames: int = 3, max_state_age_frames: int = 30,
                 min_history_positions: int = 3, min_displacement_pixels: float = 10.0,
                 max_history_gap_frames: int = 10):
        self.detector = detector
        self.counter = VirtualLineCounter(
            Point(line_p1[0], line_p1[1]),
            Point(line_p2[0], line_p2[1]),
            tolerance=tolerance,
            cooldown_frames=cooldown_frames,
            max_state_age_frames=max_state_age_frames,
            min_history_positions=min_history_positions,
            min_displacement_pixels=min_displacement_pixels,
            max_history_gap_frames=max_history_gap_frames,
        )
        self.events: List[TrafficEvent] = []
        self.diagnostics: List[Dict[str, Any]] = []
        self.invalid_track_id_detections = 0

    @staticmethod
    def _valid_track_id(track_id: Any) -> bool:
        return isinstance(track_id, Integral) and not isinstance(track_id, bool) and int(track_id) >= 0

    def get_diagnostics_summary(self) -> Dict[str, Any]:
        return {
            "invalid_track_id_detections": self.invalid_track_id_detections,
            **self.counter.get_diagnostics_summary(),
        }

    def process_frame(self, frame: np.ndarray, frame_number: int, fps: float, source_name: str) -> Tuple[np.ndarray, List[TrafficEvent]]:
        """Procesa un fotograma, actualiza conteos y dibuja visualizaciones.
        
        Devuelve el fotograma dibujado y los nuevos eventos generados en este frame.
        """
        detections = self.detector.process_frame(frame)
        new_events = []
        
        # Dibujar línea virtual
        cv2.line(frame, 
                 (int(self.counter.p1.x), int(self.counter.p1.y)), 
                 (int(self.counter.p2.x), int(self.counter.p2.y)), 
                 (0, 255, 255), 2)
                 
        active_tracks = []
        
        for det in detections:
            centroid = Point(*det.centroid)

            x1, y1, x2, y2 = map(int, det.bbox)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.circle(frame, (int(centroid.x), int(centroid.y)), 4, (0, 0, 255), -1)

            valid_track_id = self._valid_track_id(det.track_id)
            label_id = det.track_id if valid_track_id else "sin_track"
            label = f"ID:{label_id} {self.detector.map_class_to_category(det.class_name)}"
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

            if not valid_track_id:
                self.invalid_track_id_detections += 1
                self.diagnostics.append({
                    "frame_number": frame_number,
                    "track_id": det.track_id,
                    "class_name": det.class_name,
                    "confidence": det.confidence,
                    "bbox": det.bbox,
                    "category": self.detector.map_class_to_category(det.class_name),
                    "cross_result": None,
                    "counting_status": "discarded_invalid_track_id",
                })
                continue

            track_id = int(det.track_id)
            active_tracks.append(track_id)

            cross_result = self.counter.process_point(
                track_id,
                centroid,
                frame_number=frame_number,
                confidence=det.confidence,
                class_name=det.class_name,
            )

            if cross_result is not None:
                stable_class = self.counter.get_stable_class(track_id) or det.class_name
                event = TrafficEvent(
                    event_id=f"evt_{int(time.time()*1000)}_{track_id}",
                    track_id=track_id,
                    original_class=stable_class,
                    category=self.detector.map_class_to_category(stable_class),
                    confidence=self.counter.get_average_confidence(track_id),
                    frame_number=frame_number,
                    video_second=frame_number / fps if fps > 0 else 0.0,
                    direction=cross_result,
                    centroid_x=centroid.x,
                    centroid_y=centroid.y,
                    source=source_name,
                    processing_date=datetime.datetime.now().isoformat()
                )
                self.events.append(event)
                new_events.append(event)

            self.diagnostics.append({
                "frame_number": frame_number,
                "track_id": det.track_id,
                "class_name": det.class_name,
                "confidence": det.confidence,
                "bbox": det.bbox,
                "category": self.detector.map_class_to_category(det.class_name),
                "cross_result": cross_result,
                "counting_status": "event_emitted" if cross_result is not None else "tracked_no_event",
            })

        if frame_number % 30 == 0:
            self.counter.cleanup_tracks(active_tracks, current_frame=frame_number)

        return frame, new_events


def export_corrected_records(records: List[Dict[str, Any]], output_dir: str | Path | None = None) -> Dict[str, str]:
    """Exporta registros corregidos para el flujo de aforo manual."""
    if output_dir is None:
        output_dir = Path("data/processed/reports")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(records)
    if "status" not in df.columns:
        df["status"] = "AUTOMATICO"
    if "notes" not in df.columns:
        df["notes"] = ""
    if "category" not in df.columns:
        df["category"] = "DESCONOCIDO"
    if "direction" not in df.columns:
        df["direction"] = 0

    csv_path = output_dir / "corrected_events.csv"
    json_path = output_dir / "corrected_events.json"
    summary_path = output_dir / "corrected_summary.csv"

    df.to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(df.to_dict(orient="records"), fh, indent=2)

    summary = df.groupby(["category", "direction", "status"]).size().reset_index(name="count")
    summary.to_csv(summary_path, index=False)
    return {"csv": str(csv_path), "json": str(json_path), "summary": str(summary_path)}
