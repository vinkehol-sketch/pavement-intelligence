"""Lógica de cruce de línea virtual para conteo de vehículos."""
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional

@dataclass
class Point:
    x: float
    y: float

@dataclass
class TrackState:
    current_side: int = 0
    last_frame_seen: int = 0
    last_side_frame: int = 0
    first_side: Optional[int] = None
    last_side: Optional[int] = None
    pending_side: Optional[int] = None
    history: List[dict] = field(default_factory=list)
    counted: bool = False
    last_count_frame: int = -1
    dominant_class: Optional[str] = None
    confidence_sum: float = 0.0
    confidence_count: int = 0
    class_counts: Counter = field(default_factory=Counter)
    class_confidence_sums: Dict[str, float] = field(default_factory=dict)

class VirtualLineCounter:
    """Contador basado en línea virtual definida por dos puntos.

    Utiliza el producto cruzado vectorial para determinar en qué lado
    de la línea se encuentra un punto y detectar cruces. Además,
    mantiene información de trayectoria para reducir falsos positivos.
    """
    def __init__(self, p1: Point, p2: Point, tolerance: float = 0.0, cooldown_frames: int = 3,
                 max_state_age_frames: int = 30, min_history_positions: int = 3,
                 min_displacement_pixels: float = 10.0, max_history_gap_frames: int = 10):
        self.p1 = p1
        self.p2 = p2
        self.tolerance = tolerance
        self.cooldown_frames = cooldown_frames
        self.max_state_age_frames = max_state_age_frames
        self.min_history_positions = max(2, min_history_positions)
        self.min_displacement_pixels = max(0.0, min_displacement_pixels)
        self.max_history_gap_frames = max(1, max_history_gap_frames)
        # Estado de los tracks: id -> lado (1 o -1)
        self.previous_states: Dict[int, int] = {}
        # Tracks ya contados para prevenir doble conteo por oscilación
        self.counted_tracks: Set[int] = set()
        self.track_states: Dict[int, TrackState] = {}
        self.seen_track_ids: Set[int] = set()
        self.sufficient_history_track_ids: Set[int] = set()
        self.metrics = {
            "events_emitted": 0,
            "events_blocked_duplicate": 0,
            "events_blocked_oscillation": 0,
            "events_blocked_insufficient_history": 0,
        }

    def _get_raw_side(self, p: Point) -> int:
        dx = self.p2.x - self.p1.x
        dy = self.p2.y - self.p1.y
        line_length = (dx * dx + dy * dy) ** 0.5
        if line_length == 0:
            return 0

        cross_product = dx * (p.y - self.p1.y) - dy * (p.x - self.p1.x)
        signed_distance = cross_product / line_length
        return 1 if signed_distance > 0 else -1

    def get_side(self, p: Point) -> int:
        """Determina de qué lado de la línea está el punto.

        Devuelve 1 si está a un lado, -1 si está al otro.
        El producto cruzado (p2-p1) x (p-p1) nos da el lado.
        """
        raw_side = self._get_raw_side(p)
        if abs(self._get_signed_distance(p)) <= self.tolerance:
            return 0
        return raw_side

    def _get_signed_distance(self, p: Point) -> float:
        dx = self.p2.x - self.p1.x
        dy = self.p2.y - self.p1.y
        line_length = (dx * dx + dy * dy) ** 0.5
        if line_length == 0:
            return 0.0
        cross_product = dx * (p.y - self.p1.y) - dy * (p.x - self.p1.x)
        return cross_product / line_length

    def _update_track_history(self, track_id: int, p: Point, frame_number: int, confidence: Optional[float] = None,
                              class_name: Optional[str] = None) -> None:
        state = self.track_states.setdefault(track_id, TrackState())
        self.seen_track_ids.add(track_id)
        state.history.append({
            "frame": frame_number,
            "x": p.x,
            "y": p.y,
            "confidence": confidence if confidence is not None else 0.0,
            "class_name": class_name or "",
        })
        state.last_frame_seen = frame_number
        if confidence is not None:
            state.confidence_sum += confidence
            state.confidence_count += 1
        if class_name:
            state.class_counts[class_name] += 1
            state.class_confidence_sums[class_name] = state.class_confidence_sums.get(class_name, 0.0) + (confidence or 0.0)
            state.dominant_class = max(
                state.class_counts,
                key=lambda name: (state.class_counts[name], state.class_confidence_sums.get(name, 0.0), name),
            )
        if len(state.history) >= self.min_history_positions:
            self.sufficient_history_track_ids.add(track_id)

    def get_track_history(self, track_id: int) -> List[dict]:
        return list(self.track_states.get(track_id, TrackState()).history)

    def get_stable_class(self, track_id: int) -> Optional[str]:
        """Devuelve la clase mayoritaria, desempatada por confianza acumulada."""
        return self.track_states.get(track_id, TrackState()).dominant_class

    def get_average_confidence(self, track_id: int) -> float:
        state = self.track_states.get(track_id)
        if state is None or state.confidence_count == 0:
            return 0.0
        return state.confidence_sum / state.confidence_count

    def get_diagnostics_summary(self) -> dict:
        return {
            "tracks_created": len(self.seen_track_ids),
            "tracks_with_sufficient_history": len(self.sufficient_history_track_ids),
            "tracks_with_insufficient_history": len(self.seen_track_ids - self.sufficient_history_track_ids),
            **self.metrics,
        }

    def process_point(self, track_id: int, p: Point, frame_number: int = 0, confidence: Optional[float] = None,
                      class_name: Optional[str] = None) -> Optional[int]:
        """Procesa un nuevo punto para un track_id dado.

        Retorna:
            - 1 si cruzó en sentido A (lado 1 a lado -1)
            - -1 si cruzó en sentido B (lado -1 a lado 1)
            - None si no hubo cruce válido o ya fue contado
        """
        current_side = self.get_side(p)
        state = self.track_states.setdefault(track_id, TrackState())
        self._update_track_history(track_id, p, frame_number, confidence=confidence, class_name=class_name)

        if track_id in self.counted_tracks:
            if current_side != 0 and state.current_side != 0 and current_side != state.current_side:
                self.metrics["events_blocked_duplicate"] += 1
                state.current_side = current_side
                state.last_side = current_side
            return None

        if current_side == 0:
            raw_side = self._get_raw_side(p)
            if raw_side != 0:
                state.pending_side = raw_side
            return None

        if state.first_side is None:
            if state.pending_side is not None and state.pending_side != current_side:
                history = state.history
                previous = history[-2]
                displacement = ((p.x - previous["x"]) ** 2 + (p.y - previous["y"]) ** 2) ** 0.5
                continuous = frame_number <= 0 or previous["frame"] <= 0 or frame_number - previous["frame"] <= self.max_history_gap_frames
                if len(history) >= self.min_history_positions and continuous and displacement >= self.min_displacement_pixels:
                    previous_side = state.pending_side
                    state.first_side = previous_side
                    state.last_side = current_side
                    state.current_side = current_side
                    state.last_side_frame = frame_number
                    state.counted = True
                    state.last_count_frame = frame_number
                    self.counted_tracks.add(track_id)
                    self.previous_states[track_id] = current_side
                    state.pending_side = None
                    self.metrics["events_emitted"] += 1
                    return 1 if previous_side == 1 else -1
            state.first_side = current_side
            state.last_side = current_side
            state.current_side = current_side
            state.last_side_frame = frame_number
            self.previous_states[track_id] = current_side
            state.pending_side = None
            return None

        prev_side = state.current_side
        if prev_side != 0 and prev_side != current_side:
            history = state.history
            enough_positions = len(history) >= self.min_history_positions
            previous_frame = history[-2]["frame"] if len(history) >= 2 else frame_number
            continuous = frame_number <= 0 or previous_frame <= 0 or frame_number - previous_frame <= self.max_history_gap_frames
            previous_side_points = [
                item for item in history[:-1]
                if self.get_side(Point(item["x"], item["y"])) == prev_side
            ]
            has_both_sides = bool(previous_side_points)
            reference = previous_side_points[-1] if previous_side_points else history[0]
            displacement = ((p.x - reference["x"]) ** 2 + (p.y - reference["y"]) ** 2) ** 0.5

            if not enough_positions or not continuous or not has_both_sides:
                self.metrics["events_blocked_insufficient_history"] += 1
                return None
            if displacement < self.min_displacement_pixels:
                self.metrics["events_blocked_oscillation"] += 1
                return None

            crossing_allowed = frame_number <= 0 or state.last_count_frame < 0 or frame_number - state.last_side_frame >= self.cooldown_frames
            if crossing_allowed:
                state.last_side_frame = frame_number
                state.last_side = current_side
                state.current_side = current_side
                state.counted = True
                state.last_count_frame = frame_number
                self.counted_tracks.add(track_id)
                self.previous_states[track_id] = current_side
                state.pending_side = None
                self.metrics["events_emitted"] += 1
                return 1 if prev_side == 1 else -1
            self.metrics["events_blocked_oscillation"] += 1
            return None

        state.last_side = current_side
        state.current_side = current_side
        self.previous_states[track_id] = current_side
        state.pending_side = None
        return None

    def cleanup_tracks(self, active_track_ids: List[int], current_frame: Optional[int] = None):
        """Limpia identificadores antiguos para liberar memoria.

        Mantiene en counted_tracks solo los tracks que aún podrían
        estar activos, asumiendo que los ids aumentan monótonamente
        y tracks muy antiguos no volverán.
        """
        active_set = set(active_track_ids)
        current_frame = current_frame if current_frame is not None else 0

        stale_track_ids = []
        for track_id, state in self.track_states.items():
            if current_frame - state.last_frame_seen > self.max_state_age_frames:
                stale_track_ids.append(track_id)
        for track_id in stale_track_ids:
            self.track_states.pop(track_id, None)
            self.previous_states.pop(track_id, None)

        self.previous_states = {k: v for k, v in self.previous_states.items() if k not in stale_track_ids}
        self.counted_tracks = {t for t in self.counted_tracks if t not in stale_track_ids}
