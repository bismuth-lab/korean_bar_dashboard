from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

DB_PATH = Path("barpass_os.db")
EVIDENCE_DIR = Path("evidence")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    EVIDENCE_DIR.mkdir(exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_records (
                date TEXT PRIMARY KEY,
                checkin TEXT,
                checkout TEXT,
                location TEXT,
                first_task TEXT,
                completed_first INTEGER DEFAULT 0,
                lecture_min INTEGER DEFAULT 0,
                self_study_min INTEGER DEFAULT 0,
                cbt_practice_min INTEGER DEFAULT 0,
                study_blocks INTEGER DEFAULT 0,
                sleep_hours REAL DEFAULT 0,
                exercise_min INTEGER DEFAULT 0,
                mood INTEGER DEFAULT 3,
                energy INTEGER DEFAULT 3,
                anxiety INTEGER DEFAULT 3,
                avoidance TEXT DEFAULT '[]',
                note TEXT DEFAULT '',
                edited INTEGER DEFAULT 0,
                late_entry INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                subject TEXT NOT NULL,
                output_type TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                duration_min INTEGER DEFAULT 0,
                attempted INTEGER DEFAULT 0,
                correct INTEGER DEFAULT 0,
                score REAL DEFAULT NULL,
                error_reason TEXT DEFAULT '',
                evidence_path TEXT DEFAULT '',
                evidence_hash TEXT DEFAULT '',
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS mocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                mock_name TEXT NOT NULL,
                round_no INTEGER DEFAULT 0,
                total_score REAL DEFAULT NULL,
                pass_cut REAL DEFAULT NULL,
                top_percent REAL DEFAULT NULL,
                selected_score REAL DEFAULT NULL,
                essay_score REAL DEFAULT NULL,
                record_score REAL DEFAULT NULL,
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        # Backward-compatible migrations for users who already ran an older version.
        _add_column_if_missing(conn, "daily_records", "self_study_min", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "daily_records", "cbt_practice_min", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "daily_records", "edited", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "daily_records", "late_entry", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "outputs", "evidence_hash", "TEXT DEFAULT ''")

        defaults = {
            "exam_date": "2028-01-11",
            "mock_july_date": "2027-07-15",
            "mock_october_date": "2027-10-15",
            "current_final_start": "2026-06-10",
            "current_final_end": "2026-06-21",
            "summer_break_end": "2026-08-31",
            "fall_semester_start": "2026-09-01",
            "midterm_start": "2026-10-19",
            "midterm_end": "2026-10-30",
            "final_start": "2026-12-07",
            "fall_semester_end": "2026-12-18",
            "winter_break_start": "2026-12-21",
            "spring_2027_start": "2027-03-02",
            "spring_2027_midterm_start": "2027-04-20",
            "spring_2027_midterm_end": "2027-05-01",
            "spring_2027_final_start": "2027-06-08",
            "spring_2027_final_end": "2027-06-19",
            "prior_probability": "0.70",
            "daily_min_score": "35",
            "daily_target_score": "70",
            "weekly_output_goal": "12",
            "weekly_mcq_goal": "200",
            "weekly_cbt_goal": "2",
            "public_delay_hours": "24",
            "public_include_evidence_hash": "false",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )


def upsert_daily(record: dict[str, Any]) -> None:
    record = record.copy()
    if isinstance(record.get("avoidance"), list):
        record["avoidance"] = json.dumps(record["avoidance"], ensure_ascii=False)

    record_date = _parse_date(record.get("date"))
    now = datetime.now()
    noon_after_record = datetime.combine(record_date + timedelta(days=1), time(hour=12))
    record["late_entry"] = int(record_date < date.today())

    fields = [
        "date",
        "checkin",
        "checkout",
        "location",
        "first_task",
        "completed_first",
        "lecture_min",
        "self_study_min",
        "cbt_practice_min",
        "study_blocks",
        "sleep_hours",
        "exercise_min",
        "mood",
        "energy",
        "anxiety",
        "avoidance",
        "note",
        "edited",
        "late_entry",
    ]
    with get_conn() as conn:
        existing = conn.execute("SELECT date FROM daily_records WHERE date=?", (record["date"],)).fetchone()
        record["edited"] = int(bool(existing) and now >= noon_after_record)
        values = [record.get(f) for f in fields]
        placeholders = ",".join(["?"] * len(fields))
        updates = ",".join([f"{f}=excluded.{f}" for f in fields[1:]]) + ",updated_at=CURRENT_TIMESTAMP"
        sql = f"""
            INSERT INTO daily_records({','.join(fields)}) VALUES ({placeholders})
            ON CONFLICT(date) DO UPDATE SET {updates}
        """
        conn.execute(sql, values)


def insert_output(record: dict[str, Any]) -> None:
    fields = [
        "date",
        "subject",
        "output_type",
        "quantity",
        "duration_min",
        "attempted",
        "correct",
        "score",
        "error_reason",
        "evidence_path",
        "evidence_hash",
        "note",
    ]
    values = [record.get(f) for f in fields]
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO outputs({','.join(fields)}) VALUES ({','.join(['?'] * len(fields))})",
            values,
        )


def insert_mock(record: dict[str, Any]) -> None:
    fields = [
        "date",
        "mock_name",
        "round_no",
        "total_score",
        "pass_cut",
        "top_percent",
        "selected_score",
        "essay_score",
        "record_score",
        "note",
    ]
    values = [record.get(f) for f in fields]
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO mocks({','.join(fields)}) VALUES ({','.join(['?'] * len(fields))})",
            values,
        )


def delete_row(table: str, row_id: int) -> None:
    if table not in {"outputs", "mocks"}:
        raise ValueError("Unsupported table")
    with get_conn() as conn:
        conn.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))


def get_settings() -> dict[str, str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def set_setting(key: str, value: Any) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )


def read_df(query: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=params or [])


def load_daily() -> pd.DataFrame:
    df = read_df("SELECT * FROM daily_records ORDER BY date")
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["avoidance"] = df["avoidance"].apply(_loads_list)
    return df


def load_outputs() -> pd.DataFrame:
    df = read_df("SELECT * FROM outputs ORDER BY date, id")
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def load_mocks() -> pd.DataFrame:
    df = read_df("SELECT * FROM mocks ORDER BY date, id")
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _loads_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()
