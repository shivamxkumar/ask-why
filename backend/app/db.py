"""SQLite persistence: one JSON document per investigation. A new connection per call keeps it thread-safe."""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional

from app.schemas import Investigation, InvestigationSummary

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "askwhy.db"


def db_path() -> Path:
    return Path(os.environ.get("ASKWHY_DB") or DEFAULT_PATH)


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS investigations ("
        "id TEXT PRIMARY KEY, name TEXT NOT NULL, json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    return conn


def save(inv: Investigation) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO investigations (id, name, json, created_at, updated_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, json=excluded.json, updated_at=excluded.updated_at",
            (inv.id, inv.name, inv.model_dump_json(), inv.created_at, inv.updated_at),
        )


def get(inv_id: str) -> Optional[Investigation]:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT json FROM investigations WHERE id = ?", (inv_id,)).fetchone()
    return Investigation.model_validate_json(row[0]) if row else None


def list_summaries() -> list[InvestigationSummary]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT json FROM investigations ORDER BY created_at DESC, id DESC").fetchall()
    out = []
    for (raw,) in rows:
        inv = Investigation.model_validate_json(raw)
        out.append(InvestigationSummary(
            id=inv.id, name=inv.name, mode=inv.mode, status=inv.status, created_at=inv.created_at, updated_at=inv.updated_at,
            source_count=len(inv.sources), finding_count=len(inv.findings),
            open_count=sum(1 for f in inv.findings if f.status == "open"),
        ))
    return out


def delete(inv_id: str) -> bool:
    with closing(_connect()) as conn, conn:
        cur = conn.execute("DELETE FROM investigations WHERE id = ?", (inv_id,))
    return cur.rowcount > 0
