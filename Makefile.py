"""Data pipeline for artdig — public domain art catalogue.

Run with: pymake
List tasks: pymake list
"""

from pathlib import Path

from pymake import sh, task

OUTPUT_DIR = Path("output")
TOUCH_DIR = OUTPUT_DIR / ".touch"
DATABASE = OUTPUT_DIR / "artdig.duckdb"

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


task.default("ingest")
