"""Cleveland Museum of Art CSV ingestion into a dedicated DuckDB database.

Data source: https://github.com/ClevelandMuseumArt/openaccess
~61k artworks spanning 6,000 years of art history.
"""

from pathlib import Path

import duckdb

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS cma_objects (
    id                  INTEGER PRIMARY KEY,
    accession_number    VARCHAR,
    title               VARCHAR,
    artist_name         VARCHAR,
    culture             VARCHAR,
    date_display        VARCHAR,
    date_start          INTEGER,
    date_end            INTEGER,
    medium              VARCHAR,
    dimensions          VARCHAR,
    classification      VARCHAR,
    department          VARCHAR,
    collection          VARCHAR,
    credit_line         VARCHAR,
    description         VARCHAR,
    current_location    VARCHAR,
    image_url           VARCHAR,
    source_url          VARCHAR,
    is_public_domain    BOOLEAN,
    extra               JSON
);
"""


class CMAIngester:
    """Ingests Cleveland Museum of Art open-access CSV into cma_objects table."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, csv_path: Path):
        self.conn = conn
        self.csv_path = csv_path
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(SCHEMA_DDL)

    def run(self):
        csv = str(self.csv_path)
        self.conn.execute(f"""
            INSERT OR REPLACE INTO cma_objects
            SELECT
                TRY_CAST("id" AS INTEGER)                        AS id,
                NULLIF("accession_number", '')                   AS accession_number,
                NULLIF("title", '')                              AS title,
                NULLIF("creators", '')                           AS artist_name,
                NULLIF("culture", '')                            AS culture,
                NULLIF("creation_date", '')                      AS date_display,
                TRY_CAST("creation_date_earliest" AS INTEGER)    AS date_start,
                TRY_CAST("creation_date_latest" AS INTEGER)      AS date_end,
                NULLIF("technique", '')                          AS medium,
                NULLIF("measurements", '')                       AS dimensions,
                NULLIF("type", '')                               AS classification,
                NULLIF("department", '')                         AS department,
                NULLIF("collection", '')                         AS collection,
                NULLIF("creditline", '')                         AS credit_line,
                NULLIF("description", '')                        AS description,
                NULLIF("current_location", '')                   AS current_location,
                NULLIF("image_web", '')                          AS image_url,
                NULLIF("url", '')                                AS source_url,
                "share_license_status" = 'CC0'                   AS is_public_domain,
                to_json({{
                    tombstone:              NULLIF("tombstone", ''),
                    title_original:         NULLIF("title_in_original_language", ''),
                    series:                 NULLIF("series", ''),
                    artists_tags:           NULLIF("artists_tags", ''),
                    support_materials:      NULLIF("support_materials", ''),
                    copyright:              NULLIF("copyright", ''),
                    inscriptions:           NULLIF("inscriptions", ''),
                    exhibitions:            NULLIF("exhibitions", ''),
                    provenance:             NULLIF("provenance", ''),
                    find_spot:              NULLIF("find_spot", ''),
                    related_works:          NULLIF("related_works", ''),
                    did_you_know:           NULLIF("did_you_know", ''),
                    external_resources:     NULLIF("external_resources", ''),
                    citations:              NULLIF("citations", ''),
                    catalogue_raisonne:     NULLIF("catalogue_raisonne", ''),
                    image_print:            NULLIF("image_print", ''),
                    image_full:             NULLIF("image_full", ''),
                    alternate_images:       NULLIF("alternate_images", ''),
                    sketchfab_id:           NULLIF("sketchfab_id", ''),
                    sketchfab_url:          NULLIF("sketchfab_url", ''),
                    gallery_donor_text:     NULLIF("gallery_donor_text", ''),
                    state_of_the_work:      NULLIF("state_of_the_work", ''),
                    edition_of_the_work:    NULLIF("edition_of_the_work", ''),
                    share_license_status:   NULLIF("share_license_status", ''),
                    updated_at:             NULLIF("updated_at", '')
                }})                                              AS extra
            FROM read_csv_auto('{csv}', all_varchar=true)
            WHERE "id" IS NOT NULL AND "id" != ''
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM cma_objects"
        ).fetchone()[0]
        print(f"CMA: ingested {count:,} objects into cma_objects")
