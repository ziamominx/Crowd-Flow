from __future__ import annotations

import cv2
from typing import Optional

from ultralytics import YOLO
from .schemas import IntersectionSnapshot
from .pipeline import SnapshotProvider


class VisionAdapter(SnapshotProvider):
    """YOLOv8-based camera adapter for real-time traffic and crowd snapshots."""

    # COCO Class IDs
    PERSON_CLASS = 0
    # car:2, motorcycle:3, bus:5, truck:7
    VEHICLE_CLASSES = {2, 3, 5, 7}

    def __init__(self, camera_url: str | int, model_name: str = "yolov8n.pt", max_expected_crowd: int = 100):
        self.camera_url = camera_url
        self.model = YOLO(model_name)
        self.max_expected_crowd = max_expected_crowd
        self.cap = None

    def get_snapshot(self, intersection_id: str) -> IntersectionSnapshot:
        """Capture a frame from the CCTV feed, run YOLO, and generate a snapshot."""
        
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.camera_url)
        
        if not self.cap.isOpened():
            # Graceful fallback if camera is unavailable
            print(f"[Warning] Camera stream {intersection_id} at {self.camera_url} unavailable.")
            return IntersectionSnapshot(vehicle_count=0, crowd_density=0.0, emergency_vehicle_present=False)

        ret, frame = self.cap.read()

        if not ret:
            print(f"[Warning] Failed to grab frame from {intersection_id}.")
            return IntersectionSnapshot(vehicle_count=0, crowd_density=0.0, emergency_vehicle_present=False)

        # Run inference using YOLOv8
        results = self.model(frame, verbose=False)
        
        vehicle_count = 0
        person_count = 0
        emergency_present = False

        if len(results) > 0 and results[0].boxes is not None:
            for box in results[0].boxes:
                cls_id = int(box.cls[0].item())
                if cls_id in self.VEHICLE_CLASSES:
                    vehicle_count += 1
                elif cls_id == self.PERSON_CLASS:
                    person_count += 1
                    
                # Note: Emergency vehicle detection (ambulances/fire trucks)
                # would ideally require a custom-trained model or flashing-light analysis,
                # as standard COCO does not have an "ambulance" class.
                # In phase 1, we can randomly inject or simulate it until a custom dataset is ready.

        # Normalize crowd density
        crowd_density = min(person_count / self.max_expected_crowd, 1.0)

        snapshot = IntersectionSnapshot(
            vehicle_count=vehicle_count,
            crowd_density=round(crowd_density, 2),
            emergency_vehicle_present=emergency_present,
        )
        
        return snapshot
