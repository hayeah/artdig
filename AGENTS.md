# artdig — Agent Notes

## Build System: pymake

Tasks are defined in `Makefile.py`. Run with `uv run pymake <task>`.

```bash
uv run pymake list          # show all tasks with vars
uv run pymake ingest        # run default (met + nga)
uv run pymake -B ingest_met # force re-run
```

### Task Vars

Tasks accept typed parameters instead of environment variables. Set them via `--vars`:

```bash
# dot notation
uv run pymake ingest_rijks --vars ingest_rijks.set=260213

# multiple vars
uv run pymake ingest_getty --vars ingest_getty.max_pages=50 --vars ingest_getty.from_page=10

# bulk JSON
uv run pymake ingest_getty --vars 'ingest_getty={"max_pages":50,"max_objects":500}'

# from TOML file
uv run pymake ingest_getty --vars-file vars/dev.toml
```

When defining new tasks, declare parameters in the function signature — do NOT use `os.getenv()`:

```python
@task()
def my_task(limit: int = 100, dry_run: bool = False):
    ...
```

Supported types: `str`, `int`, `float`, `bool`, `Path`, and optional forms (`str | None`).

## Project Layout

```
src/artdig/
    common.py          # now_utc(), open_db()
    met/ingest.py      # → output/met.duckdb   (met_objects)
    nga/ingest.py      # → output/nga.duckdb   (nga_objects)
    getty/ingest.py     # → output/getty.duckdb (getty_objects, getty_activity, getty_object_index)
    getty/linked_art.py # Getty JSON-LD → flat GettyObject converter
    rijks/ingest.py     # → output/rijks.duckdb (rijks_objects, rijks_sets, etc.)
```

Each museum has its own DuckDB file with a bespoke schema. Common columns across museums: `title`, `object_type`, `artist_name`, `date_display`, `date_start`, `date_end`, `medium`, `classification`, `image_url`, `source_url`, plus a JSON `extra` column for everything else.
