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
    artic/ingest.py     # → output/artic.duckdb (artic_objects)
```

Each museum has its own DuckDB file with a bespoke schema. Common columns across museums: `title`, `object_type`, `artist_name`, `date_display`, `date_start`, `date_end`, `medium`, `classification`, `image_url`, `source_url`, plus a JSON `extra` column for everything else.

## Art Institute of Chicago (ARTIC)

Data comes from the official ARTIC API data dump (~115 MB compressed, ~2.5 GB extracted):
- Download: `https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2`
- Format: Individual JSON files at `data/artic/artic-api-data/json/artworks/{id}.json`
- IIIF images: `https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg`
- Source URLs: `https://www.artic.edu/artworks/{id}`

```bash
uv run pymake download_artic   # download & extract data dump
uv run pymake ingest_artic     # ingest into output/artic.duckdb (artic_objects)
uv run pymake stats_artic      # print dataset summary
```

## Rijksmuseum Harvesting

Rijks uses OAI-PMH with curated "sets". Before harvesting, run `ingest_rijks` once (with a low `max_pages`) to sync the set list, then query the DB to see what's available:

```sql
-- in output/rijks.duckdb
SELECT set_spec, set_name FROM rijks_sets ORDER BY set_spec;
```

Notable sets:
- `260213` — Top 100
- `260214` — Top 1000
- `260239` — Entire Public Domain Set

Then harvest a specific set:

```bash
uv run pymake ingest_rijks --vars ingest_rijks.set=260214
```

When the user asks to harvest Rijks objects, always ask which set they want. Show them the query above so they can pick.
