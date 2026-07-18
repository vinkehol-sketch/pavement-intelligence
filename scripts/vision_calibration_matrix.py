"""Genera una matriz de calibración para vision y exporta un CSV consolidado."""
import csv
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_headless_vision import run_single


def build_matrix(video_path: str, prefix: str, manual_count: int) -> None:
    out_dir = Path("data/processed/reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    configs = [
        ("yolov8n.pt", 0.15, 640, "cpu", "predeterminada", (0, 360), (1280, 360)),
        ("yolov8s.pt", 0.15, 640, "cpu", "predeterminada", (0, 360), (1280, 360)),
        ("yolov8n.pt", 0.25, 640, "cpu", "predeterminada", (0, 360), (1280, 360)),
        ("yolov8s.pt", 0.25, 640, "cpu", "predeterminada", (0, 360), (1280, 360)),
        ("yolov8n.pt", 0.35, 640, "cpu", "predeterminada", (0, 360), (1280, 360)),
        ("yolov8n.pt", 0.25, 960, "cpu", "predeterminada", (0, 360), (1280, 360)),
    ]

    for model, confidence, image_size, device, tracker_config, p1, p2 in configs:
        run_prefix = f"{prefix}_{model.split('.')[0]}_{confidence}_{image_size}_{tracker_config}"
        result = run_single(
            video_path,
            run_prefix,
            model=model,
            confidence=confidence,
            image_size=image_size,
            device=device,
            line_p1=p1,
            line_p2=p2,
        )
        absolute_error = abs(result["automatic_count"] - manual_count)
        percentage_error = 0.0 if manual_count == 0 else round((absolute_error / manual_count) * 100, 2)
        rows.append({
            "video": prefix,
            "model": model,
            "confidence": confidence,
            "image_size": image_size,
            "tracker_config": tracker_config,
            "line_config": f"{p1}->{p2}",
            "manual_count": manual_count,
            "automatic_count": result["automatic_count"],
            "absolute_error": absolute_error,
            "percentage_error": percentage_error,
            "processing_time_seconds": result["processing_time_seconds"],
            "processing_fps": result["processing_fps"],
        })

    csv_path = out_dir / "vision_calibration_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "video",
                "model",
                "confidence",
                "image_size",
                "tracker_config",
                "line_config",
                "manual_count",
                "automatic_count",
                "absolute_error",
                "percentage_error",
                "processing_time_seconds",
                "processing_fps",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    with open(out_dir / "vision_calibration_results.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)

    print(f"Matriz exportada en {csv_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="data/videos/samples/car-detection.mp4")
    parser.add_argument("--prefix", default="test_video")
    parser.add_argument("--manual-count", type=int, default=6)
    args = parser.parse_args()
    build_matrix(args.video, args.prefix, args.manual_count)
