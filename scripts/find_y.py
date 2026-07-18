import cv2
from pavement_intelligence.vision.detection.yolo_detector import YOLODetectorTracker

def find_range():
    cap = cv2.VideoCapture("data/videos/samples/car-detection.mp4")
    detector = YOLODetectorTracker("yolov8n.pt", "cpu", 0.45)
    min_y, max_y = 9999, 0
    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        dets = detector.process_frame(frame)
        for d in dets:
            cy = d.centroid[1]
            if cy < min_y: min_y = cy
            if cy > max_y: max_y = cy
        frame_count += 1
        if frame_count > 150: break # Only need a sample
    print(f"Y Range for centroids: {min_y} to {max_y}")

if __name__ == "__main__":
    find_range()
