"""DDL constants for the artdig database."""

CREATE_ARTWORKS = """
CREATE TABLE IF NOT EXISTS artworks (
    source              VARCHAR NOT NULL,
    source_id           VARCHAR NOT NULL,
    title               VARCHAR,
    artist_name         VARCHAR,
    artist_nationality  VARCHAR,
    artist_birth_year   INTEGER,
    artist_death_year   INTEGER,
    date_display        VARCHAR,
    date_start          INTEGER,
    date_end            INTEGER,
    medium              VARCHAR,
    dimensions          VARCHAR,
    classification      VARCHAR,
    culture             VARCHAR,
    period              VARCHAR,
    department          VARCHAR,
    country             VARCHAR,
    city                VARCHAR,
    region              VARCHAR,
    is_public_domain    BOOLEAN,
    credit_line         VARCHAR,
    image_url           VARCHAR,
    thumbnail_url       VARCHAR,
    source_url          VARCHAR,
    wikidata_id         VARCHAR,
    extras              JSON,
    PRIMARY KEY (source, source_id)
);
"""
