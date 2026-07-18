import cv2
from pavement_intelligence.vision.detection.yolo_detector import YOLODetectorTracker

def debug_tracks():
    cap = cv2.VideoCapture("data/videos/samples/car-detection.mp4")
    detector = YOLODetectorTracker("yolov8n.pt", "cpu", 0.45)
    frame_count = 0
    tracks = {}
    
    while cap.isOpened() and frame_count < 100:
        ret, frame = cap.read()
        if not ret: break
        dets = detector.process_frame(frame)
        for d in dets:
            cy = d.centroid[1]
            if d.track_id not in tracks:
                tracks[d.track_id] = []
            tracks[d.track_id].append(cy)
        frame_count += 1
        
    for tid, ys in tracks.items():
        if len(ys) > 5:
            print(f"Track {tid}: {len(ys)} frames, Y goes from {ys[0]:.1f} to {ys[-1]:.1f}")

if __name__ == "__main__":
    debug_tracks()
