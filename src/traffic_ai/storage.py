import sqlite3
from typing import List, Optional, Tuple
from .schemas import DecisionRecord


class SQLiteStorage:
    """Handles persistent logging of AI traffic decisions to a SQLite database.

    Two writers share this store:
      * the traffic-signal pipeline (intersection_id / green_seconds semantics), and
      * the zone-state producer (zone_id / city_id / load_value semantics).

    The zone columns below are nullable, so both writers coexist in the same
    tables and older dashboards keep working unchanged.
    """

    # (table, column, DDL) applied only when the column is missing — safe for
    # databases created before the zone producer existed.
    _ZONE_MIGRATIONS = [
        ("decision_logs", "zone_id", "TEXT"),
        ("decision_logs", "city_id", "TEXT"),
        ("decision_logs", "resource_type", "TEXT"),
        ("decision_logs", "load_value", "REAL"),
        ("decision_logs", "sim_time_min", "INTEGER"),
        ("decision_logs", "action", "TEXT"),
        ("active_alerts", "zone_id", "TEXT"),
        ("active_alerts", "city_id", "TEXT"),
        ("active_alerts", "resource_type", "TEXT"),
        ("active_alerts", "sim_time_min", "INTEGER"),
    ]

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
            # Migration: bring older databases up to the zone-producer schema.
            for table, column, ddl in self._ZONE_MIGRATIONS:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
                if column not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            conn.commit()

    # ------------------------------------------------------------------ #
    #  Legacy traffic-signal writer (unchanged semantics)                #
    # ------------------------------------------------------------------ #

    def save_alerts(self, intersection_id: str, alerts: list) -> None:
        """Persists generated critical alerts to the database."""
        if not alerts:
            return
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

    # ------------------------------------------------------------------ #
    #  Zone-state producer writer (event-schedule / venue / last-mile)   #
    # ------------------------------------------------------------------ #

    def save_zone_decisions(self, rows: list) -> None:
        """Persists one decision row per zone from a producer tick.

        Each row keeps the legacy NOT NULL columns populated with sane proxies
        (vehicle_count = load proxy, crowd_density = load/100) while the true
        zone semantics live in the zone_* / load_value / action columns.
        """
        if not rows:
            return
        with sqlite3.connect(self.db_path) as conn:
            for r in rows:
                conn.execute(
                    '''
                    INSERT INTO decision_logs (
                        intersection_id, vehicle_count, crowd_density,
                        emergency_present, green_seconds, red_seconds, reason,
                        zone_id, city_id, resource_type, load_value, sim_time_min, action
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        r["zone_id"],                       # intersection_id (compat)
                        int(round(r["load_value"])),        # vehicle_count (proxy)
                        round(r["load_value"] / 100.0, 4),  # crowd_density (proxy)
                        0,                                  # emergency_present
                        0,                                  # green_seconds
                        0,                                  # red_seconds
                        r["reason"],
                        r["zone_id"],
                        r["city_id"],
                        r["resource_type"],
                        round(r["load_value"], 2),
                        r["sim_time_min"],
                        r["action"]
                    )
                )
            conn.commit()

    def save_zone_alerts(self, rows: list) -> None:
        """Persists new/transitioned zone alerts (venue capacity, last-mile
        queue, schedule shifts, generic pressure)."""
        if not rows:
            return
        with sqlite3.connect(self.db_path) as conn:
            for r in rows:
                conn.execute(
                    '''
                    INSERT INTO active_alerts (
                        intersection_id, level, type, message,
                        zone_id, city_id, resource_type, sim_time_min
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        r["zone_id"] or r.get("city_id", ""),  # intersection_id (compat)
                        r["level"],
                        r["type"],
                        r["message"],
                        r["zone_id"],
                        r["city_id"],
                        r["resource_type"],
                        r["sim_time_min"]
                    )
                )
            conn.commit()

    def fetch_zone_decisions(self, limit: int = 20, city: Optional[str] = None) -> list:
        """Most recent zone-producer decision rows, newest first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if city:
                cursor = conn.execute(
                    'SELECT * FROM decision_logs WHERE city_id = ? ORDER BY id DESC LIMIT ?',
                    (city, limit)
                )
            else:
                cursor = conn.execute(
                    'SELECT * FROM decision_logs ORDER BY id DESC LIMIT ?',
                    (limit,)
                )
            return [dict(r) for r in cursor.fetchall()]

    def fetch_zone_alerts(self, limit: int = 20, city: Optional[str] = None) -> list:
        """Most recent zone-producer alert rows, newest first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if city:
                cursor = conn.execute(
                    'SELECT * FROM active_alerts WHERE city_id = ? ORDER BY id DESC LIMIT ?',
                    (city, limit)
                )
            else:
                cursor = conn.execute(
                    'SELECT * FROM active_alerts ORDER BY id DESC LIMIT ?',
                    (limit,)
                )
            return [dict(r) for r in cursor.fetchall()]

    def counts(self) -> dict:
        """Row counts for the producer status readout."""
        with sqlite3.connect(self.db_path) as conn:
            decisions = conn.execute("SELECT COUNT(*) FROM decision_logs").fetchone()[0]
            alerts = conn.execute("SELECT COUNT(*) FROM active_alerts").fetchone()[0]
            return {"decisions": decisions, "alerts": alerts}