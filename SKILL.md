# artdig — Museum Art Collection Databases

Query art collection databases from major museums using DuckDB. All databases are read-only analytical stores in `output/`.

Total: ~2.0M unique objects across 10 databases.

## How to Query

```sh
cd ~/github.com/hayeah/artdig
uv run python << 'PYEOF'
import duckdb
con = duckdb.connect('output/<db_file>', read_only=True)
for row in con.execute("SELECT ...").fetchall():
    print(row)
con.close()
PYEOF
```

Or use the `duckdb` CLI directly:

```sh
duckdb output/artdig.duckdb "SELECT ... FROM artworks ..."
```

Always open connections with `read_only=True`.

## Databases Overview

| Database | File | Table | Rows | Primary Key |
|---|---|---|---|---|
| Unified (Met+NGA) | `artdig.duckdb` | `artworks` | 628,996 | `source` + `source_id` |
| Met Museum | `met.duckdb` | `met_objects` | 484,956 | `object_id` (INTEGER) |
| National Gallery of Art | `nga.duckdb` | `nga_objects` | 144,040 | `objectid` (VARCHAR) |
| Art Institute of Chicago | `artic.duckdb` | `artic_objects` | 134,078 | `id` (INTEGER) |
| Rijksmuseum | `rijks.duckdb` | `rijks_objects` | 667,894 | `inventory_number` (VARCHAR) |
| Getty Museum | `getty.duckdb` | `getty_objects` | 989 | `object_url` (VARCHAR) |
| NYPL Public Domain | `nypl.duckdb` | `nypl_objects` | 190,494 | `uuid` (VARCHAR) |
| MoMA | `moma.duckdb` | `moma_objects` | 160,214 | `object_id` (INTEGER) |
| Tate | `tate.duckdb` | `tate_objects` | 69,201 | `id` (INTEGER) |
| Cooper Hewitt | `cooperhewitt.duckdb` | `cooperhewitt_objects` | 194,316 | `id` (INTEGER) |

## Column Name Mapping

Column names vary across databases. Use this reference:

| Concept | Unified | Met | NGA | ARTIC | Rijks | Getty | NYPL | MoMA | Tate | Cooper Hewitt |
|---|---|---|---|---|---|---|---|---|---|---|
| Title | `title` | `title` | `title` | `title` | `title_en` / `title_nl` | `title` | `title` | `title` | `title` | `title` |
| Artist | `artist_name` | `artist_name` | `artist_name` | `artist_name` | `creator_name` | `makers` | `artist_name` | `artist_name` | `artist_name` | `artist_name` |
| Type | `classification` | `classification` | `classification` | `classification` | `object_type_en` | `classification` | `object_type` | `classification` | — | `object_type` |
| Year start | `date_start` | `date_start` | `date_start` | `date_start` | `earliest_year` | `date_begin` | `date_start` | — | `date_start` | `date_start` (sparse) |
| Year end | `date_end` | `date_end` | `date_end` | `date_end` | `latest_year` | `date_end` | `date_end` | — | — | `date_end` (sparse) |
| Display date | `date_display` | `date_display` | `date_display` | `date_display` | — | `date_display` | `date_display` | `date_display` | `date_display` | `date_display` |
| Public domain | `is_public_domain` | `is_public_domain` | `is_public_domain` | `is_public_domain` | — | `is_metadata_cc0` | `is_public_domain` | `is_public_domain` | `is_public_domain` | `is_public_domain` |
| Source link | `source_url` | `source_url` | `source_url` | `source_url` | `source_url` | `source_url` | `source_url` | `source_url` | `source_url` | `source_url` |
| Image | `image_url` | `image_url` | `image_url` | `image_url` | `image_url` | `image_url` | `image_url` | `image_url` | `image_url` | `image_url` |

## Schemas

### Unified Catalog — `artdig.duckdb` → `artworks`

Cross-museum search across Met + NGA. Composite PK: `(source, source_id)`.

```
source, source_id, title, artist_name, artist_nationality,
artist_birth_year, artist_death_year, date_display, date_start, date_end,
medium, dimensions, classification, culture, period, department,
country, city, region,  -- Met only
is_public_domain, credit_line, image_url, thumbnail_url, source_url,
wikidata_id, extras (JSON)
```

### Met — `met.duckdb` → `met_objects`

```
object_id, title, object_type, artist_name, date_display, date_start, date_end,
medium, dimensions, classification, image_url, source_url, is_public_domain,
department, culture, period, country, city,
artist_nationality, artist_begin_date (VARCHAR), artist_end_date (VARCHAR),
wikidata_id, extra (JSON)
```

### NGA — `nga.duckdb` → `nga_objects`

```
objectid, title, object_type, artist_name, date_display, date_start, date_end,
medium, dimensions, classification, image_url (IIIF), source_url, is_public_domain,
department, culture, period, artist_nationality,
artist_birth_year, artist_death_year, thumbnail_url, credit_line,
wikidata_id, extra (JSON)
```

### ARTIC — `artic.duckdb` → `artic_objects`

`artist_name` includes biography (e.g. "Monet (French, 1840–1926)"). Use `json_extract_string(extra, '$.artist_title')` for the clean name.

```
id, title, object_type, artist_name, date_display, date_start, date_end,
medium, dimensions, classification, image_url (IIIF), source_url, is_public_domain,
department, place_of_origin, credit_line, accession_number,
extra (JSON) — has artist_title, style_titles, subject_titles, term_titles, etc.
```

### Rijksmuseum — `rijks.duckdb` → `rijks_objects`

Bilingual (English/Dutch). Physical dimensions in cm.

```
inventory_number, lido_rec_id, oai_identifier,
title_en, title_nl, description_en, description_nl,
object_type_en, object_type_nl, object_type_aat_uri,
creator_name, creator_role, creator_nationality, creator_qualifier,
creator_birth_year, creator_death_year,
earliest_year, latest_year,
height_cm, width_cm, depth_cm,
materials (JSON), techniques (JSON), subjects (JSON),
inscriptions (JSON), all_dimensions (JSON),
image_url, rights_url, credit_line, source_url,
record_metadata_date, ingested_at
```

Additional tables:
- `rijks_sets` (192 rows): `set_spec`, `set_name`, `record_count`
- `rijks_object_sets` (12,459 rows): `identifier`, `set_spec` — junction table linking objects to sets via `oai_identifier`

### Getty — `getty.duckdb` → `getty_objects`

Partial ingest (989 objects). Raw Linked Art JSON in `raw` column.

```
object_url, object_uuid, object_type, label, title,
accession_number, classification, makers, date_display,
date_begin, date_end, materials, source_url,
iiif_manifest_url, image_url, is_metadata_cc0, fetched_at, raw (JSON)
```

Additional tables:
- `getty_activity` (18,292 rows): ActivityStream update log
- `getty_object_index` (168,392 rows): full object URL index with fetch status

### NYPL — `nypl.duckdb` → `nypl_objects`

All public domain. Hierarchical collection structure.

```
uuid, database_id, title, object_type, artist_name,
date_display, date_start, date_end, medium, dimensions, classification,
image_url, source_url, is_public_domain,
collection_uuid, collection_title,
container_uuid, container_title, parent_hierarchy,
num_captures, accession_number, call_number, bnumber,
extra (JSON)
```

Additional table:
- `nypl_collections` (932 rows): `uuid`, `database_id`, `title`, `num_items`, `source_url`, `extra`

### MoMA — `moma.duckdb` → `moma_objects`

Modern and contemporary art. All CC0 metadata. `artist_bio` has formatted bio (e.g. "(American, 1930–1992)").

```
object_id, title, artist_name, artist_bio, artist_nationality,
artist_birth_year, artist_death_year, artist_gender,
date_display, date_acquired, medium, dimensions, classification,
department, credit_line, accession_number,
image_url, source_url, is_public_domain,
extra (JSON) — has constituent_id, height_cm, width_cm, depth_cm, duration_sec, etc.
```

### Tate — `tate.duckdb` → `tate_objects`

British art from 1500s to present + international modern/contemporary. `is_public_domain` is true when no thumbnail copyright is set. Dimensions in mm.

```
id, accession_number, title, artist_name, artist_role, artist_id,
date_display, date_start, medium, dimensions,
width_mm, height_mm, depth_mm,
credit_line, year_acquired,
image_url, source_url, is_public_domain,
extra (JSON) — has thumbnail_copyright, inscription, units
```

Additional table:
- `tate_artists` (3,532 rows): `id`, `name`, `gender`, `dates`, `birth_year`, `death_year`, `place_of_birth`, `place_of_death`, `source_url`

Join: `tate_objects.artist_id = tate_artists.id`

### Cooper Hewitt — `cooperhewitt.duckdb` → `cooperhewitt_objects`

Design-focused (textiles, furniture, posters, wallpaper, jewelry). `date_start`/`date_end` are sparse — use `date_display` or `decade` instead. Artist derived from participants CSV (prioritizes Artist > Designer > Creator roles).

```
id, title, artist_name, artist_role, object_type,
date_display, date_start (sparse), date_end (sparse), decade,
medium, dimensions, classification,
department_id, credit_line, accession_number,
image_url, source_url, is_public_domain, country,
extra (JSON) — has description, gallery_text, label_text, inscribed, provenance, period_id, type_id, etc.
```

## Query Patterns

### Start broad, then narrow

```sql
-- Step 1: How much exists?
SELECT count(*) FROM met_objects WHERE artist_name ILIKE '%monet%';

-- Step 2: What types?
SELECT classification, count(*) c FROM met_objects
WHERE artist_name ILIKE '%monet%' GROUP BY classification ORDER BY c DESC;

-- Step 3: Specific works
SELECT title, date_display, source_url, image_url FROM met_objects
WHERE artist_name ILIKE '%monet%' AND classification ILIKE '%painting%'
ORDER BY date_start;
```

### Search by artist across databases

Each DB has different artist column names. Query each separately:

```sql
-- Met / NGA / NYPL
SELECT * FROM met_objects WHERE LOWER(artist_name) LIKE '%monet%';

-- Rijks
SELECT * FROM rijks_objects WHERE LOWER(creator_name) LIKE '%rembrandt%';

-- Getty
SELECT * FROM getty_objects WHERE LOWER(makers) LIKE '%van gogh%';

-- ARTIC (artist_name has bio text; use extra for clean name)
SELECT * FROM artic_objects
WHERE LOWER(json_extract_string(extra, '$.artist_title')) = 'claude monet';

-- MoMA / Tate / Cooper Hewitt
SELECT * FROM moma_objects WHERE artist_name ILIKE '%picasso%';
SELECT * FROM tate_objects WHERE artist_name ILIKE '%hockney%';
SELECT * FROM cooperhewitt_objects WHERE artist_name ILIKE '%eames%';
```

### Use ILIKE for fuzzy matching

Values are inconsistent across sources — always use `ILIKE '%term%'`:

```sql
-- Good: catches "Painting", "Paintings", "painting"
WHERE classification ILIKE '%painting%'

-- Bad: misses variants
WHERE classification = 'Painting'
```

### Filter by date range

```sql
-- Renaissance works (1400-1600)
WHERE date_start >= 1400 AND date_end <= 1600

-- Rijks uses different column names
WHERE earliest_year >= 1400 AND latest_year <= 1600
```

### Public domain images only

```sql
SELECT * FROM met_objects WHERE is_public_domain = true AND image_url IS NOT NULL;
SELECT * FROM nypl_objects WHERE image_url IS NOT NULL;  -- all public domain
```

### Rijks collections by set

```sql
SELECT set_name, record_count FROM rijks_sets ORDER BY record_count DESC;

SELECT o.* FROM rijks_objects o
JOIN rijks_object_sets os ON o.oai_identifier = os.identifier
WHERE os.set_spec = '<set_spec>';
```

### NYPL by collection

```sql
SELECT title, num_items FROM nypl_collections ORDER BY num_items DESC;

SELECT * FROM nypl_objects WHERE collection_title ILIKE '%stereoscopic%';
```

### JSON fields (DuckDB syntax)

```sql
-- Extract string from extra/raw JSON
SELECT json_extract_string(extra, '$.artist_title') FROM artic_objects;

-- Unnest JSON arrays (Rijks subjects, materials)
SELECT inventory_number, unnest(from_json(subjects, '["VARCHAR"]')) AS subject
FROM rijks_objects WHERE subjects IS NOT NULL;

-- Met highlights
SELECT * FROM met_objects
WHERE json_extract(extra, '$.is_highlight') = true;
```

## Linking to Works

When referencing works in output, include title, artist, date, and source_url:

```
- *Young Woman with a Water Pitcher* (c. 1662) — [Met](http://www.metmuseum.org/art/collection/search/437881)
- *Girl with the Red Hat* (c. 1669) — [NGA](https://www.nga.gov/collection/art-object-page.60.html)
```

For NGA, `image_url` is a direct IIIF link. For Met, `source_url` links to the collection page where the image can be viewed.

## Writing Guides

When researching an art topic:

- Query the databases to discover what's available before writing
- Start with aggregate queries (counts, top artists, classifications)
- Fetch 3-5 representative works per section, preferring public domain
- Include `source_url` for every referenced work
- Save guides to Obsidian: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/github.com/hayeah/artdig/`

### Tate by artist with details

```sql
SELECT o.title, o.date_display, a.dates, a.place_of_birth, o.source_url
FROM tate_objects o
JOIN tate_artists a ON o.artist_id = a.id
WHERE a.name ILIKE '%turner%'
ORDER BY o.date_start;
```

### Cooper Hewitt by design type

```sql
SELECT object_type, count(*) c FROM cooperhewitt_objects
GROUP BY object_type ORDER BY c DESC LIMIT 20;

SELECT title, artist_name, date_display, source_url
FROM cooperhewitt_objects WHERE object_type ILIKE '%poster%';
```

### MoMA by department/classification

```sql
SELECT department, count(*) c FROM moma_objects
GROUP BY department ORDER BY c DESC;

SELECT classification, count(*) c FROM moma_objects
GROUP BY classification ORDER BY c DESC;
```

## Pipeline Management

```sh
cd ~/github.com/hayeah/artdig
uv run pymake ingest            # unified (Met + NGA)
uv run pymake ingest_met
uv run pymake ingest_nga
uv run pymake ingest_artic
uv run pymake ingest_rijks
uv run pymake ingest_getty
uv run pymake ingest_nypl
uv run pymake ingest_moma
uv run pymake ingest_tate
uv run pymake ingest_cooperhewitt
uv run pymake stats_moma
uv run pymake stats_tate
uv run pymake stats_cooperhewitt
```
