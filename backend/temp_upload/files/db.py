import sqlite3
import json
import os
from datetime import datetime

# Bug fix #8: a bare filename resolves relative to whatever the current working
# directory is at runtime. Using __file__ makes the path absolute and stable
# regardless of where uvicorn / the process is launched from.
DATABASE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tech_debt.db")


def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            scan_time DATETIME,
            overall_score INTEGER,
            sensitivity TEXT,
            details_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_smells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            smell_id TEXT NOT NULL,
            accepted INTEGER NOT NULL DEFAULT 0,
            updated_at DATETIME,
            file TEXT,
            line_start INTEGER,
            line_end INTEGER,
            name TEXT,
            category TEXT,
            severity TEXT,
            UNIQUE(scan_id, smell_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_scan_smells_scan_id ON scan_smells(scan_id)")
    conn.commit()
    conn.close()


def save_scan(project_id: str, overall_score: int, sensitivity: str, details: dict):
    conn = get_db_connection()
    cur = conn.execute("""
        INSERT INTO scans (project_id, scan_time, overall_score, sensitivity, details_json)
        VALUES (?, ?, ?, ?, ?)
    """, (project_id, datetime.utcnow().isoformat(), overall_score, sensitivity, json.dumps(details)))
    conn.commit()
    scan_id = cur.lastrowid

    # Persist smell rows so "human sync rate" survives UI reloads.
    all_smells = (details or {}).get("all_smells", []) or []
    for smell in all_smells:
        conn.execute(
            """
            INSERT OR IGNORE INTO scan_smells (
                scan_id,
                smell_id,
                accepted,
                updated_at,
                file,
                line_start,
                line_end,
                name,
                category,
                severity
            ) VALUES (?, ?, 0, NULL, ?, ?, ?, ?, ?, ?)
            """,
            (
                scan_id,
                smell.get("smell_id"),
                smell.get("file"),
                smell.get("line_start", 0),
                smell.get("line_end", 0),
                smell.get("name"),
                smell.get("category", ""),
                smell.get("severity", ""),
            ),
        )

    conn.commit()
    conn.close()
    return scan_id


def get_history(project_id: str):
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT scan_time, overall_score, sensitivity
        FROM scans
        WHERE project_id = ?
        ORDER BY scan_time ASC
    """, (project_id,)).fetchall()
    conn.close()
    return [
        {"scan_time": row["scan_time"], "overall_score": row["overall_score"], "sensitivity": row["sensitivity"]}
        for row in rows
    ]


def get_human_sync(scan_id: int) -> dict:
    """
    Returns:
      - human_sync_rate: integer 0..100
      - accepted_count: integer
      - total_smells: integer
      - accepted_smell_ids: list[str]
    """
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_smells,
            COALESCE(SUM(accepted), 0) AS accepted_count
        FROM scan_smells
        WHERE scan_id = ?
        """,
        (scan_id,),
    ).fetchone()

    total_smells = int(row["total_smells"] or 0)
    accepted_count = int(row["accepted_count"] or 0)
    human_sync_rate = int(round((accepted_count / total_smells) * 100)) if total_smells > 0 else 0

    accepted_rows = conn.execute(
        """
        SELECT smell_id
        FROM scan_smells
        WHERE scan_id = ? AND accepted = 1
        """,
        (scan_id,),
    ).fetchall()
    accepted_smell_ids = [r["smell_id"] for r in accepted_rows]
    conn.close()

    return {
        "human_sync_rate": human_sync_rate,
        "accepted_count": accepted_count,
        "total_smells": total_smells,
        "accepted_smell_ids": accepted_smell_ids,
    }


def set_smell_acceptance(scan_id: int, smell_id: str, accepted: bool) -> dict:
    """
    Update persisted acceptance and return fresh human sync stats.
    """
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE scan_smells
        SET accepted = ?, updated_at = ?
        WHERE scan_id = ? AND smell_id = ?
        """,
        (1 if accepted else 0, datetime.utcnow().isoformat(), scan_id, smell_id),
    )
    conn.commit()
    conn.close()
    return get_human_sync(scan_id)
