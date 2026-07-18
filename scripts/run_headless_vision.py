"""Script para correr visión de forma desatendida y contar el resultado."""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import pandas as pd

from pavement_intelligence.vision.detection.yolo_detector import YOLODetectorTracker
from pavement_intelligence.vision.pipeline import VisionPipeline


def run_single(video_path: str, prefix: str, model: str = "yolov8n.pt", confidence: float = 0.25,
               image_size: int = 640, device: str = "cpu", line_p1: tuple = None,
               line_p2: tuple = None, tolerance: float = 3.0):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir el video {video_path}.")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    if line_p1 is None or line_p2 is None:
        line_p1 = (0, int(height * 0.5))
        line_p2 = (width, int(height * 0.5))

    detector = YOLODetectorTracker(model_path=model, device=device, conf_threshold=confidence, image_size=image_size)
    pipeline = VisionPipeline(detector, line_p1, line_p2, tolerance=tolerance)

    out_dir = Path("data/processed/reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    video_out = cv2.VideoWriter(
        str(out_dir / f"processed_{prefix}.mp4"),
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps, (width, height)
    )

    frame_count = 0
    t0 = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        processed, _ = pipeline.process_frame(frame, frame_count, fps, prefix)
        video_out.write(processed)

    t1 = time.time()
    cap.release()
    video_out.release()

    duration = max(t1 - t0, 1e-6)
    print(f"[{prefix}] Total fotogramas: {frame_count}")
    print(f"[{prefix}] Total vehículos contados: {len(pipeline.events)}")
    print(f"[{prefix}] Tiempo total: {duration:.2f} s")
    print(f"[{prefix}] FPS de procesamiento: {frame_count / duration:.2f}")

    if pipeline.events:
        df = pd.DataFrame([e.to_dict() for e in pipeline.events])
        df.to_csv(out_dir / f"automatic_events_{prefix}.csv", index=False)
        with open(out_dir / f"automatic_events_{prefix}.json", "w", encoding="utf-8") as fh:
            json.dump([e.to_dict() for e in pipeline.events], fh, indent=4)
        print(f"[{prefix}] Eventos exportados.")
    else:
        print(f"[{prefix}] No se registraron eventos para exportar.")

    return {
        "video": prefix,
        "automatic_count": len(pipeline.events),
        "processing_time_seconds": round(duration, 3),
        "processing_fps": round(frame_count / duration, 3),
    }


def main(video_path: str, prefix: str):
    return run_single(video_path, prefix)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="data/videos/samples/car-detection.mp4")
    parser.add_argument("--prefix", default="test_video")
    args = parser.parse_args()
    main(args.video, args.prefix)
