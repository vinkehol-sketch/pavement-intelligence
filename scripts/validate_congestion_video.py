"""Valida headless el flujo real de video hasta la presentación de congestión."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from pavement_intelligence.ui.utils.congestion_session import (
    ALERTS_KEY,
    LAST_FRAME_KEY,
    SNAPSHOT_KEY,
    finish_congestion_session,
    process_congestion_result_once,
    start_congestion_session,
)
from pavement_intelligence.vision.analysis import AnalysisState, TrafficAnalysisController
from pavement_intelligence.vision.capture import VideoFileSource
from pavement_intelligence.vision.detection.yolo_detector import YOLODetectorTracker
from pavement_intelligence.vision.pipeline import VisionPipeline


def validate(video_path: Path, model_path: Path) -> dict[str, object]:
    source = VideoFileSource(video_path)

    def pipeline_factory() -> VisionPipeline:
        info = source.source_info()
        line_y = max(1, info.height // 2)
        detector = YOLODetectorTracker(
            model_path=str(model_path),
            device="cpu",
            conf_threshold=0.45,
            image_size=640,
            allowed_classes=["car", "motorcycle", "bus", "truck"],
            tracker_config="default",
        )
        return VisionPipeline(
            detector,
            (0, line_y),
            (max(1, info.width - 1), line_y),
            tolerance=3.0,
        )

    controller = TrafficAnalysisController(source, pipeline_factory)
    metadata = controller.start()
    session: dict[str, object] = {}
    start_congestion_session(session, metadata.source_id, monitoring_point_id="P-04")
    started = perf_counter()
    valid_frames = 0
    terminal_results = 0
    frame_keys: set[object] = set()
    duplicate_mutations = 0
    levels: list[str] = []
    transitions: list[str] = []

    while controller.state is AnalysisState.RUNNING:
        result = controller.process_next()
        assert result is not None
        if result.end_of_source:
            terminal_results += 1
        else:
            valid_frames += 1
        previous = session.get(SNAPSHOT_KEY)
        process_congestion_result_once(session, result)
        frame_keys.add(session[LAST_FRAME_KEY])
        snapshot = session[SNAPSHOT_KEY]
        if not result.end_of_source:
            level = snapshot.level.value
            if not levels or levels[-1] != level:
                transitions.append(f"{result.timestamp_seconds:.3f}s:{level}")
            levels.append(level)

        # Simula el rerun de Streamlit sobre exactamente el mismo resultado.
        before_duplicate = session[SNAPSHOT_KEY]
        process_congestion_result_once(session, result)
        if session[SNAPSHOT_KEY] is not before_duplicate:
            duplicate_mutations += 1
        if result.end_of_source:
            assert previous is not None

    first_final = finish_congestion_session(session)
    final_snapshot = session[SNAPSHOT_KEY]
    second_final = finish_congestion_session(session)
    elapsed = max(perf_counter() - started, 1e-9)
    events = controller.finish()
    event_ids = [event.event_id for event in events]
    alerts = session[ALERTS_KEY]

    return {
        "video": str(video_path),
        "duration_seconds": metadata.total_frames / metadata.fps,
        "source_fps": metadata.fps,
        "valid_frames": valid_frames,
        "samples": final_snapshot.sample_count,
        "levels_observed": sorted(set(levels)),
        "transitions": transitions,
        "events": len(event_ids),
        "unique_events": len(set(event_ids)),
        "alerts": len(alerts),
        "unique_alerts": len({alert.alert_id for alert in alerts}),
        "terminal_results": terminal_results,
        "unique_frame_keys": len(frame_keys),
        "duplicate_attempts": valid_frames + terminal_results,
        "duplicate_mutations": duplicate_mutations,
        "source_closed": not source.is_open(),
        "finalization_idempotent": (
            first_final == second_final and session[SNAPSHOT_KEY] is final_snapshot
        ),
        "final_snapshot_preserved": session[SNAPSHOT_KEY] is final_snapshot,
        "final_level": final_snapshot.level.value,
        "normative": final_snapshot.normative,
        "origin": final_snapshot.origin,
        "processing_seconds": elapsed,
        "processing_fps": valid_frames / elapsed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--video", type=Path, default=Path("data/videos/samples/car-detection.mp4")
    )
    parser.add_argument(
        "--model", type=Path, default=Path("data/models/yolov8n.pt")
    )
    args = parser.parse_args()
    print(json.dumps(validate(args.video, args.model), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
