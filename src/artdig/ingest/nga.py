"""NGA (National Gallery of Art) CSV ingestion into the artdig database."""

from pathlib import Path

import duckdb

NGA_DATA = Path("data/nga/data")
NGA_OBJECTS = NGA_DATA / "objects.csv"
NGA_CONSTITUENTS = NGA_DATA / "constituents.csv"
NGA_OBJ_CONSTITUENTS = NGA_DATA / "objects_constituents.csv"
NGA_PUBLISHED_IMAGES = NGA_DATA / "published_images.csv"
NGA_OBJECTS_TERMS = NGA_DATA / "objects_terms.csv"


class NgaIngester:
    """Ingests NGA open-data CSVs into the artworks table."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, data_dir: Path = NGA_DATA):
        self.conn = conn
        self.objects = str(data_dir / "objects.csv")
        self.constituents = str(data_dir / "constituents.csv")
        self.obj_constituents = str(data_dir / "objects_constituents.csv")
        self.published_images = str(data_dir / "published_images.csv")
        self.objects_terms = str(data_dir / "objects_terms.csv")

    def run(self):
        self.conn.execute(f"""
            INSERT OR REPLACE INTO artworks
            WITH
            -- Pick primary artist (first by display order, artist roletype only)
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
            -- Pick primary image (viewtype = 'primary', first by sequence)
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
            -- Culture from School term type (pick first alphabetically)
            school_terms AS (
                SELECT
                    objectid,
                    FIRST(term ORDER BY term) AS culture
                FROM read_csv_auto('{self.objects_terms}', all_varchar=true)
                WHERE termtype = 'School'
                GROUP BY objectid
            ),
            -- Period from Style term type (pick first alphabetically)
            style_terms AS (
                SELECT
                    objectid,
                    FIRST(term ORDER BY term) AS period
                FROM read_csv_auto('{self.objects_terms}', all_varchar=true)
                WHERE termtype = 'Style'
                GROUP BY objectid
            )
            SELECT
                'nga'                                           AS source,
                o.objectid                                      AS source_id,
                o.title                                         AS title,
                pa.artist_name                                  AS artist_name,
                pa.nationality                                  AS artist_nationality,
                pa.birth_year                                   AS artist_birth_year,
                pa.death_year                                   AS artist_death_year,
                NULLIF(o.displaydate, '')                       AS date_display,
                TRY_CAST(o.beginyear AS INTEGER)                AS date_start,
                TRY_CAST(o.endyear AS INTEGER)                  AS date_end,
                NULLIF(o.medium, '')                             AS medium,
                NULLIF(o.dimensions, '')                        AS dimensions,
                NULLIF(o.classification, '')                     AS classification,
                sc.culture                                      AS culture,
                st.period                                       AS period,
                NULLIF(o.departmentabbr, '')                     AS department,
                NULL                                            AS country,
                NULL                                            AS city,
                NULL                                            AS region,
                o.accessioned = '1'                             AS is_public_domain,
                NULLIF(o.creditline, '')                         AS credit_line,
                -- IIIF full image URL
                CASE WHEN pi.iiifurl IS NOT NULL
                     THEN pi.iiifurl || '/full/max/0/default.jpg'
                     ELSE NULL END                              AS image_url,
                pi.iiifthumburl                                 AS thumbnail_url,
                'https://www.nga.gov/collection/art-object-page.' || o.objectid || '.html'
                                                                AS source_url,
                NULLIF(o.wikidataid, '')                         AS wikidata_id,
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
                }})                                             AS extras
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
            "SELECT count(*) FROM artworks WHERE source = 'nga'"
        ).fetchone()[0]
        print(f"NGA: ingested {count:,} artworks")
