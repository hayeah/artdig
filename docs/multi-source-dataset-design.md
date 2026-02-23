# Multi-Source Dataset Design for Bespoke Museum Data APIs

Date: 2026-02-23  
Project: `artdig`

## 1) Problem Statement

`artdig` currently ingests two CSV-first sources (Met, NGA) into a single `artworks` table.  
Next targets (Rijksmuseum, Getty, Paris Musees) use different protocols and data models.

The key challenge is not just field mapping. It is building a durable ingestion system that:

- supports mixed source types (bulk dumps, REST, GraphQL, Linked Data, IIIF),
- supports resumable incremental updates,
- preserves full raw source records for reprocessing,
- keeps query storage small and fast for app/search use cases.

## 2) Are these APIs standardized or bespoke?

Short answer: both.

- Standards used across sources:
  - IIIF (image/manifest delivery)
  - Linked Data serializations (JSON-LD/RDF)
  - Linked Art / CIDOC-CRM modeling (strongly in Getty, present in Rijksmuseum services)
  - ActivityStreams / IIIF Change Discovery style feeds for change events
  - SPARQL (Getty)
  - OAI-PMH (Rijksmuseum)
- Bespoke differences remain substantial:
  - auth models (public vs token)
  - endpoint structure and pagination
  - field naming and nesting
  - rights/licensing field locations
  - update-discovery mechanics

Conclusion: build a standard-aware core, but always implement source adapters.

## 3) What We Know About Each Source (as of 2026-02-23)

### 3.1 Metropolitan Museum of Art (existing in `artdig`)

- Primary dataset mode: bulk CSV (`MetObjects.csv` from Met Open Access repo).
- CSV includes `Metadata Date` (row-level metadata recency hint) and stable `Object ID`.
- Images are not included in CSV; links are provided via object/page metadata.
- Update mechanism published by source: periodic full dataset refresh.

Implication for ingest:

- Bootstrap: full CSV load.
- Incremental: snapshot diff keyed by `Object ID`, plus optional use of `Metadata Date` where populated.
- Canonical source key: `met:<Object ID>`.

### 3.2 National Gallery of Art (existing in `artdig`)

- Primary dataset mode: multi-table CSV extract (objects, constituents, terms, images, etc).
- NGA states updates are frequent (usually daily) at repo level.
- `objects.csv` includes `lastdetectedmodification` (strong row-level incremental signal).
- Related tables include modification/release timestamps for media rows.

Implication for ingest:

- Bootstrap: full table load with relational joins.
- Incremental: if files are fully refreshed, use row hash or timestamp-based upsert by primary keys (`objectid`, etc).
- Canonical source key: `nga:<objectid>`.

### 3.3 Getty Museum Collection API

- API style: Linked.Art model over JSON-LD with REST-by-ID endpoints.
- Entity types include `object`, `place`, `document`, `group`, `person`, `exhibition`, `activity`.
- Change tracking: ActivityStream endpoint with paginated change events.
- Query interface: SPARQL endpoint available.
- Important limitation documented by Getty docs: no official list-all endpoint and no single full-download endpoint (roadmap item).

Live verified behavior (2026-02-23):

- ActivityStream root exists and exposes first/last pages.
- Last page currently around ~42k pages (value changes over time).
- Records can be fetched directly by entity UUID.

Implication for ingest:

- Bootstrap:
  - crawl ActivityStream from page `1` forward,
  - collect create/update/delete events,
  - materialize current state by replay.
- Incremental:
  - poll from `last` page backwards until checkpoint reached, or continue forward from last seen page.
- Canonical source key:
  - `getty:<entity_type>:<uuid>` (for non-object entities),
  - `getty:object:<uuid>` for object records in core catalog.

### 3.4 Rijksmuseum Data Services

- API landscape includes:
  - Data Dumps (bulk download; complete collection metadata available),
  - Search API (Linked Art Search response format),
  - Linked Data resolver endpoints,
  - OAI-PMH,
  - LDES,
  - IIIF services including Change Discovery.
- IIIF Change Discovery feed is live at `/cd/collection.json` and points to paged updates.

Live verified behavior (2026-02-23):

- CD root and `pages/last.json` are available and return update events.
- Search endpoint returns `OrderedCollectionPage` with 100-item pagination and `pageToken`.

Implication for ingest:

- Bootstrap preference: official data dumps (fastest/most complete).
- Incremental preference: IIIF Change Discovery (and/or LDES if better fit for infra).
- Canonical source key: normalize resolver/object identifiers, e.g. `rijks:<numeric_or_id>`.

### 3.5 Paris Musees Collections API

- API style: GraphQL endpoint.
- Access model: account creation + auth token required for full API usage (documented on API site).
- Unauthenticated GraphQL access may return access denied (`403`) depending on request shape.
- Public docs do not currently expose a clear anonymous bulk dump path.

Implication for ingest:

- Bootstrap likely requires authenticated paginated GraphQL extraction.
- Incremental strategy depends on available fields:
  - best case: updated timestamp / revision token query,
  - fallback: periodic full-id scan + hash diff.
- Canonical source key: `parismusees:<id>`.

## 4) Proposed Architecture

Use a 3-layer design:

1. Raw layer (append-only, large)
2. Canonical layer (normalized relational, query-friendly)
3. Serving/analytics layer (DuckDB/SQLite views/materializations)

### 4.1 Raw Layer

Store each fetched source record exactly as received:

- `raw/{source}/{entity_type}/{source_id}/{fetched_at}_{sha256}.json`
- metadata ledger table `raw_objects`:
  - `source`
  - `entity_type`
  - `source_id`
  - `version_hash`
  - `fetched_at`
  - `event_time` (if known)
  - `payload_path`
  - `is_deleted`

Why:

- reproducibility,
- re-map without re-fetch,
- auditability of source changes.

### 4.2 Canonical Layer

Keep this compact and source-agnostic:

- `records` (core object row)
- `record_agents`
- `record_images`
- `record_terms`
- `record_measurements`
- `record_external_ids`
- `source_checkpoints`

Guideline:

- only keep fields in canonical tables if they are common and frequently queried,
- keep everything else in raw payloads and derive via views as needed.

### 4.3 Serving/Analytics Layer

- DuckDB file for heavy local analytical queries.
- Optional SQLite subset for app runtime needs.
- Build views for common app/search queries (artist/date/medium/public-domain/image-ready).

## 5) Incremental Update Design

Each source gets its own checkpoint and updater logic under a common interface.

## 5.1 Common Checkpoint Model

`source_checkpoints`:

- `source` (PK)
- `checkpoint_type` (`page`, `token`, `timestamp`, `commit`)
- `checkpoint_value` (TEXT)
- `last_success_at` (TIMESTAMP)
- `metadata_json` (JSON)

## 5.2 Source-Specific Incremental Strategies

### Met

- Preferred approach:
  - fetch latest CSV snapshot,
  - compare against prior snapshot by `Object ID` + row hash,
  - upsert changed rows and mark missing rows as tombstoned if needed.
- Optional optimization:
  - use `Metadata Date` when present to shortcut unchanged rows.

### NGA

- Preferred approach:
  - fetch latest CSV tables,
  - use table PK + `lastdetectedmodification` (where available),
  - recompute row hash for tables lacking reliable mod timestamps.
- Rebuild derived object joins incrementally from changed PK sets.

### Getty

- Preferred approach:
  - poll ActivityStream,
  - process events since last event/page checkpoint,
  - fetch changed/deleted entities by referenced IDs.
- Handle event types:
  - create/update -> fetch + upsert
  - delete -> tombstone in canonical tables

### Rijksmuseum

- Preferred approach:
  - consume IIIF Change Discovery page events (or LDES if chosen),
  - fetch referenced object identifiers from event payload,
  - upsert/tombstone accordingly.
- Bootstrap remains dump-based; CD/LDES for ongoing sync.

### Paris Musees

- Preferred approach (if supported by schema):
  - query GraphQL with `updated_at > checkpoint` + pagination.
- Fallback:
  - paginated full object-id scan + payload hash diff.
- Must include token refresh and auth failure handling.

## 6) Canonical ID and Identity Rules

- Canonical PK should be deterministic and source namespaced:
  - `record_id = "{source}:{source_id}"`
- Keep source-native IDs intact for traceability.
- Keep external IDs separately (`wikidata`, `ulan`, `aat`, etc.) in `record_external_ids`.
- Never rely on title/name for identity.

## 7) Deletions and Tombstones

Do not hard-delete by default.

- `records.is_deleted` boolean
- `records.deleted_at` timestamp

Delete signals:

- explicit delete event (Getty/Change feeds),
- missing in snapshot over configurable grace period (CSV-only sources).

## 8) Rights and License Normalization

Because rights fields differ by source, normalize to a minimal policy surface:

- `is_public_domain` (boolean)
- `license` (short text or URL)
- `rights_statement` (optional text)
- `license_source_path` (JSON path for provenance/debug)

Treat image rights independently from metadata rights.

## 9) Data Quality and Validation

Add ingestion assertions and metrics:

- object count by source and by day
- changed/new/deleted row counts per run
- null-rate on critical fields (`title`, `source_url`, `primary_image_url`)
- duplicate key detection
- license classification coverage

Persist run logs:

- `ingest_runs(run_id, source, started_at, ended_at, status, stats_json, error_text)`

## 10) Operational Plan

Cadence proposal:

- Met: daily snapshot poll
- NGA: daily snapshot poll
- Getty: hourly or daily ActivityStream poll
- Rijksmuseum: daily CD/LDES poll (or higher frequency if needed)
- Paris Musees: daily tokened incremental query (or nightly full diff fallback)

Failure policy:

- source adapter failures should not block other sources,
- checkpoint advances only after successful commit of run transaction.

## 11) Implementation Plan for `artdig`

Phase 1: Storage and schema foundation

- Add `raw_objects`, `source_checkpoints`, `ingest_runs`.
- Add normalized canonical tables (`records`, `record_agents`, `record_images`, etc.).

Phase 2: Existing source migration

- Re-implement Met/NGA ingesters to write both raw + canonical layers.
- Validate parity with current `artworks`-based queries.

Phase 3: New sources

- Implement `getty` adapter with ActivityStream checkpointing.
- Implement `rijks` adapter with dump bootstrap + CD incremental.
- Implement `parismusees` adapter with tokened GraphQL and checkpoint strategy.

Phase 4: Serving views and app integration

- Build compatibility view (`artworks_v`) to ease transition from current table.
- Update app/backend queries to use canonical tables/views.

## 12) Open Questions

- Paris Musees schema details after authentication:
  - exact pagination shape,
  - presence/absence of reliable `updated_at` fields,
  - delete visibility.
- Rijksmuseum dump lifecycle:
  - stable URL strategy vs dated archive links,
  - whether historical snapshots should be mirrored locally.
- Getty coverage choice:
  - only `object` entities in core catalog,
  - or include `person/place/exhibition` as first-class canonical entities.

## 13) References

- Met Open Access repo: https://github.com/metmuseum/openaccess
- NGA Open Data repo: https://github.com/NationalGalleryOfArt/opendata
- Getty project page: https://www.getty.edu/projects/open-data-apis/
- Getty Museum Collection docs: https://data.getty.edu/museum/collection/docs/
- Getty ActivityStream: https://data.getty.edu/museum/collection/activity-stream
- Getty SPARQL: https://data.getty.edu/museum/collection/sparql
- Rijksmuseum docs hub: https://data.rijksmuseum.nl/docs/
- Rijksmuseum data dumps docs: https://data.rijksmuseum.nl/docs/data-dumps/
- Rijksmuseum Search docs: https://data.rijksmuseum.nl/docs/search
- Rijksmuseum IIIF Change Discovery docs: https://data.rijksmuseum.nl/docs/iiif/cd
- Rijksmuseum CD root: https://data.rijksmuseum.nl/cd/collection.json
- Paris Musees API portal: https://apicollections.parismusees.paris.fr/
