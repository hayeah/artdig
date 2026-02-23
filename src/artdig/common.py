"""Shared utilities for artdig ingesters."""

from datetime import UTC, datetime
from pathlib import Path

import duckdb


def now_utc() -> datetime:
    return datetime.now(UTC)


def open_db(path: Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))
