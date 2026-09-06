import sqlite3
from typing import List, Tuple
from .schemas import DecisionRecord

class SQLiteStorage:
    """Handles persistent logging of AI traffic decisions to a SQLite database."""
    
    def __init__(self, db_path: str = "traffic_data.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initializes the database schema if it doesn't already exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS decision_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    intersection_id TEXT NOT NULL,
                    vehicle_count INTEGER NOT NULL,
                    crowd_density REAL NOT NULL,
                    emergency_present BOOLEAN NOT NULL,
                    green_seconds INTEGER NOT NULL,
                    red_seconds INTEGER NOT NULL,
                    reason TEXT NOT NULL
                );
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS active_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    intersection_id TEXT NOT NULL,
                    level TEXT NOT NULL,
                    type TEXT NOT NULL,
                    message TEXT NOT NULL
                );
            ''')
            conn.commit()

    def save_alerts(self, intersection_id: str, alerts: list) -> None:
        """Persists generated critical alerts to the database."""
        if not alerts: return
        with sqlite3.connect(self.db_path) as conn:
            for alert in alerts:
                conn.execute(
                    'INSERT INTO active_alerts (intersection_id, level, type, message) VALUES (?, ?, ?, ?)',
                    (intersection_id, alert.level, alert.type, alert.message)
                )
            conn.commit()

    def save_decision(self, decision: DecisionRecord) -> None:
        """Persists a complete decision record to the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''
                INSERT INTO decision_logs (
                    intersection_id, vehicle_count, crowd_density, 
                    emergency_present, green_seconds, red_seconds, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    decision.intersection_id,
                    decision.snapshot.vehicle_count,
                    decision.snapshot.crowd_density,
                    decision.snapshot.emergency_vehicle_present,
                    decision.plan.green_seconds,
                    decision.plan.red_seconds,
                    decision.plan.reason
                )
            )
            conn.commit()
            
    def get_recent_decisions(self, limit: int = 5) -> List[Tuple]:
        """Fetch the most recent decisions, primarily used to populate dashboards."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT intersection_id, vehicle_count, green_seconds, timestamp FROM decision_logs ORDER BY timestamp DESC LIMIT ?', 
                (limit,)
            )
            return cursor.fetchall()
