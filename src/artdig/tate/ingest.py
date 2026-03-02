"""Tate collection CSV ingestion into a dedicated DuckDB database.

Data source: https://github.com/tategallery/collection
~69k artworks from Tate Britain and Tate Modern (British art 1500s–present,
international modern/contemporary).
"""

from pathlib import Path

import duckdb

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS tate_objects (
    id                  INTEGER PRIMARY KEY,
    accession_number    VARCHAR,
    title               VARCHAR,
    artist_name         VARCHAR,
    artist_role         VARCHAR,
    artist_id           INTEGER,
    date_display        VARCHAR,
    date_start          INTEGER,
    medium              VARCHAR,
    dimensions          VARCHAR,
    width_mm            INTEGER,
    height_mm           INTEGER,
    depth_mm            INTEGER,
    credit_line         VARCHAR,
    year_acquired       INTEGER,
    image_url           VARCHAR,
    source_url          VARCHAR,
    is_public_domain    BOOLEAN,
    extra               JSON
);
"""

ARTISTS_DDL = """
CREATE TABLE IF NOT EXISTS tate_artists (
    id                  INTEGER PRIMARY KEY,
    name                VARCHAR,
    gender              VARCHAR,
    dates               VARCHAR,
    birth_year          INTEGER,
    death_year          INTEGER,
    place_of_birth      VARCHAR,
    place_of_death      VARCHAR,
    source_url          VARCHAR
);
"""


class TateIngester:
    """Ingests Tate collection CSVs into DuckDB."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, artworks_csv: Path, artists_csv: Path):
        self.conn = conn
        self.artworks_csv = artworks_csv
        self.artists_csv = artists_csv
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(SCHEMA_DDL)
        self.conn.execute(ARTISTS_DDL)

    def run(self):
        self._ingest_artists()
        self._ingest_artworks()

    def _ingest_artists(self):
        csv = str(self.artists_csv)
        self.conn.execute(f"""
            INSERT OR REPLACE INTO tate_artists
            SELECT
                TRY_CAST("id" AS INTEGER)                    AS id,
                NULLIF("name", '')                           AS name,
                NULLIF("gender", '')                         AS gender,
                NULLIF("dates", '')                          AS dates,
                TRY_CAST("yearOfBirth" AS INTEGER)           AS birth_year,
                TRY_CAST("yearOfDeath" AS INTEGER)           AS death_year,
                NULLIF("placeOfBirth", '')                   AS place_of_birth,
                NULLIF("placeOfDeath", '')                   AS place_of_death,
                NULLIF("url", '')                            AS source_url
            FROM read_csv_auto('{csv}', all_varchar=true)
            WHERE "id" IS NOT NULL AND "id" != ''
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM tate_artists"
        ).fetchone()[0]
        print(f"Tate: ingested {count:,} artists into tate_artists")

    def _ingest_artworks(self):
        csv = str(self.artworks_csv)
        self.conn.execute(f"""
            INSERT OR REPLACE INTO tate_objects
            SELECT
                TRY_CAST("id" AS INTEGER)                    AS id,
                NULLIF("accession_number", '')                AS accession_number,
                NULLIF("title", '')                          AS title,
                NULLIF("artist", '')                         AS artist_name,
                NULLIF("artistRole", '')                     AS artist_role,
                TRY_CAST("artistId" AS INTEGER)              AS artist_id,
                NULLIF("dateText", '')                       AS date_display,
                TRY_CAST("year" AS INTEGER)                  AS date_start,
                NULLIF("medium", '')                         AS medium,
                NULLIF("dimensions", '')                     AS dimensions,
                TRY_CAST("width" AS INTEGER)                 AS width_mm,
                TRY_CAST("height" AS INTEGER)                AS height_mm,
                TRY_CAST("depth" AS INTEGER)                 AS depth_mm,
                NULLIF("creditLine", '')                     AS credit_line,
                TRY_CAST("acquisitionYear" AS INTEGER)       AS year_acquired,
                NULLIF("thumbnailUrl", '')                   AS image_url,
                NULLIF("url", '')                            AS source_url,
                CASE WHEN "thumbnailCopyright" IS NULL OR "thumbnailCopyright" = ''
                     THEN true ELSE false END                AS is_public_domain,
                to_json({{
                    thumbnail_copyright: NULLIF("thumbnailCopyright", ''),
                    inscription:         NULLIF("inscription", ''),
                    units:               NULLIF("units", '')
                }})                                          AS extra
            FROM read_csv_auto('{csv}', all_varchar=true)
            WHERE "id" IS NOT NULL AND "id" != ''
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM tate_objects"
        ).fetchone()[0]
        print(f"Tate: ingested {count:,} artworks into tate_objects")
