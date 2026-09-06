from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .controller import SignalController
from .schemas import IntersectionSnapshot, SignalPlan, DecisionRecord
from .alerts import AlertEngine, Alert

class SnapshotProvider(Protocol):
    """Interface for camera/IoT/GPS snapshot providers."""

    def get_snapshot(self, intersection_id: str) -> IntersectionSnapshot:
        ...


class DataLogger(Protocol):
    """Interface for database/storage adapters."""
    def save_decision(self, decision: DecisionRecord) -> None:
        ...
    def save_alerts(self, intersection_id: str, alerts: list[Alert]) -> None:
        ...

class TrafficDecisionEngine:
    """Coordinates snapshot ingestion and signal decisioning.

    This class is the handoff point where real adapters
    (CCTV, IoT, maps) can be plugged in.
    """

    def __init__(self, provider: SnapshotProvider, controller: SignalController | None = None, logger: DataLogger | None = None):
        self.provider = provider
        self.controller = controller or SignalController()
        self.logger = logger
        self.alert_engine = AlertEngine()

    def run_once(self, intersection_id: str) -> DecisionRecord:
        snapshot = self.provider.get_snapshot(intersection_id)
        plan = self.controller.recommend(snapshot)
        record = DecisionRecord(intersection_id=intersection_id, snapshot=snapshot, plan=plan)
        
        alerts = self.alert_engine.evaluate(record)
        
        # Save historical record and any triggered alerts if a database logger is connected
        if self.logger:
            self.logger.save_decision(record)
            self.logger.save_alerts(intersection_id, alerts)
            
        return record
