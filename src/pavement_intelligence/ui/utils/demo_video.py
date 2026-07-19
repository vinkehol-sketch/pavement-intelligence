"""Utilidades aisladas para el reproductor local demostrativo de tráfico."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import MutableMapping

import cv2
import numpy as np


DEMO_STATE_DEFAULTS: dict[str, object] = {
    "traffic_demo_source_mode": "Imagen estática",
    "traffic_demo_video_path": "",
    "traffic_demo_playing": False,
    "traffic_demo_frame_index": 0,
    "traffic_demo_total_frames": 0,
    "traffic_demo_fps": 0.0,
    "traffic_demo_last_update": 0.0,
    "traffic_demo_loop": True,
    "traffic_demo_error": "",
}


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    fps: float
    total_frames: int
    width: int
    height: int

    @property
    def duration_seconds(self) -> float:
        return self.total_frames / self.fps

    @property
    def resolution(self) -> str:
        return f"{self.width} × {self.height}"


@dataclass(frozen=True)
class DemoMetrics:
    flow_veh_min: int
    vehicles_in_scene: int
    category_counts: tuple[int, ...]
    direction_counts: tuple[int, int]
    congestion: str
    alert_count: int


def inspect_video(path: str | Path) -> VideoInfo:
    """Inspecciona un video local y siempre libera el recurso de OpenCV."""
    video_path = Path(path)
    if not video_path.is_file():
        raise FileNotFoundError(f"No existe el video demostrativo: {video_path}")
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise ValueError(f"OpenCV no pudo abrir el video: {video_path}")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fps <= 0 or total <= 0 or width <= 0 or height <= 0:
            raise ValueError(f"Metadatos de video inválidos: {video_path}")
        return VideoInfo(video_path, fps, total, width, height)
    finally:
        capture.release()


def clamp_frame_index(frame_index: int, total_frames: int) -> int:
    if total_frames <= 0:
        return 0
    return min(max(int(frame_index), 0), total_frames - 1)


def read_frame(path: str | Path, frame_index: int) -> np.ndarray:
    """Lee un fotograma BGR validado y libera el archivo inmediatamente."""
    info = inspect_video(path)
    index = clamp_frame_index(frame_index, info.total_frames)
    capture = cv2.VideoCapture(str(info.path))
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok or frame is None or frame.size == 0:
            raise ValueError(f"No se pudo leer el fotograma {index}.")
        return frame
    finally:
        capture.release()


def frame_to_rgb(frame: np.ndarray) -> np.ndarray:
    if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3 or frame.size == 0:
        raise ValueError("El fotograma debe ser una imagen BGR de tres canales.")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def playback_progress(frame_index: int, total_frames: int) -> float:
    if total_frames <= 1:
        return 0.0
    return clamp_frame_index(frame_index, total_frames) / (total_frames - 1)


def advance_frame(
    frame_index: int,
    total_frames: int,
    source_fps: float,
    last_update: float,
    now: float,
    *,
    loop: bool = True,
) -> tuple[int, float, bool]:
    """Avanza según tiempo transcurrido sin bloquear ni crear temporizadores."""
    if total_frames <= 0 or source_fps <= 0:
        return 0, now, False
    elapsed = max(0.0, now - last_update)
    steps = max(1, int(elapsed * source_fps))
    candidate = frame_index + steps
    if candidate >= total_frames:
        if loop:
            candidate %= total_frames
        else:
            return total_frames - 1, now, False
    return candidate, now, True


def compute_demo_metrics(progress: float) -> DemoMetrics:
    """Serie sintética determinista; no inspecciona el contenido del video."""
    p = min(max(float(progress), 0.0), 1.0)
    category_final = (842, 216, 128, 249, 121)
    category_counts = tuple(round(value * (0.55 + 0.45 * p)) for value in category_final)
    total = sum(category_counts)
    north_south = round(total * (0.53 + 0.02 * p))
    flow = round(21 + 17 * p + 4 * (1 - abs(2 * p - 1)))
    in_scene = round(8 + 10 * p)
    congestion = "Moderada" if flow >= 34 else "Normal"
    return DemoMetrics(flow, in_scene, category_counts, (north_south, total - north_south), congestion, int(p >= 0.65))


def initialize_demo_playback(session: MutableMapping[str, object], video_path: str | Path) -> None:
    for key, value in DEMO_STATE_DEFAULTS.items():
        session.setdefault(key, value)
    session["traffic_demo_video_path"] = str(video_path)


def reset_demo_playback(session: MutableMapping[str, object], *, last_update: float = 0.0) -> None:
    session["traffic_demo_playing"] = False
    session["traffic_demo_frame_index"] = 0
    session["traffic_demo_last_update"] = last_update
    session["traffic_demo_error"] = ""
