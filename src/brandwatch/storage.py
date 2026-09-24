"""SQLite persistence for discovery candidates and their sources."""

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brandwatch.collection import CollectionResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    hostname TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sightings (
    hostname TEXT NOT NULL REFERENCES candidates(hostname),
    source TEXT NOT NULL,
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (hostname, source)
);
CREATE TABLE IF NOT EXISTS collections (
    id TEXT PRIMARY KEY,
    hostname TEXT NOT NULL REFERENCES candidates(hostname),
    requested_url TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_path TEXT NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


def save_candidates(connection: sqlite3.Connection, hosts: set[str], source: str) -> int:
    with connection:
        for host in sorted(hosts):
            connection.execute(
                "INSERT INTO candidates (hostname) VALUES (?) "
                "ON CONFLICT(hostname) DO UPDATE SET last_seen = CURRENT_TIMESTAMP",
                (host,),
            )
            connection.execute(
                "INSERT INTO sightings (hostname, source) VALUES (?, ?) "
                "ON CONFLICT(hostname, source) DO UPDATE SET last_seen = CURRENT_TIMESTAMP",
                (host, source),
            )
    return len(hosts)


def list_candidates(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    return connection.execute(
        "SELECT c.hostname, group_concat(s.source, ',') "
        "FROM candidates c JOIN sightings s ON s.hostname = c.hostname "
        "GROUP BY c.hostname ORDER BY c.hostname"
    ).fetchall()


def save_collection(connection: sqlite3.Connection, result: "CollectionResult") -> None:
    """Keep an append-only index of successful and failed evidence captures."""
    with connection:
        connection.execute(
            "INSERT INTO collections "
            "(id, hostname, requested_url, collected_at, status, evidence_path, is_demo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                result.id,
                result.hostname,
                result.requested_url,
                result.completed_at,
                result.status,
                result.evidence_path,
                int(result.is_demo),
            ),
        )


def list_collections(connection: sqlite3.Connection, limit: int = 20) -> list[tuple]:
    return connection.execute(
        "SELECT id, hostname, status, evidence_path FROM collections "
        "ORDER BY collected_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
