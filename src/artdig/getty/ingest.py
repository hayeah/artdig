"""Getty Museum Collection ingestion into a dedicated DuckDB database."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import duckdb

from artdig.common import now_utc

ACTIVITY_ROOT = "https://data.getty.edu/museum/collection/activity-stream"
OBJECT_PREFIX = "https://data.getty.edu/museum/collection/object/"
SPARQL_ENDPOINT = "https://data.getty.edu/museum/collection/sparql"


def _fetch_json(url: str, timeout: float = 10.0) -> dict:
    req = Request(
        url,
        headers={
            "Accept": "application/ld+json, application/json",
            "User-Agent": "artdig-getty-ingester/0.1",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return json.loads(data)


def _fetch_sparql_json(query: str, timeout: float = 60.0) -> dict:
    from urllib.parse import urlencode

    params = urlencode({"query": query, "format": "json"})
    url = f"{SPARQL_ENDPOINT}?{params}"
    req = Request(
        url,
        headers={
            "Accept": "application/sparql-results+json, application/json",
            "User-Agent": "artdig-getty-ingester/0.1",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return json.loads(data)


def _parse_page_number(url: str | None) -> int | None:
    if not url:
        return None
    m = re.search(r"/page/(\d+)$", url)
    if not m:
        return None
    return int(m.group(1))


def _parse_year(value: str | None) -> int | None:
    if not value:
        return None
    m = re.match(r"^(\d{4})", value)
    if not m:
        return None
    return int(m.group(1))


def _extract_labels(items: list[dict] | None) -> str | None:
    if not items:
        return None
    labels = [i.get("_label", "").strip() for i in items if i.get("_label")]
    labels = [x for x in labels if x]
    return " | ".join(labels) if labels else None


def _extract_title(identified_by: list[dict] | None, fallback: str | None) -> str | None:
    if not identified_by:
        return fallback

    preferred = None
    first_name = None
    for entry in identified_by:
        if entry.get("type") != "Name":
            continue
        content = (entry.get("content") or "").strip()
        if not content:
            continue
        if first_name is None:
            first_name = content
        for cls in entry.get("classified_as", []):
            label = (cls.get("_label") or "").lower()
            if "preferred term" in label or "primary title" in label:
                preferred = content
                break
        if preferred:
            break

    return preferred or first_name or fallback


def _extract_accession_number(identified_by: list[dict] | None) -> str | None:
    if not identified_by:
        return None
    for entry in identified_by:
        content = (entry.get("content") or "").strip()
        if not content:
            continue
        for cls in entry.get("classified_as", []):
            if (cls.get("_label") or "").lower() == "accession number":
                return content
    return None


def _extract_makers(obj: dict) -> str | None:
    carried = obj.get("produced_by", {}).get("carried_out_by", [])
    return _extract_labels(carried)


def _extract_display_date(obj: dict) -> str | None:
    timespan = obj.get("produced_by", {}).get("timespan", {})
    for ident in timespan.get("identified_by", []):
        content = (ident.get("content") or "").strip()
        if content:
            return content
    return None


def _extract_source_url(obj: dict) -> str | None:
    for item in obj.get("subject_of", []):
        value = item.get("id") if isinstance(item, dict) else None
        if isinstance(value, str) and "getty.edu/art/collection/object/" in value:
            return value
    return None


def _extract_iiif_manifest_url(obj: dict) -> str | None:
    for item in obj.get("subject_of", []):
        value = item.get("id") if isinstance(item, dict) else None
        if isinstance(value, str) and "/iiif/manifest/" in value:
            return value
    return None


def _extract_image_url(obj: dict) -> str | None:
    rep = obj.get("representation") or []
    if not rep:
        return None
    value = rep[0].get("id") if isinstance(rep[0], dict) else None
    return value if isinstance(value, str) else None


def _is_metadata_cc0(obj: dict) -> bool:
    for right in obj.get("subject_to", []):
        for cls in right.get("classified_as", []):
            if cls.get("id") == "http://creativecommons.org/publicdomain/zero/1.0/":
                return True
    return False


def _event_object_url(item: dict) -> str | None:
    obj = item.get("object")
    if isinstance(obj, dict):
        value = obj.get("id")
        return value if isinstance(value, str) else None
    if isinstance(obj, str):
        return obj
    return None


@dataclass(slots=True)
class GettyConfig:
    db_path: Path = Path("output/getty.duckdb")
    from_page: int = 1
    to_page: int | None = None
    max_pages: int | None = None
    max_objects: int | None = None
    sleep_seconds: float = 0.02


class GettyIngester:
    """Builds a Getty-only DuckDB dataset from ActivityStream + object records."""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS getty_activity (
                activity_id          VARCHAR PRIMARY KEY,
                page_number          INTEGER,
                activity_type        VARCHAR,
                event_time           TIMESTAMP,
                object_url           VARCHAR,
                raw                  JSON
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS getty_objects (
                object_url           VARCHAR PRIMARY KEY,
                object_uuid          VARCHAR,
                object_type          VARCHAR,
                label                VARCHAR,
                title                VARCHAR,
                accession_number     VARCHAR,
                classification       VARCHAR,
                makers               VARCHAR,
                date_display         VARCHAR,
                date_begin           INTEGER,
                date_end             INTEGER,
                materials            VARCHAR,
                source_url           VARCHAR,
                iiif_manifest_url    VARCHAR,
                image_url            VARCHAR,
                is_metadata_cc0      BOOLEAN,
                fetched_at           TIMESTAMP,
                raw                  JSON
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS getty_object_index (
                object_url      VARCHAR PRIMARY KEY,
                status          VARCHAR NOT NULL DEFAULT 'pending',
                indexed_at      TIMESTAMP NOT NULL,
                fetched_at      TIMESTAMP,
                error_message   VARCHAR
            )
        """)

    def _upsert_object(self, obj: dict, object_url_hint: str | None = None) -> str:
        object_id = obj.get("id") or object_url_hint
        if not isinstance(object_id, str) or not object_id:
            raise ValueError("Object payload does not include a valid 'id'")

        object_uuid = object_id.rstrip("/").split("/")[-1]
        date_begin = _parse_year(
            obj.get("produced_by", {}).get("timespan", {}).get("begin_of_the_begin")
        )
        date_end = _parse_year(
            obj.get("produced_by", {}).get("timespan", {}).get("end_of_the_end")
        )

        self.conn.execute(
            """
            INSERT OR REPLACE INTO getty_objects (
                object_url,
                object_uuid,
                object_type,
                label,
                title,
                accession_number,
                classification,
                makers,
                date_display,
                date_begin,
                date_end,
                materials,
                source_url,
                iiif_manifest_url,
                image_url,
                is_metadata_cc0,
                fetched_at,
                raw
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::JSON)
            """,
            [
                object_id,
                object_uuid,
                obj.get("type"),
                obj.get("_label"),
                _extract_title(obj.get("identified_by"), obj.get("_label")),
                _extract_accession_number(obj.get("identified_by")),
                _extract_labels(obj.get("classified_as")),
                _extract_makers(obj),
                _extract_display_date(obj),
                date_begin,
                date_end,
                _extract_labels(obj.get("made_of")),
                _extract_source_url(obj),
                _extract_iiif_manifest_url(obj),
                _extract_image_url(obj),
                _is_metadata_cc0(obj),
                now_utc(),
                json.dumps(obj),
            ],
        )
        return object_id

    def _resolve_to_page(self, requested_to_page: int | None) -> int:
        if requested_to_page is not None:
            return requested_to_page
        root = _fetch_json(ACTIVITY_ROOT)
        last_url = root.get("last", {}).get("id")
        last_page = _parse_page_number(last_url)
        if last_page is None:
            raise RuntimeError(f"Unable to determine last ActivityStream page from: {last_url}")
        return last_page

    def ingest_activity_pages(
        self, *, from_page: int, to_page: int, max_pages: int | None, sleep_seconds: float
    ) -> set[str]:
        object_urls: set[str] = set()
        pages_done = 0

        for page in range(from_page, to_page + 1):
            if max_pages is not None and pages_done >= max_pages:
                break

            page_url = f"{ACTIVITY_ROOT}/page/{page}"
            payload = _fetch_json(page_url)
            items = payload.get("orderedItems", [])
            pages_done += 1

            for item in items:
                activity_id = item.get("id")
                if not activity_id:
                    continue
                object_url = _event_object_url(item)
                event_time = item.get("endTime")

                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO getty_activity
                    (activity_id, page_number, activity_type, event_time, object_url, raw)
                    VALUES (?, ?, ?, TRY_CAST(? AS TIMESTAMP), ?, ?::JSON)
                    """,
                    [
                        activity_id,
                        page,
                        item.get("type"),
                        event_time,
                        object_url,
                        json.dumps(item),
                    ],
                )

                if object_url and object_url.startswith(OBJECT_PREFIX):
                    object_urls.add(object_url)

            print(f"Getty: activity page {page} ingested ({len(items)} events)")
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        return object_urls

    def ingest_objects(
        self, object_urls: list[str], *, max_objects: int | None, sleep_seconds: float
    ):
        processed = 0
        for object_url in object_urls:
            if max_objects is not None and processed >= max_objects:
                break

            try:
                obj = _fetch_json(object_url)
            except HTTPError as e:
                print(f"Getty: skipping {object_url} ({e.code})")
                continue
            except URLError as e:
                print(f"Getty: network error for {object_url} ({e})")
                continue

            self._upsert_object(obj, object_url_hint=object_url)

            processed += 1
            if processed % 100 == 0:
                print(f"Getty: fetched {processed:,}/{len(object_urls):,} objects")
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        print(f"Getty: object ingest complete ({processed:,} records fetched)")

    def build_object_index_from_sparql(self) -> int:
        query = """
PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
SELECT DISTINCT ?obj
WHERE {
  ?obj a crm:E22_Human-Made_Object .
  FILTER(STRSTARTS(STR(?obj), "https://data.getty.edu/museum/collection/object/"))
}
ORDER BY ?obj
LIMIT 200000
"""
        payload = _fetch_sparql_json(query)
        urls = [
            b.get("obj", {}).get("value")
            for b in payload.get("results", {}).get("bindings", [])
            if b.get("obj", {}).get("type") == "uri"
        ]
        urls = [u for u in urls if isinstance(u, str)]

        now = now_utc()
        self.conn.execute("SET preserve_insertion_order = false")
        chunk_size = 5000
        for start in range(0, len(urls), chunk_size):
            chunk = urls[start : start + chunk_size]
            self.conn.executemany(
                """
                INSERT OR IGNORE INTO getty_object_index (object_url, status, indexed_at)
                VALUES (?, 'pending', ?)
                """,
                [(u, now) for u in chunk],
            )

        self.conn.execute(
            """
            UPDATE getty_object_index idx
            SET status = 'done',
                fetched_at = COALESCE(idx.fetched_at, obj.fetched_at),
                error_message = NULL
            FROM getty_objects obj
            WHERE idx.object_url = obj.object_url
            """
        )

        total = self.conn.execute("SELECT count(*) FROM getty_object_index").fetchone()[0]
        pending = self.conn.execute(
            "SELECT count(*) FROM getty_object_index WHERE status = 'pending'"
        ).fetchone()[0]
        print(f"Getty: SPARQL index loaded ({total:,} total, {pending:,} pending)")
        return total

    def hydrate_pending_objects(self, *, limit: int, sleep_seconds: float) -> tuple[int, int]:
        rows = self.conn.execute(
            """
            SELECT object_url
            FROM getty_object_index
            WHERE status = 'pending'
            ORDER BY object_url
            LIMIT ?
            """,
            [limit],
        ).fetchall()
        urls = [r[0] for r in rows]

        success = 0
        errors = 0
        for i, object_url in enumerate(urls, start=1):
            try:
                obj = _fetch_json(object_url)
                object_id = self._upsert_object(obj, object_url_hint=object_url)
                self.conn.execute(
                    """
                    UPDATE getty_object_index
                    SET status = 'done', fetched_at = ?, error_message = NULL
                    WHERE object_url = ?
                    """,
                    [now_utc(), object_id],
                )
                success += 1
            except HTTPError as e:
                self.conn.execute(
                    """
                    UPDATE getty_object_index
                    SET status = 'error', error_message = ?
                    WHERE object_url = ?
                    """,
                    [f"HTTP {e.code}", object_url],
                )
                errors += 1
            except URLError as e:
                self.conn.execute(
                    """
                    UPDATE getty_object_index
                    SET status = 'error', error_message = ?
                    WHERE object_url = ?
                    """,
                    [f"URL error: {e}", object_url],
                )
                errors += 1

            if i % 100 == 0:
                print(f"Getty: hydrated {i:,}/{len(urls):,} pending objects")
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        print(f"Getty: hydrate pending complete (success={success:,}, errors={errors:,})")
        return success, errors

    def run(self, cfg: GettyConfig):
        to_page = self._resolve_to_page(cfg.to_page)
        if to_page < cfg.from_page:
            raise ValueError(f"Invalid page range: from_page={cfg.from_page}, to_page={to_page}")

        object_urls = self.ingest_activity_pages(
            from_page=cfg.from_page,
            to_page=to_page,
            max_pages=cfg.max_pages,
            sleep_seconds=cfg.sleep_seconds,
        )
        sorted_urls = sorted(object_urls)
        self.ingest_objects(
            sorted_urls,
            max_objects=cfg.max_objects,
            sleep_seconds=cfg.sleep_seconds,
        )

        activity_count = self.conn.execute(
            "SELECT count(*) FROM getty_activity"
        ).fetchone()[0]
        object_count = self.conn.execute("SELECT count(*) FROM getty_objects").fetchone()[0]
        print(f"Getty: dataset ready in DB (activity={activity_count:,}, objects={object_count:,})")


def config_from_env(db_path: Path | None = None) -> GettyConfig:
    from_page = int(os.getenv("GETTY_FROM_PAGE", "1"))
    to_page_value = os.getenv("GETTY_TO_PAGE", "").strip()
    to_page = int(to_page_value) if to_page_value else None
    max_pages_value = os.getenv("GETTY_MAX_PAGES", "").strip()
    max_pages = int(max_pages_value) if max_pages_value else None
    max_objects_value = os.getenv("GETTY_MAX_OBJECTS", "").strip()
    max_objects = int(max_objects_value) if max_objects_value else None
    sleep_seconds = float(os.getenv("GETTY_SLEEP_SECONDS", "0.02"))
    return GettyConfig(
        db_path=db_path or Path("output/getty.duckdb"),
        from_page=from_page,
        to_page=to_page,
        max_pages=max_pages,
        max_objects=max_objects,
        sleep_seconds=sleep_seconds,
    )


def pending_limit_from_env(default: int = 1000) -> int:
    value = os.getenv("GETTY_PENDING_LIMIT", "").strip()
    return int(value) if value else default
