import cv2
import os
import math
import time
from collections import deque

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

class MultiCameraIngestor:
    """Deterministic Multi-Stream Computer Vision Evaluator for Phase 1.5."""
    
    def __init__(self):
        self.data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.cameras = {
            "silk_board": os.path.join(self.data_dir, "silk_board.mp4"),
            "madiwala": os.path.join(self.data_dir, "madiwala.mp4"),
            "koramangala": os.path.join(self.data_dir, "koramangala.mp4")
        }
        
        # Temporal Smoothing History Buffer
        self.history = {
            "silk_board": deque(maxlen=5),
            "madiwala": deque(maxlen=5),
            "koramangala": deque(maxlen=5)
        }
        
        self.caps = {}
        for name, path in self.cameras.items():
            if os.path.exists(path):
                self.caps[name] = cv2.VideoCapture(path)
            else:
                self.caps[name] = None
        
        self.model = YOLO("yolov8n.pt") if YOLO else None

    def smooth_count(self, junction: str, current_count: int) -> int:
        """Reduces YOLO frame-level flickers natively."""
        self.history[junction].append(current_count)
        return int(sum(self.history[junction]) / len(self.history[junction]))

    def estimate_speed(self, vehicle_count: int) -> float:
        """🚗 Physics Approximation via Non-Linear Congestion Decay."""
        max_speed = 60.0
        k = 0.05  # congestion sensitivity parameter
        speed = max_speed * math.exp(-k * vehicle_count)
        return float(max(speed, 5.0))

    def compute_density(self, vehicle_count: int) -> float:
        """📊 Clamped Mathematical Density."""
        lane_capacity = 50.0 
        return float(round(min(vehicle_count / lane_capacity, 1.0), 2))

    def compute_flow(self, vehicle_count: int, speed: float) -> float:
        """❗ Road Throughput Capacity. Required for Graph Propagation."""
        return float(round(vehicle_count * speed, 1))

    def count_vehicles(self, frame) -> int:
        """YOLOv8 Raw Processing."""
        if self.model is None:
            return 0
            
        results = self.model(frame, verbose=False)
        count = 0
        if len(results) > 0 and results[0].boxes is not None:
            for box in results[0].boxes:
                cls = int(box.cls[0].item())
                if cls in [2, 3, 5, 7]:  # car, motorcycle, bus, truck 
                    count += 1
        return count

    def get_frames(self) -> dict:
        """🔁 Extraction Loop (returns None if offline)."""
        frames = {}
        for name, cap in self.caps.items():
            if cap is None:
                frames[name] = None
                continue
                
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                
            if ret:
                frames[name] = frame
            else:
                frames[name] = None
                
        return frames

    def build_state(self) -> dict:
        """Unified Phase 1.5 JSON Output integrating fault handling and timestamps."""
        frames = self.get_frames()
        state = {}
        current_time = time.time()
        
        # Fallback Sanity Output for pure deterministic testing without UI crashing
        fallback_counts = {"silk_board": 23, "madiwala": 41, "koramangala": 12}
        
        for junction in self.cameras.keys():
            frame = frames.get(junction)
            
            # 1. Fault Handling (Camera Offline)
            if frame is None:
                # Fulfilling the requirement for local environment debugging without video files
                raw_count = fallback_counts[junction]
                v_count = self.smooth_count(junction, raw_count)
                speed = self.estimate_speed(v_count)
                density = self.compute_density(v_count)
                
                state[junction] = {
                    "vehicles": v_count,
                    "speed": round(speed, 1),
                    "density": density,
                    "flow": self.compute_flow(v_count, speed),
                    "timestamp": current_time,
                    "status": "camera_offline_simulating"
                }
                continue
                
            # 2. Main YOLO Ingestion
            raw_count = self.count_vehicles(frame)
            v_count = self.smooth_count(junction, raw_count)
            speed = self.estimate_speed(v_count)
            density = self.compute_density(v_count)
            
            # 3. State Output Generation
            state[junction] = {
                "vehicles": v_count,
                "speed": round(speed, 1),
                "density": density,
                "flow": self.compute_flow(v_count, speed),
                "timestamp": current_time,
                "status": "online"
            }
            
        return state
