"""Met Museum CSV ingestion into a dedicated DuckDB database."""

from pathlib import Path

import duckdb

MET_CSV = Path("data/met/MetObjects.csv")

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS met_objects (
    object_id           INTEGER PRIMARY KEY,
    title               VARCHAR,
    object_type         VARCHAR,
    artist_name         VARCHAR,
    date_display        VARCHAR,
    date_start          INTEGER,
    date_end            INTEGER,
    medium              VARCHAR,
    dimensions          VARCHAR,
    classification      VARCHAR,
    image_url           VARCHAR,
    source_url          VARCHAR,
    is_public_domain    BOOLEAN,
    department          VARCHAR,
    culture             VARCHAR,
    period              VARCHAR,
    country             VARCHAR,
    city                VARCHAR,
    artist_nationality  VARCHAR,
    artist_begin_date   VARCHAR,
    artist_end_date     VARCHAR,
    wikidata_id         VARCHAR,
    extra               JSON
);
"""


class MetIngester:
    """Ingests Met Museum open-access CSV into met_objects table."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, csv_path: Path = MET_CSV):
        self.conn = conn
        self.csv_path = csv_path
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(SCHEMA_DDL)

    def run(self):
        csv = str(self.csv_path)
        self.conn.execute(f"""
            INSERT OR REPLACE INTO met_objects
            SELECT
                TRY_CAST("Object ID" AS INTEGER)            AS object_id,
                NULLIF("Title", '')                          AS title,
                NULLIF("Object Name", '')                    AS object_type,
                NULLIF("Artist Display Name", '')            AS artist_name,
                NULLIF("Object Date", '')                    AS date_display,
                TRY_CAST("Object Begin Date" AS INTEGER)     AS date_start,
                TRY_CAST("Object End Date" AS INTEGER)       AS date_end,
                NULLIF("Medium", '')                         AS medium,
                NULLIF("Dimensions", '')                     AS dimensions,
                NULLIF("Classification", '')                 AS classification,
                'https://collectionapi.metmuseum.org/public/collection/v1/objects/' || "Object ID"
                                                             AS image_url,
                NULLIF("Link Resource", '')                  AS source_url,
                CASE WHEN "Is Public Domain" = 'True'
                     THEN true ELSE false END                AS is_public_domain,
                NULLIF("Department", '')                     AS department,
                NULLIF("Culture", '')                        AS culture,
                NULLIF("Period", '')                         AS period,
                NULLIF("Country", '')                        AS country,
                NULLIF("City", '')                           AS city,
                NULLIF("Artist Nationality", '')             AS artist_nationality,
                NULLIF("Artist Begin Date", '')              AS artist_begin_date,
                NULLIF("Artist End Date", '')                AS artist_end_date,
                CASE WHEN "Object Wikidata URL" IS NOT NULL AND "Object Wikidata URL" != ''
                     THEN regexp_extract("Object Wikidata URL", '(Q\\d+)')
                     ELSE NULL END                           AS wikidata_id,
                to_json({{
                    object_number:          NULLIF("Object Number", ''),
                    is_highlight:           "Is Highlight" = 'True',
                    is_timeline_work:       "Is Timeline Work" = 'True',
                    gallery_number:         NULLIF("Gallery Number", ''),
                    accession_year:         NULLIF("AccessionYear", ''),
                    dynasty:                NULLIF("Dynasty", ''),
                    reign:                  NULLIF("Reign", ''),
                    portfolio:              NULLIF("Portfolio", ''),
                    constituent_id:         NULLIF("Constituent ID", ''),
                    artist_role:            NULLIF("Artist Role", ''),
                    artist_prefix:          NULLIF(TRIM("Artist Prefix"), ''),
                    artist_display_bio:     NULLIF("Artist Display Bio", ''),
                    artist_suffix:          NULLIF(TRIM("Artist Suffix"), ''),
                    artist_alpha_sort:      NULLIF("Artist Alpha Sort", ''),
                    artist_gender:          NULLIF("Artist Gender", ''),
                    artist_ulan_url:        NULLIF("Artist ULAN URL", ''),
                    artist_wikidata_url:    NULLIF("Artist Wikidata URL", ''),
                    geography_type:         NULLIF("Geography Type", ''),
                    region:                 NULLIF("Region", ''),
                    state:                  NULLIF("State", ''),
                    county:                 NULLIF("County", ''),
                    subregion:              NULLIF("Subregion", ''),
                    locale:                 NULLIF("Locale", ''),
                    locus:                  NULLIF("Locus", ''),
                    excavation:             NULLIF("Excavation", ''),
                    river:                  NULLIF("River", ''),
                    credit_line:            NULLIF("Credit Line", ''),
                    rights_and_reproduction: NULLIF("Rights and Reproduction", ''),
                    repository:             NULLIF("Repository", ''),
                    tags:                   NULLIF("Tags", ''),
                    tags_aat_url:           NULLIF("Tags AAT URL", ''),
                    tags_wikidata_url:      NULLIF("Tags Wikidata URL", '')
                }})                                          AS extra
            FROM read_csv_auto('{csv}', all_varchar=true)
            WHERE "Object ID" IS NOT NULL AND "Object ID" != ''
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM met_objects"
        ).fetchone()[0]
        print(f"Met: ingested {count:,} objects into met_objects")
