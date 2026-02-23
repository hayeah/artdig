"""Data pipeline for artdig — public domain art catalogue.

Run with: pymake
List tasks: pymake list
"""

from pathlib import Path

from pymake import sh, task

OUTPUT_DIR = Path("output")
TOUCH_DIR = OUTPUT_DIR / ".touch"
MET_DATABASE = OUTPUT_DIR / "met.duckdb"
NGA_DATABASE = OUTPUT_DIR / "nga.duckdb"
GETTY_DATABASE = OUTPUT_DIR / "getty.duckdb"
RIJKS_DATABASE = OUTPUT_DIR / "rijks.duckdb"

MET_CSV = Path("data/met/MetObjects.csv")
NGA_OBJECTS = Path("data/nga/data/objects.csv")

RIJKS_DATA_DIR = Path("data/rijks")
RIJKS_LIDO_ZIP = RIJKS_DATA_DIR / "202001-rma-lido-collection.zip"

_RIJKS_RELEASE = "https://github.com/Rijksmuseum/rijksmuseum.github.io/releases/download/1.0.0"
_RIJKS_ZIPS = [
    "202001-rma-lido-collection.zip",
    "202001-rma-csv-collection.zip",
    "202001-rma-dc-collection.zip",
    "201911-rma-edm-actors.zip",
]


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
    """Ingest Met Museum CSV into output/met.duckdb."""
    TOUCH_DIR.mkdir(parents=True, exist_ok=True)
    from artdig.common import open_db
    from artdig.met.ingest import MetIngester

    conn = open_db(MET_DATABASE)
    try:
        MetIngester(conn).run()
    finally:
        conn.close()


@task(
    inputs=[submodules, NGA_OBJECTS],
    touch=TOUCH_DIR / "ingest_nga",
)
def ingest_nga():
    """Ingest NGA CSVs into output/nga.duckdb."""
    TOUCH_DIR.mkdir(parents=True, exist_ok=True)
    from artdig.common import open_db
    from artdig.nga.ingest import NgaIngester

    conn = open_db(NGA_DATABASE)
    try:
        NgaIngester(conn).run()
    finally:
        conn.close()


@task()
def ingest_getty(
    from_page: int = 1,
    to_page: int | None = None,
    max_pages: int | None = None,
    max_objects: int | None = None,
    sleep_seconds: float = 0.02,
):
    """Ingest Getty ActivityStream + objects into output/getty.duckdb."""
    from artdig.common import open_db
    from artdig.getty.ingest import GettyConfig, GettyIngester

    conn = open_db(GETTY_DATABASE)
    try:
        cfg = GettyConfig(
            from_page=from_page,
            to_page=to_page,
            max_pages=max_pages,
            max_objects=max_objects,
            sleep_seconds=sleep_seconds,
        )
        GettyIngester(conn).run(cfg)
    finally:
        conn.close()


@task(outputs=[RIJKS_LIDO_ZIP])
def download_rijks():
    """Download Rijksmuseum historical data dumps from GitHub."""
    import urllib.request

    RIJKS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in _RIJKS_ZIPS:
        dest = RIJKS_DATA_DIR / name
        if dest.exists():
            print(f"  skip {name} (exists)")
            continue
        url = f"{_RIJKS_RELEASE}/{name}"
        print(f"  downloading {name} ...")
        urllib.request.urlretrieve(url, dest)
        print(f"  saved {dest} ({dest.stat().st_size / 1e6:.0f} MB)")


@task()
def ingest_rijks(
    set: str | None = None,
    max_pages: int | None = None,
    sleep_seconds: float = 0.1,
    resume: bool = True,
):
    """Harvest Rijksmuseum collection via OAI-PMH into output/rijks.duckdb.

    Supports resumption — safe to interrupt and restart.
    Skips objects already in the DB (only adds set memberships).
    """
    from artdig.common import open_db
    from artdig.rijks.ingest import RijksConfig, RijksIngester

    conn = open_db(RIJKS_DATABASE)
    try:
        cfg = RijksConfig(
            set_spec=set,
            max_pages=max_pages,
            sleep_seconds=sleep_seconds,
            resume=resume,
        )
        RijksIngester(conn).run(cfg)
    finally:
        conn.close()


@task()
def rijks_list_sets():
    """List Rijksmuseum OAI-PMH sets with object counts (syncs from API first)."""
    from artdig.common import open_db
    from artdig.rijks.ingest import RijksIngester

    conn = open_db(RIJKS_DATABASE)
    try:
        RijksIngester(conn).sync_sets()
        rows = conn.execute("""
            SELECT s.set_spec, s.set_name, s.record_count,
                   count(os.identifier) AS n
            FROM rijks_sets s
            LEFT JOIN rijks_object_sets os ON s.set_spec = os.set_spec
            GROUP BY s.set_spec, s.set_name, s.record_count
            ORDER BY n DESC, s.set_spec
        """).fetchall()
        print(f"{'set':>10}  {'total':>7}  {'local':>6}  name")
        print(f"{'---':>10}  {'-----':>7}  {'-----':>6}  ----")
        for spec, name, record_count, n in rows:
            total = f"{record_count:,}" if record_count else "?"
            local = f"{n:,}" if n > 0 else "-"
            print(f"{spec:>10}  {total:>7}  {local:>6}  {name}")
    finally:
        conn.close()


@task()
def rijks_probe_sizes(sleep_seconds: float = 0.2):
    """Probe each Rijks set with one OAI-PMH request to get record counts."""
    from artdig.common import open_db
    from artdig.rijks.ingest import RijksIngester

    conn = open_db(RIJKS_DATABASE)
    try:
        RijksIngester(conn).probe_set_sizes(sleep_seconds=sleep_seconds)
    finally:
        conn.close()


@task()
def reparse_rijks():
    """Re-parse all Rijks objects from stored raw XML (no network)."""
    from artdig.common import open_db
    from artdig.rijks.ingest import RijksIngester

    conn = open_db(RIJKS_DATABASE)
    try:
        RijksIngester(conn).reparse()
    finally:
        conn.close()


@task()
def stats_rijks():
    """Print basic stats for the Rijksmuseum-only database."""
    from artdig.common import open_db

    conn = open_db(RIJKS_DATABASE)
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
    from artdig.common import open_db
    from artdig.getty.ingest import GettyIngester

    conn = open_db(GETTY_DATABASE)
    try:
        GettyIngester(conn).build_object_index_from_sparql()
    finally:
        conn.close()


@task()
def ingest_getty_pending(
    limit: int = 1000,
    sleep_seconds: float = 0.02,
):
    """Hydrate pending Getty object URLs from index."""
    from artdig.common import open_db
    from artdig.getty.ingest import GettyIngester

    conn = open_db(GETTY_DATABASE)
    try:
        GettyIngester(conn).hydrate_pending_objects(limit=limit, sleep_seconds=sleep_seconds)
    finally:
        conn.close()


@task(inputs=[ingest_met, ingest_nga])
def ingest():
    """Run all ingestion tasks."""
    pass


@task()
def stats_getty():
    """Print basic stats for the Getty-only database."""
    from artdig.common import open_db

    conn = open_db(GETTY_DATABASE)
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
