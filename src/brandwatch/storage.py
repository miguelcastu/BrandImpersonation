"""SQLite persistence for discovery candidates and their sources."""

import sqlite3
from pathlib import Path

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
