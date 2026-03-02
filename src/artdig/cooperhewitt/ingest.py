"""Cooper Hewitt Smithsonian Design Museum CSV ingestion into DuckDB.

Data source: https://github.com/cooperhewitt/collection
~227k design objects (textiles, furniture, posters, wallpaper, jewelry, etc.).
Participants (artists/designers) are in a separate CSV joined by object_id.
"""

from pathlib import Path

import duckdb

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS cooperhewitt_objects (
    id                  INTEGER PRIMARY KEY,
    title               VARCHAR,
    artist_name         VARCHAR,
    artist_role         VARCHAR,
    object_type         VARCHAR,
    date_display        VARCHAR,
    date_start          INTEGER,
    date_end            INTEGER,
    decade              VARCHAR,
    medium              VARCHAR,
    dimensions          VARCHAR,
    classification      VARCHAR,
    department_id       INTEGER,
    credit_line         VARCHAR,
    accession_number    VARCHAR,
    image_url           VARCHAR,
    source_url          VARCHAR,
    is_public_domain    BOOLEAN DEFAULT true,
    country             VARCHAR,
    extra               JSON
);
"""


class CooperHewittIngester:
    """Ingests Cooper Hewitt collection CSVs into DuckDB."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, meta_dir: Path):
        self.conn = conn
        self.meta_dir = meta_dir
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(SCHEMA_DDL)

    def run(self):
        objects_csv = str(self.meta_dir / "objects.csv")
        participants_csv = str(self.meta_dir / "objects-participants.csv")

        # Build a CTE of primary artist per object (prefer Artist > Designer > Creator roles)
        self.conn.execute(f"""
            INSERT OR REPLACE INTO cooperhewitt_objects
            WITH ranked_participants AS (
                SELECT
                    TRY_CAST(object_id AS INTEGER) AS object_id,
                    person_name,
                    role_name,
                    person_date,
                    ROW_NUMBER() OVER (
                        PARTITION BY object_id
                        ORDER BY CASE role_name
                            WHEN 'Artist' THEN 1
                            WHEN 'Designer' THEN 2
                            WHEN 'Creator' THEN 3
                            WHEN 'Maker' THEN 4
                            WHEN 'Architect' THEN 5
                            WHEN 'Author' THEN 6
                            WHEN 'Engraver' THEN 7
                            WHEN 'Illustrator' THEN 8
                            WHEN 'Painter' THEN 9
                            WHEN 'Graphic Designer' THEN 10
                            WHEN 'Manufacturer' THEN 11
                            WHEN 'Publisher' THEN 12
                            ELSE 20
                        END
                    ) AS rn
                FROM read_csv_auto('{participants_csv}', all_varchar=true)
                WHERE role_name NOT IN ('Collector', 'Donor', 'Lender', 'Patron')
            ),
            primary_artist AS (
                SELECT object_id, person_name, role_name
                FROM ranked_participants
                WHERE rn = 1
            )
            SELECT
                TRY_CAST(o."id" AS INTEGER)                  AS id,
                NULLIF(o."title", '')                        AS title,
                pa.person_name                               AS artist_name,
                pa.role_name                                 AS artist_role,
                NULLIF(o."type", '')                         AS object_type,
                NULLIF(o."date", '')                         AS date_display,
                TRY_CAST(o."year_start" AS INTEGER)          AS date_start,
                TRY_CAST(o."year_end" AS INTEGER)            AS date_end,
                NULLIF(o."decade", '')                       AS decade,
                NULLIF(o."medium", '')                       AS medium,
                NULLIF(o."dimensions", '')                   AS dimensions,
                NULLIF(o."type", '')                         AS classification,
                TRY_CAST(o."department_id" AS INTEGER)       AS department_id,
                NULLIF(o."creditline", '')                   AS credit_line,
                NULLIF(o."accession_number", '')             AS accession_number,
                NULLIF(o."primary_image", '')                AS image_url,
                NULLIF(o."url", '')                          AS source_url,
                true                                         AS is_public_domain,
                NULLIF(o."woe:country_name", '')             AS country,
                to_json({{
                    title_raw:      NULLIF(o."title_raw", ''),
                    description:    NULLIF(o."description", ''),
                    gallery_text:   NULLIF(o."gallery_text", ''),
                    label_text:     NULLIF(o."label_text", ''),
                    inscribed:      NULLIF(o."inscribed", ''),
                    markings:       NULLIF(o."markings", ''),
                    signed:         NULLIF(o."signed", ''),
                    provenance:     NULLIF(o."provenance", ''),
                    justification:  NULLIF(o."justification", ''),
                    on_display:     NULLIF(o."on_display", ''),
                    is_loan_object: NULLIF(o."is_loan_object", ''),
                    tombstone:      NULLIF(o."tombstone", ''),
                    period_id:      TRY_CAST(o."period_id" AS INTEGER),
                    type_id:        TRY_CAST(o."type_id" AS INTEGER),
                    media_id:       TRY_CAST(o."media_id" AS INTEGER),
                    year_acquired:  TRY_CAST(o."year_acquired" AS INTEGER),
                    dimensions_raw: NULLIF(o."dimensions_raw", '')
                }})                                          AS extra
            FROM read_csv_auto('{objects_csv}', all_varchar=true) o
            LEFT JOIN primary_artist pa ON TRY_CAST(o."id" AS INTEGER) = pa.object_id
            WHERE o."id" IS NOT NULL AND o."id" != ''
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM cooperhewitt_objects"
        ).fetchone()[0]
        print(f"Cooper Hewitt: ingested {count:,} objects into cooperhewitt_objects")
