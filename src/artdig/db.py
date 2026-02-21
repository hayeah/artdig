"""Database connection and schema management."""

from pathlib import Path

import duckdb

from artdig.schema import CREATE_ARTWORKS

DEFAULT_DB_PATH = Path("output/artdig.duckdb")


class ArtdigDB:
    """Manages DuckDB connection and schema for the artdig catalogue."""

    def __init__(self, path: Path = DEFAULT_DB_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.path))
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(CREATE_ARTWORKS)

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
