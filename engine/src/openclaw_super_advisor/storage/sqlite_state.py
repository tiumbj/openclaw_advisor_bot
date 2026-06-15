from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..market_data.cursors import BackfillState, CursorState
from ..market_data.normalization import from_iso_z, to_iso_z
from ..market_data.schemas import BarRecord, HeartbeatRecord, QualityIncident, TickRecord

MIGRATIONS = (
    (
        "001_market_data_foundation",
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS symbol_mappings (
            logical_symbol TEXT PRIMARY KEY,
            broker_symbol TEXT NOT NULL,
            aliases_json TEXT NOT NULL,
            description TEXT NOT NULL,
            point REAL NOT NULL,
            digits INTEGER NOT NULL,
            visible INTEGER NOT NULL,
            updated_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS collection_cursors (
            stream_kind TEXT NOT NULL,
            logical_symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            cursor_utc TEXT NOT NULL,
            marker_id TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY (stream_kind, logical_symbol, timeframe)
        );
        CREATE TABLE IF NOT EXISTS latest_ticks (
            logical_symbol TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS latest_bars (
            logical_symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            bar_kind TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (logical_symbol, timeframe, bar_kind)
        );
        CREATE TABLE IF NOT EXISTS quality_incidents (
            incident_key TEXT PRIMARY KEY,
            event_kind TEXT NOT NULL,
            logical_symbol TEXT NOT NULL,
            timeframe TEXT,
            detail TEXT NOT NULL,
            first_seen_utc TEXT NOT NULL,
            last_seen_utc TEXT NOT NULL,
            hit_count INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS collector_heartbeats (
            heartbeat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            collector_name TEXT NOT NULL,
            status TEXT NOT NULL,
            detail_json TEXT NOT NULL,
            observed_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS backfill_state (
            run_key TEXT PRIMARY KEY,
            logical_symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            start_at_utc TEXT NOT NULL,
            end_at_utc TEXT NOT NULL,
            next_start_utc TEXT NOT NULL,
            status TEXT NOT NULL,
            last_error TEXT,
            updated_at_utc TEXT NOT NULL
        );
        """,
    ),
)


class SQLiteStateStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA foreign_keys=ON;")
        connection.execute("PRAGMA busy_timeout=5000;")
        connection.execute("PRAGMA synchronous=FULL;")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_cursor(
        self, stream_kind: str, logical_symbol: str, timeframe: str = ""
    ) -> CursorState | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT stream_kind, logical_symbol, timeframe, cursor_utc, marker_id
                FROM collection_cursors
                WHERE stream_kind = ? AND logical_symbol = ? AND timeframe = ?
                """,
                (stream_kind, logical_symbol, timeframe),
            ).fetchone()
        if row is None:
            return None
        return CursorState(
            stream_kind=str(row["stream_kind"]),
            logical_symbol=str(row["logical_symbol"]),
            timeframe=str(row["timeframe"]),
            cursor_utc=from_iso_z(str(row["cursor_utc"])),
            marker_id=str(row["marker_id"]),
        )

    def advance_cursor(
        self,
        connection: sqlite3.Connection,
        stream_kind: str,
        logical_symbol: str,
        timeframe: str,
        cursor_utc: str,
        marker_id: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO collection_cursors (
                stream_kind, logical_symbol, timeframe, cursor_utc, marker_id, updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(stream_kind, logical_symbol, timeframe) DO UPDATE SET
                cursor_utc = excluded.cursor_utc,
                marker_id = excluded.marker_id,
                updated_at_utc = excluded.updated_at_utc
            """,
            (stream_kind, logical_symbol, timeframe, cursor_utc, marker_id, cursor_utc),
        )

    def record_symbol_mapping(
        self,
        connection: sqlite3.Connection,
        logical_symbol: str,
        broker_symbol: str,
        aliases: tuple[str, ...],
        description: str,
        point: float,
        digits: int,
        visible: bool,
        observed_at_utc: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO symbol_mappings (
                logical_symbol,
                broker_symbol,
                aliases_json,
                description,
                point,
                digits,
                visible,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(logical_symbol) DO UPDATE SET
                broker_symbol = excluded.broker_symbol,
                aliases_json = excluded.aliases_json,
                description = excluded.description,
                point = excluded.point,
                digits = excluded.digits,
                visible = excluded.visible,
                updated_at_utc = excluded.updated_at_utc
            """,
            (
                logical_symbol,
                broker_symbol,
                json.dumps(list(aliases)),
                description,
                point,
                digits,
                int(visible),
                observed_at_utc,
            ),
        )

    def upsert_latest_tick(self, connection: sqlite3.Connection, record: TickRecord) -> None:
        connection.execute(
            """
            INSERT INTO latest_ticks (logical_symbol, payload_json)
            VALUES (?, ?)
            ON CONFLICT(logical_symbol) DO UPDATE SET payload_json = excluded.payload_json
            """,
            (
                record.logical_symbol,
                json.dumps(record.to_dict(), ensure_ascii=True, sort_keys=True),
            ),
        )

    def upsert_latest_bar(
        self, connection: sqlite3.Connection, record: BarRecord, bar_kind: str
    ) -> None:
        connection.execute(
            """
            INSERT INTO latest_bars (logical_symbol, timeframe, bar_kind, payload_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(logical_symbol, timeframe, bar_kind) DO UPDATE SET
                payload_json = excluded.payload_json
            """,
            (
                record.logical_symbol,
                record.timeframe,
                bar_kind,
                json.dumps(record.to_dict(), ensure_ascii=True, sort_keys=True),
            ),
        )

    def record_incidents(
        self, connection: sqlite3.Connection, incidents: list[QualityIncident]
    ) -> None:
        for incident in incidents:
            payload_json = json.dumps(incident.to_dict(), ensure_ascii=True, sort_keys=True)
            connection.execute(
                """
                INSERT INTO quality_incidents (
                    incident_key, event_kind, logical_symbol, timeframe, detail,
                    first_seen_utc, last_seen_utc, hit_count, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(incident_key) DO UPDATE SET
                    last_seen_utc = excluded.last_seen_utc,
                    hit_count = quality_incidents.hit_count + 1,
                    payload_json = excluded.payload_json
                """,
                (
                    incident.incident_key,
                    incident.event_kind,
                    incident.logical_symbol,
                    incident.timeframe,
                    incident.detail,
                    to_iso_z(incident.observed_at_utc),
                    to_iso_z(incident.observed_at_utc),
                    payload_json,
                ),
            )

    def record_heartbeat(self, connection: sqlite3.Connection, heartbeat: HeartbeatRecord) -> None:
        connection.execute(
            """
            INSERT INTO collector_heartbeats (collector_name, status, detail_json, observed_at_utc)
            VALUES (?, ?, ?, ?)
            """,
            (
                heartbeat.collector_name,
                heartbeat.status,
                json.dumps(heartbeat.detail, ensure_ascii=True, sort_keys=True),
                to_iso_z(heartbeat.observed_at_utc),
            ),
        )

    def get_latest_closed_bar(self, logical_symbol: str, timeframe: str) -> BarRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM latest_bars
                WHERE logical_symbol = ? AND timeframe = ? AND bar_kind = 'closed'
                """,
                (logical_symbol, timeframe),
            ).fetchone()
        return None if row is None else self._bar_from_json(str(row["payload_json"]))

    def get_backfill_state(self, run_key: str) -> BackfillState | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    run_key,
                    logical_symbol,
                    timeframe,
                    start_at_utc,
                    end_at_utc,
                    next_start_utc,
                    status,
                    last_error
                FROM backfill_state
                WHERE run_key = ?
                """,
                (run_key,),
            ).fetchone()
        if row is None:
            return None
        return BackfillState(
            run_key=str(row["run_key"]),
            logical_symbol=str(row["logical_symbol"]),
            timeframe=str(row["timeframe"]),
            start_at_utc=from_iso_z(str(row["start_at_utc"])),
            end_at_utc=from_iso_z(str(row["end_at_utc"])),
            next_start_utc=from_iso_z(str(row["next_start_utc"])),
            status=str(row["status"]),
            last_error=None if row["last_error"] is None else str(row["last_error"]),
        )

    def upsert_backfill_state(
        self,
        connection: sqlite3.Connection,
        state: BackfillState,
        updated_at_utc: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO backfill_state (
                run_key, logical_symbol, timeframe, start_at_utc, end_at_utc, next_start_utc,
                status, last_error, updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_key) DO UPDATE SET
                next_start_utc = excluded.next_start_utc,
                status = excluded.status,
                last_error = excluded.last_error,
                updated_at_utc = excluded.updated_at_utc
            """,
            (
                state.run_key,
                state.logical_symbol,
                state.timeframe,
                to_iso_z(state.start_at_utc),
                to_iso_z(state.end_at_utc),
                to_iso_z(state.next_start_utc),
                state.status,
                state.last_error,
                updated_at_utc,
            ),
        )

    def snapshot(self, logical_symbol: str | None = None) -> dict[str, object]:
        where = ""
        params: tuple[object, ...] = ()
        if logical_symbol is not None:
            where = " WHERE logical_symbol = ?"
            params = (logical_symbol,)
        with self.connect() as connection:
            symbol_rows = connection.execute(
                f"SELECT * FROM symbol_mappings{where} ORDER BY logical_symbol",
                params,
            ).fetchall()
            tick_rows = connection.execute(
                f"SELECT payload_json FROM latest_ticks{where} ORDER BY logical_symbol",
                params,
            ).fetchall()
            bar_rows = connection.execute(
                (
                    f"SELECT payload_json FROM latest_bars{where} "
                    "ORDER BY logical_symbol, timeframe, bar_kind"
                ),
                params,
            ).fetchall()
            incident_rows = connection.execute(
                """
                SELECT payload_json, hit_count FROM quality_incidents
                ORDER BY last_seen_utc DESC
                LIMIT 50
                """
            ).fetchall()
            heartbeat_row = connection.execute(
                """
                SELECT collector_name, status, detail_json, observed_at_utc
                FROM collector_heartbeats
                ORDER BY heartbeat_id DESC
                LIMIT 1
                """
            ).fetchone()
        snapshot: dict[str, object] = {
            "symbols": [
                {
                    "logical_symbol": str(row["logical_symbol"]),
                    "broker_symbol": str(row["broker_symbol"]),
                    "aliases": json.loads(str(row["aliases_json"])),
                    "description": str(row["description"]),
                    "point": float(row["point"]),
                    "digits": int(row["digits"]),
                    "visible": bool(row["visible"]),
                    "updated_at_utc": str(row["updated_at_utc"]),
                }
                for row in symbol_rows
            ],
            "ticks": [json.loads(str(row["payload_json"])) for row in tick_rows],
            "bars": [json.loads(str(row["payload_json"])) for row in bar_rows],
            "quality_incidents": [
                json.loads(str(row["payload_json"])) | {"hit_count": int(row["hit_count"])}
                for row in incident_rows
            ],
            "heartbeat": None,
        }
        if heartbeat_row is not None:
            snapshot["heartbeat"] = {
                "collector_name": str(heartbeat_row["collector_name"]),
                "status": str(heartbeat_row["status"]),
                "detail": json.loads(str(heartbeat_row["detail_json"])),
                "observed_at_utc": str(heartbeat_row["observed_at_utc"]),
            }
        return snapshot

    def storage_check(self, parquet_root: Path) -> dict[str, object]:
        with self.connect() as connection:
            migration_rows = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        parquet_files = list(parquet_root.rglob("*.parquet")) if parquet_root.exists() else []
        return {
            "sqlite_path": str(self.database_path),
            "migrations": [str(row["version"]) for row in migration_rows],
            "parquet_root": str(parquet_root),
            "parquet_file_count": len(parquet_files),
        }

    def _apply_migrations(self) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied = {
                str(row["version"])
                for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
            }
            for version, statement in MIGRATIONS:
                if version in applied:
                    continue
                connection.executescript(statement)
                connection.execute(
                    (
                        "INSERT INTO schema_migrations (version, applied_at) "
                        "VALUES (?, datetime('now'))"
                    ),
                    (version,),
                )

    def _bar_from_json(self, payload_json: str) -> BarRecord:
        payload = json.loads(payload_json)
        return BarRecord(
            schema_version=str(payload["schema_version"]),
            collector_version=str(payload["collector_version"]),
            logical_symbol=str(payload["logical_symbol"]),
            broker_symbol=str(payload["broker_symbol"]),
            timeframe=str(payload["timeframe"]),
            open_time_utc=from_iso_z(str(payload["open_time_utc"])),
            close_time_utc=from_iso_z(str(payload["close_time_utc"])),
            open=float(payload["open"]),
            high=float(payload["high"]),
            low=float(payload["low"]),
            close=float(payload["close"]),
            tick_volume=int(payload["tick_volume"]),
            real_volume=int(payload["real_volume"]),
            spread=int(payload["spread"]),
            is_closed=bool(payload["is_closed"]),
            bar_id=str(payload["bar_id"]),
            data_quality=str(payload["data_quality"]),
            quality_flags=tuple(str(item) for item in payload["quality_flags"]),
            source=str(payload.get("source", "UNKNOWN")),
            source_system=str(payload.get("source_system", "UNKNOWN")),
            fetched_at_utc=(
                None
                if payload.get("fetched_at_utc") is None
                else from_iso_z(str(payload["fetched_at_utc"]))
            ),
            realtime_class=str(payload.get("realtime_class", "UNKNOWN")),
            formula_version=(
                None
                if payload.get("formula_version") is None
                else str(payload["formula_version"])
            ),
        )
