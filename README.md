# artdig

A DuckDB catalogue of ~629,000 public domain artworks from two major museums:

- **Metropolitan Museum of Art** — ~485k objects
- **National Gallery of Art** — ~144k objects

The data pipeline normalizes both sources into a single `artworks` table, making it easy to search across collections by artist, culture, period, medium, classification, and more.

Includes a **visionOS app** for browsing art guides and viewing high-resolution artwork images.

## Setup

Requires Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone --filter=tree:0 https://github.com/hayeah/artdig.git
cd artdig
uv sync
```

### Build the database

The source data is pulled from git submodules (Met open access CSV + NGA data export):

```sh
uv run pymake ingest
```

This creates `output/artdig.duckdb` with the unified `artworks` table.

To verify:

```sh
uv run pymake stats
```

## Querying

### DuckDB CLI

```sh
duckdb output/artdig.duckdb "SELECT count(*) FROM artworks"
```

### Python

```python
import duckdb
con = duckdb.connect("output/artdig.duckdb", read_only=True)
con.execute("SELECT title, artist_name FROM artworks LIMIT 5").fetchall()
```

## Schema

Single table `artworks` with composite primary key `(source, source_id)`:

| Column | Type | Notes |
|---|---|---|
| source | VARCHAR | `'met'` or `'nga'` |
| source_id | VARCHAR | Object ID from source museum |
| title | VARCHAR | |
| artist_name | VARCHAR | Multiple artists separated by `\|` |
| artist_nationality | VARCHAR | |
| artist_birth_year | INTEGER | |
| artist_death_year | INTEGER | |
| date_display | VARCHAR | Human-readable (e.g. "c. 1660") |
| date_start | INTEGER | Earliest year — use for range filtering |
| date_end | INTEGER | Latest year |
| medium | VARCHAR | |
| dimensions | VARCHAR | |
| classification | VARCHAR | e.g. "Painting", "Prints", "Photograph" |
| culture | VARCHAR | e.g. "French", "Japanese", "Greek, Attic" |
| period | VARCHAR | e.g. "Edo period (1615–1868)" |
| department | VARCHAR | |
| country | VARCHAR | Met only |
| city | VARCHAR | Met only |
| region | VARCHAR | Met only |
| is_public_domain | BOOLEAN | |
| credit_line | VARCHAR | |
| image_url | VARCHAR | NGA: direct IIIF URL; Met: API object URL |
| thumbnail_url | VARCHAR | NGA only |
| source_url | VARCHAR | Link to museum website |
| wikidata_id | VARCHAR | |
| extras | JSON | Source-specific overflow fields |

## Example queries

```sql
-- Dutch Golden Age painters
SELECT artist_name, count(*) AS works
FROM artworks
WHERE artist_nationality ILIKE '%dutch%'
  AND classification ILIKE '%painting%'
  AND date_start BETWEEN 1580 AND 1700
GROUP BY artist_name
ORDER BY works DESC
LIMIT 10;

-- Japanese woodblock prints
SELECT title, artist_name, date_display, source_url
FROM artworks
WHERE (culture ILIKE '%japan%' OR artist_nationality ILIKE '%japanese%')
  AND classification ILIKE '%print%'
ORDER BY date_start
LIMIT 20;

-- NGA paintings with direct high-res images
SELECT title, artist_name, image_url
FROM artworks
WHERE source = 'nga'
  AND image_url IS NOT NULL
  AND classification ILIKE '%painting%'
LIMIT 5;
```

More examples in [EXAMPLE.md](EXAMPLE.md).

## Pipeline tasks

```sh
uv run pymake list         # show available tasks
uv run pymake ingest       # ingest both sources (default)
uv run pymake ingest_met   # Met only
uv run pymake ingest_nga   # NGA only
uv run pymake stats        # print summary statistics
```

## Project structure

```
src/artdig/
  schema.py       — DDL for the artworks table
  db.py           — database connection helper
  stats.py        — catalogue statistics
  ingest/
    met.py        — Met CSV ingester
    nga.py        — NGA CSV ingester
data/
  met/            — Met open access dataset (submodule)
  nga/            — NGA open data export (submodule)
app/
  ArtDig/         — visionOS app (Swift, XcodeGen)
Makefile.py       — pymake task definitions
SKILL.md          — Claude Code agent skill guide
```

## visionOS app

The `app/` directory contains a visionOS app for browsing markdown art guides and viewing artwork images. Built with SwiftUI, it supports:

- Markdown guide rendering
- Progressive image loading with caching
- NGA IIIF and Met API image sources
- Favorites

Build with Xcode (requires visionOS SDK).

## License

The source code is MIT licensed. The artwork data comes from each museum's open access program — see their respective licenses for usage terms.
