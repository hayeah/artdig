"""NGA (National Gallery of Art) CSV ingestion into a dedicated DuckDB database."""

from pathlib import Path

import duckdb

NGA_DATA = Path("data/nga/data")

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS nga_objects (
    objectid            VARCHAR PRIMARY KEY,
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
    artist_nationality  VARCHAR,
    artist_birth_year   INTEGER,
    artist_death_year   INTEGER,
    thumbnail_url       VARCHAR,
    credit_line         VARCHAR,
    wikidata_id         VARCHAR,
    extra               JSON
);
"""


class NgaIngester:
    """Ingests NGA open-data CSVs into nga_objects table."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, data_dir: Path = NGA_DATA):
        self.conn = conn
        self.objects = str(data_dir / "objects.csv")
        self.constituents = str(data_dir / "constituents.csv")
        self.obj_constituents = str(data_dir / "objects_constituents.csv")
        self.published_images = str(data_dir / "published_images.csv")
        self.objects_terms = str(data_dir / "objects_terms.csv")
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(SCHEMA_DDL)

    def run(self):
        self.conn.execute(f"""
            INSERT OR REPLACE INTO nga_objects
            WITH
            primary_artist AS (
                SELECT
                    oc.objectid,
                    c.preferreddisplayname AS artist_name,
                    c.nationality,
                    TRY_CAST(c.beginyear AS INTEGER) AS birth_year,
                    TRY_CAST(c.endyear AS INTEGER) AS death_year,
                    ROW_NUMBER() OVER (
                        PARTITION BY oc.objectid
                        ORDER BY oc.displayorder
                    ) AS rn
                FROM read_csv_auto('{self.obj_constituents}', all_varchar=true) oc
                JOIN read_csv_auto('{self.constituents}', all_varchar=true) c
                    ON oc.constituentid = c.constituentid
                WHERE oc.roletype = 'artist'
            ),
            primary_image AS (
                SELECT
                    depictstmsobjectid AS objectid,
                    iiifurl,
                    iiifthumburl,
                    ROW_NUMBER() OVER (
                        PARTITION BY depictstmsobjectid
                        ORDER BY sequence
                    ) AS rn
                FROM read_csv_auto('{self.published_images}', all_varchar=true)
                WHERE viewtype = 'primary'
            ),
            school_terms AS (
                SELECT
                    objectid,
                    FIRST(term ORDER BY term) AS culture
                FROM read_csv_auto('{self.objects_terms}', all_varchar=true)
                WHERE termtype = 'School'
                GROUP BY objectid
            ),
            style_terms AS (
                SELECT
                    objectid,
                    FIRST(term ORDER BY term) AS period
                FROM read_csv_auto('{self.objects_terms}', all_varchar=true)
                WHERE termtype = 'Style'
                GROUP BY objectid
            )
            SELECT
                o.objectid                                      AS objectid,
                o.title                                         AS title,
                NULLIF(o.classification, '')                     AS object_type,
                pa.artist_name                                  AS artist_name,
                NULLIF(o.displaydate, '')                        AS date_display,
                TRY_CAST(o.beginyear AS INTEGER)                 AS date_start,
                TRY_CAST(o.endyear AS INTEGER)                   AS date_end,
                NULLIF(o.medium, '')                              AS medium,
                NULLIF(o.dimensions, '')                          AS dimensions,
                NULLIF(o.classification, '')                      AS classification,
                CASE WHEN pi.iiifurl IS NOT NULL
                     THEN pi.iiifurl || '/full/max/0/default.jpg'
                     ELSE NULL END                               AS image_url,
                'https://www.nga.gov/collection/art-object-page.' || o.objectid || '.html'
                                                                 AS source_url,
                o.accessioned = '1'                              AS is_public_domain,
                NULLIF(o.departmentabbr, '')                      AS department,
                sc.culture                                       AS culture,
                st.period                                        AS period,
                pa.nationality                                   AS artist_nationality,
                pa.birth_year                                    AS artist_birth_year,
                pa.death_year                                    AS artist_death_year,
                pi.iiifthumburl                                  AS thumbnail_url,
                NULLIF(o.creditline, '')                          AS credit_line,
                NULLIF(o.wikidataid, '')                          AS wikidata_id,
                to_json({{
                    accession_num:                  NULLIF(o.accessionnum, ''),
                    sub_classification:             NULLIF(o.subclassification, ''),
                    visual_browser_classification:  NULLIF(o.visualbrowserclassification, ''),
                    visual_browser_timespan:        NULLIF(o.visualbrowsertimespan, ''),
                    parent_id:                      NULLIF(o.parentid, ''),
                    is_virtual:                     o.isvirtual = '1',
                    portfolio:                      NULLIF(o.portfolio, ''),
                    series:                         NULLIF(o.series, ''),
                    volume:                         NULLIF(o.volume, ''),
                    inscription:                    NULLIF(o.inscription, ''),
                    markings:                       NULLIF(o.markings, ''),
                    attribution_inverted:           NULLIF(o.attributioninverted, '')
                }})                                              AS extra
            FROM read_csv_auto('{self.objects}', all_varchar=true) o
            LEFT JOIN primary_artist pa
                ON o.objectid = pa.objectid AND pa.rn = 1
            LEFT JOIN primary_image pi
                ON o.objectid = pi.objectid AND pi.rn = 1
            LEFT JOIN school_terms sc
                ON o.objectid = sc.objectid
            LEFT JOIN style_terms st
                ON o.objectid = st.objectid
            WHERE o.objectid IS NOT NULL
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM nga_objects"
        ).fetchone()[0]
        print(f"NGA: ingested {count:,} objects into nga_objects")
