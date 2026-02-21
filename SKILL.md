# artdig — Agent Skill Guide

You have access to **artdig**, a DuckDB database of ~629,000 public domain artworks from the Metropolitan Museum of Art (~485k) and the National Gallery of Art (~144k). Use it to find representative art for any topic — artists, movements, cultures, time periods, media, or subjects.

## How to Query

Run SQL against the DuckDB file from the project root:

```sh
cd ~/github.com/hayeah/artdig
duckdb output/artdig.duckdb "SELECT ... FROM artworks ..."
```

Or via Python (use `uv run` from the project root):

```sh
cd ~/github.com/hayeah/artdig && uv run python << 'PYEOF'
import duckdb
con = duckdb.connect('output/artdig.duckdb', read_only=True)
for row in con.execute("SELECT ...").fetchall():
    print(row)
PYEOF
```

Always open the database with `read_only=True` for queries.

## Schema

Single table `artworks` with composite PK `(source, source_id)`:

| Column | Type | Notes |
|---|---|---|
| source | VARCHAR | `'met'` or `'nga'` |
| source_id | VARCHAR | Object ID from source |
| title | VARCHAR | |
| artist_name | VARCHAR | |
| artist_nationality | VARCHAR | |
| artist_birth_year | INTEGER | |
| artist_death_year | INTEGER | |
| date_display | VARCHAR | Human-readable date string (e.g. "c. 1660") |
| date_start | INTEGER | Earliest year (use for date range filtering) |
| date_end | INTEGER | Latest year |
| medium | VARCHAR | |
| dimensions | VARCHAR | |
| classification | VARCHAR | e.g. "Painting", "Prints", "Photograph", "Drawing" |
| culture | VARCHAR | e.g. "French", "Japanese", "Greek, Attic" |
| period | VARCHAR | e.g. "Edo period (1615–1868)", "Impressionist" |
| department | VARCHAR | |
| country | VARCHAR | (Met only) |
| city | VARCHAR | (Met only) |
| region | VARCHAR | (Met only) |
| is_public_domain | BOOLEAN | |
| credit_line | VARCHAR | |
| image_url | VARCHAR | NGA: direct IIIF URL; Met: API object URL |
| thumbnail_url | VARCHAR | NGA only |
| source_url | VARCHAR | Link to museum website |
| wikidata_id | VARCHAR | e.g. "Q12418" |
| extras | JSON | Source-specific overflow fields |

## Query Patterns

### Start broad, then narrow

When exploring a topic, start with aggregate queries to understand what data exists, then drill into specific works.

```sql
-- Step 1: How much Dutch art is there?
SELECT count(*) FROM artworks
WHERE artist_nationality ILIKE '%dutch%' OR culture ILIKE '%dutch%';

-- Step 2: What classifications?
SELECT classification, count(*) AS cnt FROM artworks
WHERE artist_nationality ILIKE '%dutch%'
GROUP BY classification ORDER BY cnt DESC LIMIT 10;

-- Step 3: Who are the top artists in paintings?
SELECT artist_name, count(*) AS cnt FROM artworks
WHERE artist_nationality ILIKE '%dutch%'
  AND classification ILIKE '%painting%'
  AND date_start BETWEEN 1580 AND 1700
GROUP BY artist_name ORDER BY cnt DESC LIMIT 15;

-- Step 4: Find specific works
SELECT title, artist_name, date_display, source, source_url, image_url
FROM artworks
WHERE artist_name ILIKE '%Vermeer%'
  AND classification ILIKE '%painting%'
ORDER BY date_start;
```

### Use ILIKE for fuzzy matching

Column values are inconsistent across sources. Always use `ILIKE '%term%'` instead of exact matches:

```sql
-- Good: catches "Painting", "Paintings", "painting"
WHERE classification ILIKE '%painting%'

-- Bad: misses "Paintings" (Met) vs "Painting" (NGA)
WHERE classification = 'Painting'
```

### Filter by date range

Use `date_start` and `date_end` (integer years) for temporal queries:

```sql
-- Renaissance works (1400-1600)
WHERE date_start BETWEEN 1400 AND 1600

-- Works from a specific century
WHERE date_start >= 1800 AND date_start < 1900
```

### Search across multiple fields

Art topics span multiple columns. Combine `culture`, `period`, `artist_nationality`, `classification`, and `title`:

```sql
-- Japanese woodblock prints
WHERE (culture ILIKE '%japan%' OR artist_nationality ILIKE '%japanese%')
  AND classification ILIKE '%print%'

-- Landscape paintings (by title keyword)
WHERE title ILIKE '%landscape%'
  AND classification ILIKE '%painting%'
```

### Get works with images

NGA works have direct IIIF image links. Prefer these when you need viewable images:

```sql
-- NGA works with direct high-res images
SELECT title, artist_name, source_url, image_url
FROM artworks
WHERE source = 'nga'
  AND image_url IS NOT NULL
  AND classification ILIKE '%painting%'
LIMIT 5;
```

For Met works, `image_url` is an API endpoint (e.g. `https://collectionapi.metmuseum.org/public/collection/v1/objects/437878`). The `source_url` links to the collection page where the image can be viewed.

### Access extras JSON

Source-specific fields are in the `extras` column:

```sql
-- Met: find highlighted/notable works
WHERE source = 'met' AND json_extract(extras, '$.is_highlight') = true

-- Met: search by tags
WHERE source = 'met' AND json_extract_string(extras, '$.tags') ILIKE '%landscape%'

-- NGA: accession number
SELECT json_extract_string(extras, '$.accession_num') FROM artworks WHERE source = 'nga'
```

## Key Data Characteristics

- **artist_name**: May contain multiple artists separated by `|` (e.g. "Pieter Soutman|Cornelis Visscher")
- **artist_nationality**: May be duplicated with `|` (e.g. "French|French") or have leading spaces — use ILIKE and TRIM
- **classification**: Met uses plural ("Paintings", "Prints"), NGA uses singular ("Painting", "Print") — use ILIKE with wildcards
- **culture**: Met has more specific values ("Greek, Attic"), NGA derives from term tables ("School" termType)
- **period**: Mix of region-specific periods ("Edo period (1615–1868)"), movements ("Impressionist"), and dynasties ("Qing dynasty (1644–1911)")
- **date_start/date_end**: Can be negative (BCE works); some outliers exist (e.g. -400000 for prehistoric)

## Linking to Works

When referencing works in output (guides, notes, etc.), include:

- **Title** and **artist_name** for identification
- **date_display** for the human-readable date
- **source_url** as a clickable link to the museum page
- **image_url** for NGA works (direct IIIF link to full image)

Format example:

```
- *Young Woman with a Water Pitcher* (c. 1662) — [Met 437881](http://www.metmuseum.org/art/collection/search/437881)
- *Girl with the Red Hat* (c. 1669) — [NGA 60](https://www.nga.gov/collection/art-object-page.60.html) · [image](https://api.nga.gov/iiif/b705a403-3496-42e8-abf5-a37e34c32198/full/max/0/default.jpg)
```

## Writing Guides

When the user asks you to write an art guide or research a topic:

- Query the database to discover what's available before writing
- Start with aggregate queries (counts, top artists, classifications) to map the territory
- Then fetch 3–5 representative works per artist/section, preferring paintings and public domain works
- Include `source_url` for every referenced work and `image_url` where available (NGA)
- Save guides to the Obsidian notes directory: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/github.com/hayeah/artdig/`

## Pipeline Management

If the database doesn't exist or needs rebuilding:

```sh
cd ~/github.com/hayeah/artdig
uv run pymake ingest   # ingest both sources (default task)
uv run pymake stats     # print summary statistics
```

Individual sources can be re-ingested independently:

```sh
uv run pymake ingest_met
uv run pymake ingest_nga
```

## Reference

- Full schema: `src/artdig/schema.py`
- Example queries: `EXAMPLE.md`
- Existing guides: `.obnotes/` (symlink to Obsidian)
