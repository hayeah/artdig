# artdig — Example Queries

All queries run against `output/artdig.duckdb`. You can use the `duckdb` CLI directly:

```sh
duckdb output/artdig.duckdb
```

Or from Python:

```python
import duckdb
con = duckdb.connect("output/artdig.duckdb", read_only=True)
con.execute("SELECT ...").fetchall()
```

---

## Catalogue Overview

```sql
-- Record counts by source
SELECT source, count(*) AS cnt
FROM artworks
GROUP BY source
ORDER BY source;
```

```
┌────────┬────────┐
│ source │  cnt   │
├────────┼────────┤
│ met    │ 484956 │
│ nga    │ 144040 │
└────────┴────────┘
```

```sql
-- Top classifications across both museums
SELECT classification, count(*) AS cnt
FROM artworks
WHERE classification IS NOT NULL
GROUP BY classification
ORDER BY cnt DESC
LIMIT 15;
```

```sql
-- Date range and average
SELECT
    min(date_start) AS earliest,
    max(date_end)   AS latest,
    round(avg(date_start), 0) AS avg_start_year
FROM artworks
WHERE date_start IS NOT NULL;
```

---

## Browse by Culture and Period

```sql
-- Top cultures in the catalogue
SELECT culture, count(*) AS cnt
FROM artworks
WHERE culture IS NOT NULL
GROUP BY culture
ORDER BY cnt DESC
LIMIT 15;
```

```sql
-- Japanese art by period
SELECT period, count(*) AS cnt
FROM artworks
WHERE culture ILIKE '%japan%'
  AND period IS NOT NULL
GROUP BY period
ORDER BY cnt DESC
LIMIT 10;
```

```sql
-- Chinese art by dynasty
SELECT period, count(*) AS cnt
FROM artworks
WHERE culture ILIKE '%china%' OR culture ILIKE '%chinese%'
GROUP BY period
ORDER BY cnt DESC
LIMIT 10;
```

```sql
-- Egyptian art by period
SELECT period, count(*) AS cnt
FROM artworks
WHERE culture ILIKE '%egypt%'
  AND period IS NOT NULL
GROUP BY period
ORDER BY cnt DESC
LIMIT 10;
```

---

## Find Artists by Nationality and Era

```sql
-- Top Dutch Golden Age artists (1580–1700)
SELECT
    artist_name,
    count(*) AS works,
    min(date_start) AS earliest,
    max(date_end) AS latest
FROM artworks
WHERE (artist_nationality ILIKE '%dutch%' OR culture ILIKE '%dutch%')
  AND date_start BETWEEN 1580 AND 1700
  AND artist_name IS NOT NULL
GROUP BY artist_name
ORDER BY works DESC
LIMIT 20;
```

```sql
-- French Impressionist and Post-Impressionist artists
SELECT artist_name, count(*) AS cnt
FROM artworks
WHERE period ILIKE '%impressionist%'
  AND artist_name IS NOT NULL
GROUP BY artist_name
ORDER BY cnt DESC
LIMIT 15;
```

```sql
-- 19th-century American painters
SELECT artist_name, count(*) AS cnt
FROM artworks
WHERE artist_nationality ILIKE '%american%'
  AND classification ILIKE '%painting%'
  AND date_start BETWEEN 1750 AND 1900
  AND artist_name IS NOT NULL
GROUP BY artist_name
ORDER BY cnt DESC
LIMIT 15;
```

```sql
-- Top artist nationalities overall
SELECT artist_nationality, count(*) AS cnt
FROM artworks
WHERE artist_nationality IS NOT NULL
  AND TRIM(artist_nationality) != ''
GROUP BY artist_nationality
ORDER BY cnt DESC
LIMIT 15;
```

---

## Explore Specific Artists

```sql
-- Vermeer's paintings across both museums
SELECT title, date_display, source, source_url, image_url
FROM artworks
WHERE artist_name ILIKE '%vermeer%'
  AND classification ILIKE '%painting%'
ORDER BY date_start;
```

```sql
-- Rembrandt's public domain works with images (NGA has direct IIIF links)
SELECT title, date_display, source, source_url, image_url
FROM artworks
WHERE artist_name ILIKE '%rembrandt%'
  AND is_public_domain = true
  AND classification ILIKE '%painting%'
ORDER BY date_start
LIMIT 10;
```

---

## Genre Deep Dives

```sql
-- Greek vases by regional origin
SELECT culture, count(*) AS cnt
FROM artworks
WHERE classification ILIKE '%vase%'
  AND culture ILIKE '%greek%'
GROUP BY culture
ORDER BY cnt DESC
LIMIT 10;
```

```sql
-- Early photography pioneers (1840–1900)
SELECT artist_name, count(*) AS cnt
FROM artworks
WHERE classification ILIKE '%photograph%'
  AND date_start BETWEEN 1840 AND 1900
  AND artist_name IS NOT NULL
GROUP BY artist_name
ORDER BY cnt DESC
LIMIT 15;
```

```sql
-- Textiles by culture of origin
SELECT culture, count(*) AS cnt
FROM artworks
WHERE classification ILIKE '%textile%'
  AND culture IS NOT NULL
GROUP BY culture
ORDER BY cnt DESC
LIMIT 10;
```

```sql
-- Flemish Baroque artists
SELECT artist_name, count(*) AS cnt
FROM artworks
WHERE (artist_nationality ILIKE '%flemish%' OR culture ILIKE '%flemish%')
  AND date_start BETWEEN 1580 AND 1700
  AND artist_name IS NOT NULL
GROUP BY artist_name
ORDER BY cnt DESC
LIMIT 15;
```

---

## Search by Keywords

```sql
-- Find works with "sunflower" in the title
SELECT title, artist_name, date_display, source, source_url
FROM artworks
WHERE title ILIKE '%sunflower%'
ORDER BY date_start;
```

```sql
-- Find self-portraits
SELECT title, artist_name, date_display, classification, source_url
FROM artworks
WHERE title ILIKE '%self-portrait%'
  AND classification ILIKE '%painting%'
ORDER BY date_start
LIMIT 20;
```

```sql
-- Works mentioning a specific medium
SELECT title, artist_name, date_display, medium
FROM artworks
WHERE medium ILIKE '%gold%'
  AND classification ILIKE '%painting%'
LIMIT 10;
```

---

## Working with the Extras JSON

Source-specific fields that don't fit the common schema are stored in the `extras` JSON column.

```sql
-- Met: find highlighted works
SELECT title, artist_name, date_display, source_url
FROM artworks
WHERE source = 'met'
  AND json_extract(extras, '$.is_highlight') = true
LIMIT 10;
```

```sql
-- Met: search by tags
SELECT title, artist_name, classification
FROM artworks
WHERE source = 'met'
  AND json_extract_string(extras, '$.tags') ILIKE '%landscape%'
LIMIT 10;
```

```sql
-- NGA: virtual objects vs physical
SELECT
    json_extract(extras, '$.is_virtual') AS is_virtual,
    count(*) AS cnt
FROM artworks
WHERE source = 'nga'
GROUP BY is_virtual;
```

---

## Image URLs

NGA works have direct IIIF image links. Met works store the API object URL (actual image requires per-object API call).

```sql
-- NGA paintings with direct high-res images
SELECT title, artist_name, image_url, thumbnail_url
FROM artworks
WHERE source = 'nga'
  AND image_url IS NOT NULL
  AND classification ILIKE '%painting%'
LIMIT 5;
```

```sql
-- Count works with images by source
SELECT source, count(*) AS with_image
FROM artworks
WHERE image_url IS NOT NULL
GROUP BY source;
```
