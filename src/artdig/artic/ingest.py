"""Art Institute of Chicago data dump ingestion into a dedicated DuckDB database."""

from pathlib import Path

import duckdb

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS artic_objects (
    id                  INTEGER PRIMARY KEY,
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
    place_of_origin     VARCHAR,
    credit_line         VARCHAR,
    accession_number    VARCHAR,
    extra               JSON
);
"""


class ArticIngester:
    """Ingests Art Institute of Chicago JSON data dump into artic_objects table."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, data_dir: Path):
        self.conn = conn
        self.data_dir = data_dir
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(SCHEMA_DDL)

    def run(self):
        json_glob = str(self.data_dir / "artic-api-data" / "json" / "artworks" / "*.json")
        self.conn.execute(f"""
            INSERT OR REPLACE INTO artic_objects
            SELECT
                CAST(id AS INTEGER)                              AS id,
                NULLIF(title, '')                                AS title,
                NULLIF(artwork_type_title, '')                   AS object_type,
                NULLIF(artist_display, '')                       AS artist_name,
                NULLIF(date_display, '')                         AS date_display,
                TRY_CAST(date_start AS INTEGER)                  AS date_start,
                TRY_CAST(date_end AS INTEGER)                    AS date_end,
                NULLIF(medium_display, '')                       AS medium,
                NULLIF(dimensions, '')                           AS dimensions,
                CASE WHEN classification_titles IS NOT NULL
                     THEN array_to_string(classification_titles, ', ')
                     ELSE NULL END                               AS classification,
                CASE WHEN image_id IS NOT NULL AND image_id != ''
                     THEN 'https://www.artic.edu/iiif/2/' || image_id || '/full/843,/0/default.jpg'
                     ELSE NULL END                               AS image_url,
                'https://www.artic.edu/artworks/' || CAST(id AS VARCHAR)
                                                                 AS source_url,
                COALESCE(is_public_domain, false)                AS is_public_domain,
                NULLIF(department_title, '')                     AS department,
                NULLIF(place_of_origin, '')                      AS place_of_origin,
                NULLIF(credit_line, '')                          AS credit_line,
                NULLIF(main_reference_number, '')                AS accession_number,
                to_json({{
                    artist_title:         NULLIF(artist_title, ''),
                    style_titles:         style_titles,
                    term_titles:          term_titles,
                    category_titles:      category_titles,
                    material_titles:      material_titles,
                    technique_titles:     technique_titles,
                    subject_titles:       subject_titles,
                    theme_titles:         theme_titles,
                    inscriptions:         NULLIF(inscriptions, ''),
                    provenance_text:      NULLIF(provenance_text, ''),
                    publication_history:  NULLIF(publication_history, ''),
                    exhibition_history:   NULLIF(exhibition_history, ''),
                    catalogue_display:    NULLIF(catalogue_display, ''),
                    fiscal_year:          fiscal_year,
                    is_on_view:           is_on_view,
                    gallery_title:        NULLIF(gallery_title, ''),
                    gallery_id:           gallery_id,
                    colorfulness:         colorfulness,
                    color:                color,
                    latitude:             latitude,
                    longitude:            longitude
                }})                                              AS extra
            FROM read_json('{json_glob}',
                ignore_errors=true,
                union_by_name=true,
                columns={{
                    id: 'INTEGER',
                    title: 'VARCHAR',
                    artwork_type_title: 'VARCHAR',
                    artist_display: 'VARCHAR',
                    artist_title: 'VARCHAR',
                    date_display: 'VARCHAR',
                    date_start: 'INTEGER',
                    date_end: 'INTEGER',
                    medium_display: 'VARCHAR',
                    dimensions: 'VARCHAR',
                    classification_titles: 'VARCHAR[]',
                    image_id: 'VARCHAR',
                    is_public_domain: 'BOOLEAN',
                    department_title: 'VARCHAR',
                    place_of_origin: 'VARCHAR',
                    credit_line: 'VARCHAR',
                    main_reference_number: 'VARCHAR',
                    style_titles: 'VARCHAR[]',
                    term_titles: 'VARCHAR[]',
                    category_titles: 'VARCHAR[]',
                    material_titles: 'VARCHAR[]',
                    technique_titles: 'VARCHAR[]',
                    subject_titles: 'VARCHAR[]',
                    theme_titles: 'VARCHAR[]',
                    inscriptions: 'VARCHAR',
                    provenance_text: 'VARCHAR',
                    publication_history: 'VARCHAR',
                    exhibition_history: 'VARCHAR',
                    catalogue_display: 'VARCHAR',
                    fiscal_year: 'INTEGER',
                    is_on_view: 'BOOLEAN',
                    gallery_title: 'VARCHAR',
                    gallery_id: 'INTEGER',
                    colorfulness: 'DOUBLE',
                    color: 'JSON',
                    latitude: 'DOUBLE',
                    longitude: 'DOUBLE'
                }}
            )
            WHERE id IS NOT NULL
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM artic_objects"
        ).fetchone()[0]
        print(f"ARTIC: ingested {count:,} objects into artic_objects")
