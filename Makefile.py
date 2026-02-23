"""Data pipeline for artdig — public domain art catalogue.

Run with: pymake
List tasks: pymake list
"""

import os
from pathlib import Path

from pymake import sh, task

OUTPUT_DIR = Path("output")
TOUCH_DIR = OUTPUT_DIR / ".touch"
DATABASE = OUTPUT_DIR / "artdig.duckdb"
GETTY_DATABASE = OUTPUT_DIR / "getty.duckdb"
RIJKS_DATABASE = OUTPUT_DIR / "rijks.duckdb"

MET_CSV = Path("data/met/MetObjects.csv")
NGA_OBJECTS = Path("data/nga/data/objects.csv")


@task()
def submodules():
    """Update git submodules and pull LFS files."""
    sh("git submodule update --init --recursive")
    # LFS smudge: only convert if file is still a pointer (< 1KB)
    sh(
        "cd data/met && "
        "if [ $(wc -c < MetObjects.csv) -lt 1000 ]; then "
        "git lfs fetch origin master && "
        "git lfs smudge < MetObjects.csv > MetObjects_real.csv && "
        "mv MetObjects_real.csv MetObjects.csv; "
        "fi"
    )


@task(
    inputs=[submodules, MET_CSV],
    touch=TOUCH_DIR / "ingest_met",
)
def ingest_met():
    """Ingest Met Museum CSV into DuckDB."""
    TOUCH_DIR.mkdir(parents=True, exist_ok=True)
    from artdig.db import ArtdigDB
    from artdig.ingest.met import MetIngester

    with ArtdigDB(DATABASE) as db:
        MetIngester(db.conn).run()


@task(
    inputs=[submodules, NGA_OBJECTS],
    touch=TOUCH_DIR / "ingest_nga",
)
def ingest_nga():
    """Ingest NGA CSVs into DuckDB."""
    TOUCH_DIR.mkdir(parents=True, exist_ok=True)
    from artdig.db import ArtdigDB
    from artdig.ingest.nga import NgaIngester

    with ArtdigDB(DATABASE) as db:
        NgaIngester(db.conn).run()


@task()
def ingest_getty():
    """Ingest Getty ActivityStream + objects into a dedicated DuckDB.

    Optional environment variables:
      GETTY_FROM_PAGE=1
      GETTY_TO_PAGE=200
      GETTY_MAX_PAGES=50
      GETTY_MAX_OBJECTS=500
      GETTY_SLEEP_SECONDS=0.02
    """
    import duckdb
    from artdig.ingest.getty import GettyIngester, config_from_env

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(GETTY_DATABASE))
    try:
        cfg = config_from_env(GETTY_DATABASE)
        GettyIngester(conn).run(cfg)
    finally:
        conn.close()


@task()
def ingest_rijks():
    """Harvest Rijksmuseum collection via OAI-PMH into a dedicated DuckDB.

    Supports resumption — safe to interrupt and restart.
    Skips objects already in the DB (only adds set memberships).

    Optional environment variables:
      RIJKS_SET=260213         # OAI-PMH set to harvest (omit for all)
      RIJKS_MAX_PAGES=100
      RIJKS_SLEEP_SECONDS=0.1
      RIJKS_RESUME=1
    """
    import duckdb
    from artdig.ingest.rijks import RijksIngester, config_from_env

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(RIJKS_DATABASE))
    try:
        cfg = config_from_env()
        RijksIngester(conn).run(cfg)
    finally:
        conn.close()


@task()
def stats_rijks():
    """Print basic stats for the Rijksmuseum-only database."""
    import duckdb

    conn = duckdb.connect(str(RIJKS_DATABASE), read_only=True)
    try:
        rows = conn.execute("""
            SELECT
                count(*) AS objects,
                count(*) FILTER (WHERE image_url IS NOT NULL) AS with_image,
                count(*) FILTER (WHERE creator_name IS NOT NULL) AS with_creator,
                count(*) FILTER (WHERE date_created IS NOT NULL) AS with_date
            FROM rijks_objects
        """).fetchone()
        print("=== Rijksmuseum Dataset ===")
        print(f"  db: {RIJKS_DATABASE}")
        print(f"  objects: {rows[0]:,}")
        print(f"  with image: {rows[1]:,}")
        print(f"  with creator: {rows[2]:,}")
        print(f"  with date: {rows[3]:,}")
    finally:
        conn.close()


@task()
def ingest_getty_index():
    """Build Getty object index from SPARQL into output/getty.duckdb."""
    import duckdb
    from artdig.ingest.getty import GettyIngester

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(GETTY_DATABASE))
    try:
        GettyIngester(conn).build_object_index_from_sparql()
    finally:
        conn.close()


@task()
def ingest_getty_pending():
    """Hydrate pending Getty object URLs from index.

    Optional environment variables:
      GETTY_PENDING_LIMIT=1000
      GETTY_SLEEP_SECONDS=0.02
    """
    import duckdb
    from artdig.ingest.getty import GettyIngester, pending_limit_from_env

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(GETTY_DATABASE))
    try:
        limit = pending_limit_from_env(1000)
        sleep_seconds = float(os.getenv("GETTY_SLEEP_SECONDS", "0.02"))
        GettyIngester(conn).hydrate_pending_objects(limit=limit, sleep_seconds=sleep_seconds)
    finally:
        conn.close()


@task(inputs=[ingest_met, ingest_nga])
def ingest():
    """Run all ingestion tasks."""
    pass


@task(inputs=[ingest])
def stats():
    """Print catalogue summary statistics."""
    from artdig.db import ArtdigDB
    from artdig.stats import CatalogueStats

    with ArtdigDB(DATABASE) as db:
        CatalogueStats(db.conn).run()


@task()
def stats_getty():
    """Print basic stats for the Getty-only database."""
    import duckdb

    conn = duckdb.connect(str(GETTY_DATABASE), read_only=True)
    try:
        rows = conn.execute("""
            SELECT
                count(*) AS objects,
                count(*) FILTER (WHERE image_url IS NOT NULL) AS with_image,
                count(*) FILTER (WHERE iiif_manifest_url IS NOT NULL) AS with_manifest,
                count(*) FILTER (WHERE is_metadata_cc0) AS metadata_cc0
            FROM getty_objects
        """).fetchone()
        print("=== Getty Dataset ===")
        print(f"  db: {GETTY_DATABASE}")
        print(f"  objects: {rows[0]:,}")
        print(f"  with image: {rows[1]:,}")
        print(f"  with manifest: {rows[2]:,}")
        print(f"  metadata cc0: {rows[3]:,}")
    finally:
        conn.close()


task.default("ingest")
