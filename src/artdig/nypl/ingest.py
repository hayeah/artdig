"""NYPL public-domain data dump ingestion into a dedicated DuckDB database.

Data source: https://github.com/NYPL-publicdomain/data-and-utilities
~190k public domain items with metadata and image capture URLs.
Snapshot from December 2015.
"""

from pathlib import Path

import duckdb

ITEMS_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS nypl_objects (
    uuid                VARCHAR PRIMARY KEY,
    database_id         INTEGER,
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
    is_public_domain    BOOLEAN DEFAULT true,
    collection_uuid     VARCHAR,
    collection_title    VARCHAR,
    container_uuid      VARCHAR,
    container_title     VARCHAR,
    parent_hierarchy    VARCHAR,
    num_captures        INTEGER,
    accession_number    VARCHAR,
    call_number         VARCHAR,
    bnumber             VARCHAR,
    extra               JSON
);
"""

COLLECTIONS_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS nypl_collections (
    uuid                VARCHAR PRIMARY KEY,
    database_id         INTEGER,
    title               VARCHAR,
    num_items           INTEGER,
    source_url          VARCHAR,
    extra               JSON
);
"""


class NYPLIngester:
    """Ingests NYPL public-domain NDJSON data dump into DuckDB."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, data_dir: Path):
        self.conn = conn
        self.data_dir = data_dir
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(ITEMS_SCHEMA_DDL)
        self.conn.execute(COLLECTIONS_SCHEMA_DDL)

    def run(self):
        self._ingest_items()
        self._ingest_collections()

    def _ingest_items(self):
        items_glob = str(self.data_dir / "items" / "*.ndjson")
        self.conn.execute(f"""
            INSERT OR REPLACE INTO nypl_objects
            SELECT
                CAST("UUID" AS VARCHAR)                               AS uuid,
                CAST("databaseID" AS INTEGER)                         AS database_id,
                NULLIF(CAST(title AS VARCHAR), '')                    AS title,
                CASE WHEN "resourceType" IS NOT NULL
                     THEN array_to_string("resourceType", ', ')
                     ELSE NULL END                                    AS object_type,
                CASE WHEN contributor IS NOT NULL AND len(contributor) > 0
                     THEN contributor[1].contributorName
                     ELSE NULL END                                    AS artist_name,
                CASE WHEN date IS NOT NULL AND len(date) > 0
                     THEN CAST(date[1] AS VARCHAR)
                     ELSE NULL END                                    AS date_display,
                TRY_CAST("dateStart" AS INTEGER)                      AS date_start,
                TRY_CAST("dateEnd" AS INTEGER)                        AS date_end,
                CASE WHEN "physicalDescriptionForm" IS NOT NULL
                          AND len("physicalDescriptionForm") > 0
                     THEN array_to_string("physicalDescriptionForm", ', ')
                     ELSE NULL END                                    AS medium,
                CASE WHEN "physicalDescriptionExtent" IS NOT NULL
                          AND len("physicalDescriptionExtent") > 0
                     THEN array_to_string("physicalDescriptionExtent", ', ')
                     ELSE NULL END                                    AS dimensions,
                CASE WHEN genre IS NOT NULL AND len(genre) > 0
                     THEN array_to_string(
                         list_transform(genre, g -> g.text), ', ')
                     ELSE NULL END                                    AS classification,
                CASE WHEN captures IS NOT NULL AND len(captures) > 0
                     THEN CAST(captures[1] AS VARCHAR)
                     ELSE NULL END                                    AS image_url,
                NULLIF(CAST("digitalCollectionsURL" AS VARCHAR), '')  AS source_url,
                true                                                  AS is_public_domain,
                NULLIF(CAST("collectionUUID" AS VARCHAR), '')         AS collection_uuid,
                NULLIF(CAST("collectionTitle" AS VARCHAR), '')        AS collection_title,
                NULLIF(CAST("containerUUID" AS VARCHAR), '')          AS container_uuid,
                NULLIF(CAST("containerTitle" AS VARCHAR), '')         AS container_title,
                NULLIF(CAST("parentHierarchy" AS VARCHAR), '')        AS parent_hierarchy,
                TRY_CAST("numberOfCaptures" AS INTEGER)               AS num_captures,
                NULLIF(CAST("identifierAccessionNumber" AS VARCHAR), '') AS accession_number,
                NULLIF(CAST("identifierCallNumber" AS VARCHAR), '')   AS call_number,
                NULLIF(CAST("identifierBNumber" AS VARCHAR), '')      AS bnumber,
                to_json({{
                    alternative_title: "alternativeTitle",
                    all_contributors:  contributor,
                    all_captures:      captures,
                    language:          language,
                    description:       description,
                    note:              note,
                    subject_topical:   "subjectTopical",
                    subject_name:      "subjectName",
                    subject_geographic: "subjectGeographic",
                    subject_temporal:  "subjectTemporal",
                    subject_title:     "subjectTitle",
                    publisher:         publisher,
                    place_of_publication: "placeOfPublication",
                    identifier_isbn:   "identifierISBN",
                    identifier_issn:   "identifierISSN",
                    identifier_lccn:   "identifierLCCN",
                    identifier_oclc:   "identifierOCLCRLIN"
                }})                                                   AS extra
            FROM read_json('{items_glob}',
                format='newline_delimited',
                ignore_errors=true,
                union_by_name=true
            )
            WHERE "UUID" IS NOT NULL
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM nypl_objects"
        ).fetchone()[0]
        print(f"NYPL: ingested {count:,} items into nypl_objects")

    def _ingest_collections(self):
        collections_file = str(self.data_dir / "collections" / "pd_collections.ndjson")
        self.conn.execute(f"""
            INSERT OR REPLACE INTO nypl_collections
            SELECT
                CAST("UUID" AS VARCHAR)                               AS uuid,
                CAST("databaseID" AS INTEGER)                         AS database_id,
                NULLIF(CAST(title AS VARCHAR), '')                    AS title,
                TRY_CAST("numberOfItems" AS INTEGER)                  AS num_items,
                NULLIF(CAST("digitalCollectionsURL" AS VARCHAR), '')  AS source_url,
                to_json({{
                    alternative_title: "alternativeTitle",
                    contributor:       contributor,
                    date:              date,
                    date_start:        "dateStart",
                    date_end:          "dateEnd",
                    description:       description,
                    note:              note,
                    subject_topical:   "subjectTopical",
                    subject_name:      "subjectName",
                    subject_geographic: "subjectGeographic",
                    resource_type:     "resourceType",
                    genre:             genre,
                    identifier_bnumber: "identifierBNumber",
                    call_number:       "identifierCallNumber",
                    identifier_oclc:   "identifierOCLCRLIN",
                    physical_extent:   "physicalDescriptionExtent",
                    publisher:         publisher,
                    place_of_publication: "placeOfPublication"
                }})                                                   AS extra
            FROM read_json('{collections_file}',
                format='newline_delimited',
                ignore_errors=true,
                union_by_name=true
            )
            WHERE "UUID" IS NOT NULL
        """)
        count = self.conn.execute(
            "SELECT count(*) FROM nypl_collections"
        ).fetchone()[0]
        print(f"NYPL: ingested {count:,} collections into nypl_collections")
