"""MoMA collection CSV ingestion into a dedicated DuckDB database.

Data source: https://github.com/MuseumofModernArt/collection
~173k artworks spanning modern and contemporary art (1880s–present).
"""

from pathlib import Path

import duckdb

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS moma_objects (
    object_id           INTEGER PRIMARY KEY,
    title               VARCHAR,
    artist_name         VARCHAR,
    artist_bio          VARCHAR,
    artist_nationality  VARCHAR,
    artist_birth_year   INTEGER,
    artist_death_year   INTEGER,
    artist_gender       VARCHAR,
    date_display        VARCHAR,
    date_acquired       VARCHAR,
    medium              VARCHAR,
    dimensions          VARCHAR,
    classification      VARCHAR,
    department          VARCHAR,
    credit_line         VARCHAR,
    accession_number    VARCHAR,
    image_url           VARCHAR,
    source_url          VARCHAR,
    is_public_domain    BOOLEAN DEFAULT true,
    extra               JSON
);
"""


class MoMAIngester:
    """Ingests MoMA open-access CSV into moma_objects table."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, csv_path: Path):
        self.conn = conn
        self.csv_path = csv_path
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(SCHEMA_DDL)

    def run(self):
        csv = str(self.csv_path)
        self.conn.execute(f"""
            INSERT OR REPLACE INTO moma_objects
            SELECT
                TRY_CAST("ObjectID" AS INTEGER)              AS object_id,
                NULLIF("Title", '')                          AS title,
                NULLIF("Artist", '')                         AS artist_name,
                NULLIF("ArtistBio", '')                      AS artist_bio,
                NULLIF("Nationality", '')                    AS artist_nationality,
                TRY_CAST(regexp_extract("BeginDate", '(-?\\d+)') AS INTEGER)
                                                             AS artist_birth_year,
                CASE WHEN TRY_CAST("EndDate" AS INTEGER) = 0
                     THEN NULL
                     ELSE TRY_CAST("EndDate" AS INTEGER)
                END                                          AS artist_death_year,
                NULLIF("Gender", '')                         AS artist_gender,
                NULLIF("Date", '')                           AS date_display,
                NULLIF("DateAcquired", '')                   AS date_acquired,
                NULLIF("Medium", '')                         AS medium,
                NULLIF("Dimensions", '')                     AS dimensions,
                NULLIF("Classification", '')                 AS classification,
                NULLIF("Department", '')                     AS department,
                NULLIF("CreditLine", '')                     AS credit_line,
                NULLIF("AccessionNumber", '')                AS accession_number,
                NULLIF("ImageURL", '')                       AS image_url,
                NULLIF("URL", '')                            AS source_url,
                true                                         AS is_public_domain,
                to_json({{
                    constituent_id: NULLIF("ConstituentID", ''),
                    cataloged:      NULLIF("Cataloged", ''),
                    on_view:        NULLIF("OnView", ''),
                    circumference_cm: TRY_CAST("Circumference (cm)" AS DOUBLE),
                    depth_cm:       TRY_CAST("Depth (cm)" AS DOUBLE),
                    diameter_cm:    TRY_CAST("Diameter (cm)" AS DOUBLE),
                    height_cm:      TRY_CAST("Height (cm)" AS DOUBLE),
                    length_cm:      TRY_CAST("Length (cm)" AS DOUBLE),
                    weight_kg:      TRY_CAST("Weight (kg)" AS DOUBLE),
                    width_cm:       TRY_CAST("Width (cm)" AS DOUBLE),
                    seat_height_cm: TRY_CAST("Seat Height (cm)" AS DOUBLE),
                    duration_sec:   TRY_CAST("Duration (sec.)" AS DOUBLE)
                }})                                          AS extra
            FROM read_csv_auto('{csv}', all_varchar=true)
            WHERE "ObjectID" IS NOT NULL AND "ObjectID" != ''
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM moma_objects"
        ).fetchone()[0]
        print(f"MoMA: ingested {count:,} objects into moma_objects")
