"""Met Museum CSV ingestion into the artdig database."""

from pathlib import Path

import duckdb

MET_CSV = Path("data/met/MetObjects.csv")


class MetIngester:
    """Ingests Met Museum open-access CSV into the artworks table."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, csv_path: Path = MET_CSV):
        self.conn = conn
        self.csv_path = csv_path

    def run(self):
        csv = str(self.csv_path)
        self.conn.execute(f"""
            INSERT OR REPLACE INTO artworks
            SELECT
                'met'                                       AS source,
                "Object ID"                                 AS source_id,
                "Title"                                     AS title,
                NULLIF("Artist Display Name", '')           AS artist_name,
                NULLIF("Artist Nationality", '')            AS artist_nationality,
                TRY_CAST("Artist Begin Date" AS INTEGER)    AS artist_birth_year,
                TRY_CAST("Artist End Date" AS INTEGER)      AS artist_death_year,
                NULLIF("Object Date", '')                   AS date_display,
                TRY_CAST("Object Begin Date" AS INTEGER)    AS date_start,
                TRY_CAST("Object End Date" AS INTEGER)      AS date_end,
                NULLIF("Medium", '')                        AS medium,
                NULLIF("Dimensions", '')                    AS dimensions,
                NULLIF("Classification", '')                AS classification,
                NULLIF("Culture", '')                       AS culture,
                NULLIF("Period", '')                        AS period,
                NULLIF("Department", '')                    AS department,
                NULLIF("Country", '')                       AS country,
                NULLIF("City", '')                          AS city,
                NULLIF("Region", '')                        AS region,
                CASE WHEN "Is Public Domain" = 'True'
                     THEN true ELSE false END               AS is_public_domain,
                NULLIF("Credit Line", '')                   AS credit_line,
                -- Full image requires per-object API call; store the API URL
                'https://collectionapi.metmuseum.org/public/collection/v1/objects/' || "Object ID"
                                                            AS image_url,
                NULL                                        AS thumbnail_url,
                NULLIF("Link Resource", '')                 AS source_url,
                -- Extract Wikidata ID from URL like https://www.wikidata.org/wiki/Q123
                CASE WHEN "Object Wikidata URL" IS NOT NULL AND "Object Wikidata URL" != ''
                     THEN regexp_extract("Object Wikidata URL", '(Q\\d+)')
                     ELSE NULL END                          AS wikidata_id,
                to_json({{
                    object_number:          NULLIF("Object Number", ''),
                    is_highlight:           "Is Highlight" = 'True',
                    is_timeline_work:       "Is Timeline Work" = 'True',
                    gallery_number:         NULLIF("Gallery Number", ''),
                    accession_year:         NULLIF("AccessionYear", ''),
                    object_name:            NULLIF("Object Name", ''),
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
                    state:                  NULLIF("State", ''),
                    county:                 NULLIF("County", ''),
                    subregion:              NULLIF("Subregion", ''),
                    locale:                 NULLIF("Locale", ''),
                    locus:                  NULLIF("Locus", ''),
                    excavation:             NULLIF("Excavation", ''),
                    river:                  NULLIF("River", ''),
                    rights_and_reproduction: NULLIF("Rights and Reproduction", ''),
                    repository:             NULLIF("Repository", ''),
                    tags:                   NULLIF("Tags", ''),
                    tags_aat_url:           NULLIF("Tags AAT URL", ''),
                    tags_wikidata_url:      NULLIF("Tags Wikidata URL", '')
                }})                                         AS extras
            FROM read_csv_auto('{csv}', all_varchar=true)
            WHERE "Object ID" IS NOT NULL AND "Object ID" != ''
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM artworks WHERE source = 'met'"
        ).fetchone()[0]
        print(f"Met: ingested {count:,} artworks")
