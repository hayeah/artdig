"""Rijksmuseum OAI-PMH ingestion into a dedicated DuckDB database."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.request import Request, urlopen

import duckdb

from artdig.common import now_utc

OAI_ENDPOINT = "https://data.rijksmuseum.nl/oai"

# XML namespaces used in OAI-PMH / EDM responses
NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "edm": "http://www.europeana.eu/schemas/edm/",
    "edmfp": "http://www.europeanafashion.eu/edmfp/",
    "ore": "http://www.openarchives.org/ore/terms/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdaGr2": "http://rdvocab.info/ElementsGr2/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "svcs": "http://rdfs.org/sioc/services#",
    "mrel": "http://id.loc.gov/vocabulary/relators/",
}

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS rijks_objects (
    identifier          VARCHAR PRIMARY KEY,
    object_number       VARCHAR,
    title               VARCHAR,
    description         VARCHAR,
    object_type         VARCHAR,
    creator_name        VARCHAR,
    creator_birth_date  VARCHAR,
    creator_death_date  VARCHAR,
    creator_birthplace  VARCHAR,
    creator_wikidata    VARCHAR,
    date_created        VARCHAR,
    dimensions          VARCHAR,
    medium              VARCHAR,
    techniques          VARCHAR,
    image_url           VARCHAR,
    iiif_service_url    VARCHAR,
    rights_url          VARCHAR,
    source_url          VARCHAR,
    datestamp           TIMESTAMP,
    fetched_at          TIMESTAMP,
    raw_xml             VARCHAR
);
CREATE TABLE IF NOT EXISTS rijks_sets (
    set_spec            VARCHAR PRIMARY KEY,
    set_name            VARCHAR,
    record_count        INTEGER
);
CREATE TABLE IF NOT EXISTS rijks_object_sets (
    identifier          VARCHAR NOT NULL,
    set_spec            VARCHAR NOT NULL,
    PRIMARY KEY (identifier, set_spec)
);
CREATE TABLE IF NOT EXISTS rijks_harvest_state (
    key                 VARCHAR PRIMARY KEY,
    value               VARCHAR
);
"""


def _fetch_xml(url: str, timeout: float = 60.0) -> ET.Element:
    req = Request(
        url,
        headers={
            "Accept": "text/xml, application/xml",
            "User-Agent": "artdig-rijks-ingester/0.1",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return ET.fromstring(data)


def _text(el: ET.Element | None, path: str, lang: str | None = None) -> str | None:
    """Extract text from an element, optionally filtering by xml:lang."""
    if el is None:
        return None
    if lang:
        for child in el.findall(path, NS):
            if child.get("{http://www.w3.org/XML/1998/namespace}lang") == lang:
                return (child.text or "").strip() or None
    child = el.find(path, NS)
    if child is not None:
        return (child.text or "").strip() or None
    return None


def _attr(el: ET.Element | None, path: str, attr: str) -> str | None:
    if el is None:
        return None
    child = el.find(path, NS)
    if child is not None:
        return child.get(attr)
    return None


def _concept_label(rdf: ET.Element, resource_uri: str) -> str | None:
    """Look up a skos:Concept or rdf:Description label by its rdf:about URI."""
    for concept in rdf.findall(".//skos:Concept[@rdf:about]", NS):
        if concept.get(f"{{{NS['rdf']}}}about") == resource_uri:
            label = _text(concept, "skos:prefLabel", lang="en")
            return label or _text(concept, "skos:prefLabel")
    return None


def _collect_concept_labels(rdf: ET.Element, cho: ET.Element, tag: str) -> str | None:
    """Collect labels for all elements of a given tag from the CHO."""
    labels = []
    for el in cho.findall(tag, NS):
        uri = el.get(f"{{{NS['rdf']}}}resource")
        if uri:
            label = _concept_label(rdf, uri)
            if label:
                labels.append(label)
    return " | ".join(labels) if labels else None


def _parse_creator(rdf: ET.Element, creator_uri: str | None) -> dict:
    """Extract creator details from rdf:Description or edm:Agent matching the creator URI."""
    result = {
        "name": None,
        "birth_date": None,
        "death_date": None,
        "birthplace": None,
        "wikidata": None,
    }
    if not creator_uri:
        return result

    # Creator details may be in rdf:Description or edm:Agent elements
    candidates = list(rdf.findall("rdf:Description", NS)) + list(rdf.findall(".//edm:Agent", NS))
    for desc in candidates:
        if desc.get(f"{{{NS['rdf']}}}about") != creator_uri:
            continue
        result["name"] = (
            _text(desc, "skos:prefLabel", lang="en")
            or _text(desc, "skos:prefLabel")
        )
        result["birth_date"] = _text(desc, "rdaGr2:dateOfBirth")
        result["death_date"] = _text(desc, "rdaGr2:dateOfDeath")

        # birthplace
        place_el = desc.find("rdaGr2:placeOfBirth", NS)
        if place_el is not None:
            place_uri = place_el.get(f"{{{NS['rdf']}}}resource")
            if place_uri:
                for place in rdf.findall("edm:Place", NS):
                    if place.get(f"{{{NS['rdf']}}}about") == place_uri:
                        result["birthplace"] = (
                            _text(place, "skos:prefLabel", lang="en")
                            or _text(place, "skos:prefLabel")
                        )
                        break

        # wikidata
        for same_as in desc.findall("owl:sameAs", NS):
            uri = same_as.get(f"{{{NS['rdf']}}}resource", "")
            if "wikidata.org" in uri:
                result["wikidata"] = uri
                break
        break

    return result


def _parse_record_header(record_el: ET.Element) -> tuple[str | None, str | None, list[str]]:
    """Extract identifier, datestamp, and setSpecs from a record header.

    Returns (identifier, datestamp, set_specs). Returns (None, ...) for
    deleted or unparseable records.
    """
    header = record_el.find("oai:header", NS)
    if header is None:
        return None, None, []
    if header.get("status") == "deleted":
        return None, None, []
    identifier = _text(header, "oai:identifier")
    datestamp = _text(header, "oai:datestamp")
    set_specs = [
        el.text.strip()
        for el in header.findall("oai:setSpec", NS)
        if el.text and el.text.strip()
    ]
    return identifier, datestamp, set_specs


def _parse_record_metadata(record_el: ET.Element, identifier: str, datestamp: str | None) -> dict | None:
    """Parse full EDM metadata from a record element."""
    metadata = record_el.find("oai:metadata", NS)
    if metadata is None:
        return None

    rdf = metadata.find("rdf:RDF", NS)
    if rdf is None:
        return None

    agg = rdf.find(".//ore:Aggregation", NS)
    cho = rdf.find(".//edm:ProvidedCHO", NS)
    if cho is None:
        return None

    # Creator
    creator_uri = _attr(cho, "dc:creator", f"{{{NS['rdf']}}}resource")
    creator = _parse_creator(rdf, creator_uri)

    # Image from aggregation — two XML shapes:
    #   <edm:isShownBy rdf:resource="...url..." />
    #   <edm:isShownBy><edm:WebResource rdf:about="...url...">...</edm:WebResource></edm:isShownBy>
    image_url = None
    iiif_service_url = None
    if agg is not None:
        image_url = _attr(agg, "edm:isShownBy", f"{{{NS['rdf']}}}resource")
        if image_url is None:
            shown_by = agg.find("edm:isShownBy", NS)
            if shown_by is not None:
                web_resource = shown_by.find("edm:WebResource", NS)
                if web_resource is not None:
                    image_url = web_resource.get(f"{{{NS['rdf']}}}about")

        # IIIF service URL
        web_resource = rdf.find(".//edm:WebResource", NS)
        if web_resource is not None:
            svc = web_resource.find("svcs:has_service", NS)
            if svc is not None:
                iiif_service_url = svc.get(f"{{{NS['rdf']}}}resource")

    # Rights
    rights_url = _attr(agg, "edm:rights", f"{{{NS['rdf']}}}resource") if agg is not None else None

    raw_xml = ET.tostring(record_el, encoding="unicode")

    return {
        "identifier": identifier,
        "object_number": _text(cho, "dc:identifier"),
        "title": _text(cho, "dc:title", lang="en") or _text(cho, "dc:title"),
        "description": _text(cho, "dc:description", lang="en") or _text(cho, "dc:description"),
        "object_type": _collect_concept_labels(rdf, cho, "dc:type"),
        "creator_name": creator["name"],
        "creator_birth_date": creator["birth_date"],
        "creator_death_date": creator["death_date"],
        "creator_birthplace": creator["birthplace"],
        "creator_wikidata": creator["wikidata"],
        "date_created": _text(cho, "dcterms:created", lang="en") or _text(cho, "dcterms:created"),
        "dimensions": _text(cho, "dcterms:extent", lang="en") or _text(cho, "dcterms:extent"),
        "medium": _collect_concept_labels(rdf, cho, "dcterms:medium"),
        "techniques": _collect_concept_labels(rdf, cho, "edmfp:technique"),
        "image_url": image_url,
        "iiif_service_url": iiif_service_url,
        "rights_url": rights_url,
        "source_url": f"https://www.rijksmuseum.nl/nl/collectie/{_text(cho, 'dc:identifier')}" if _text(cho, "dc:identifier") else None,
        "datestamp": datestamp,
        "raw_xml": raw_xml,
    }


@dataclass(slots=True)
class RijksConfig:
    set_spec: str | None = None
    max_pages: int | None = None
    sleep_seconds: float = 0.1
    resume: bool = True


class RijksIngester:
    """Harvests Rijksmuseum collection via OAI-PMH into a bespoke DuckDB."""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn
        self._ensure_schema()

    def _ensure_schema(self):
        for stmt in SCHEMA_DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self.conn.execute(stmt)

    def _save_state(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO rijks_harvest_state (key, value) VALUES (?, ?)",
            [key, value],
        )

    def _load_state(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM rijks_harvest_state WHERE key = ?", [key]
        ).fetchone()
        return row[0] if row else None

    def _object_exists(self, identifier: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM rijks_objects WHERE identifier = ?", [identifier]
        ).fetchone()
        return row is not None

    def _upsert_record(self, rec: dict):
        self.conn.execute(
            """
            INSERT OR REPLACE INTO rijks_objects (
                identifier, object_number, title, description, object_type,
                creator_name, creator_birth_date, creator_death_date,
                creator_birthplace, creator_wikidata,
                date_created, dimensions, medium, techniques,
                image_url, iiif_service_url, rights_url, source_url,
                datestamp, fetched_at, raw_xml
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMP), ?, ?)
            """,
            [
                rec["identifier"],
                rec["object_number"],
                rec["title"],
                rec["description"],
                rec["object_type"],
                rec["creator_name"],
                rec["creator_birth_date"],
                rec["creator_death_date"],
                rec["creator_birthplace"],
                rec["creator_wikidata"],
                rec["date_created"],
                rec["dimensions"],
                rec["medium"],
                rec["techniques"],
                rec["image_url"],
                rec["iiif_service_url"],
                rec["rights_url"],
                rec["source_url"],
                rec["datestamp"],
                now_utc(),
                rec["raw_xml"],
            ],
        )

    def _upsert_object_sets(self, identifier: str, set_specs: list[str]):
        for spec in set_specs:
            self.conn.execute(
                "INSERT OR IGNORE INTO rijks_object_sets (identifier, set_spec) VALUES (?, ?)",
                [identifier, spec],
            )

    def sync_sets(self):
        """Fetch all OAI-PMH sets and store them in rijks_sets."""
        root = _fetch_xml(f"{OAI_ENDPOINT}?verb=ListSets")
        list_sets = root.find("oai:ListSets", NS)
        if list_sets is None:
            print("Rijks: no sets found")
            return

        count = 0
        for set_el in list_sets.findall("oai:set", NS):
            spec = _text(set_el, "oai:setSpec")
            name = _text(set_el, "oai:setName")
            if spec:
                self.conn.execute(
                    "INSERT OR REPLACE INTO rijks_sets (set_spec, set_name) VALUES (?, ?)",
                    [spec, name],
                )
                count += 1

        print(f"Rijks: synced {count} sets")

    def _state_key(self, set_spec: str | None) -> str:
        """Per-set resumption token key."""
        if set_spec:
            return f"resumption_token:{set_spec}"
        return "resumption_token"

    def harvest(self, cfg: RijksConfig):
        """Harvest records, optionally filtered by set. Skips already-fetched objects."""
        state_key = self._state_key(cfg.set_spec)
        set_label = cfg.set_spec or "all"

        # Determine starting URL
        resumption_token = None
        if cfg.resume:
            resumption_token = self._load_state(state_key)
            if resumption_token:
                print(f"Rijks [{set_label}]: resuming from saved token")

        if resumption_token:
            url = f"{OAI_ENDPOINT}?verb=ListRecords&resumptionToken={resumption_token}"
        else:
            url = f"{OAI_ENDPOINT}?verb=ListRecords&metadataPrefix=edm"
            if cfg.set_spec:
                url += f"&set={cfg.set_spec}"

        pages = 0
        total_new = 0
        total_skipped = 0
        complete_list_size = "?"

        while url:
            if cfg.max_pages is not None and pages >= cfg.max_pages:
                print(f"Rijks [{set_label}]: reached max_pages={cfg.max_pages}, stopping")
                break

            root = _fetch_xml(url)

            error = root.find("oai:error", NS)
            if error is not None:
                code = error.get("code", "unknown")
                msg = error.text or ""
                raise RuntimeError(f"OAI-PMH error ({code}): {msg}")

            list_records = root.find("oai:ListRecords", NS)
            if list_records is None:
                print(f"Rijks [{set_label}]: no ListRecords element, stopping")
                break

            page_new = 0
            page_skipped = 0
            for record_el in list_records.findall("oai:record", NS):
                identifier, datestamp, set_specs = _parse_record_header(record_el)
                if not identifier:
                    continue

                # Always record set memberships
                self._upsert_object_sets(identifier, set_specs)

                # Skip full parse if already in DB
                if self._object_exists(identifier):
                    page_skipped += 1
                    continue

                rec = _parse_record_metadata(record_el, identifier, datestamp)
                if rec is None:
                    continue
                self._upsert_record(rec)
                page_new += 1

            total_new += page_new
            total_skipped += page_skipped
            pages += 1

            # Extract resumptionToken
            token_el = list_records.find("oai:resumptionToken", NS)
            if token_el is not None and token_el.text:
                resumption_token = token_el.text.strip()
                self._save_state(state_key, resumption_token)
                complete_list_size = token_el.get("completeListSize", "?")
                url = f"{OAI_ENDPOINT}?verb=ListRecords&resumptionToken={resumption_token}"
            else:
                resumption_token = None
                self._save_state(state_key, "")
                url = None

            if pages % 10 == 0 or url is None:
                existing = self.conn.execute("SELECT count(*) FROM rijks_objects").fetchone()[0]
                print(
                    f"Rijks [{set_label}]: page {pages}, "
                    f"+{page_new} new, ~{page_skipped} skipped, "
                    f"{existing:,} total in db "
                    f"(list size: {complete_list_size if resumption_token else 'done'})"
                )

            if url and cfg.sleep_seconds > 0:
                time.sleep(cfg.sleep_seconds)

        # Clear completed state so re-running does a fresh harvest
        if resumption_token is None:
            self._save_state(state_key, "")

        count = self.conn.execute("SELECT count(*) FROM rijks_objects").fetchone()[0]
        with_image = self.conn.execute(
            "SELECT count(*) FROM rijks_objects WHERE image_url IS NOT NULL"
        ).fetchone()[0]
        print(
            f"Rijks [{set_label}]: done — {total_new} new, {total_skipped} skipped, "
            f"{count:,} total objects ({with_image:,} with images)"
        )

    def reparse(self):
        """Re-parse all objects from stored raw_xml without re-downloading."""
        rows = self.conn.execute(
            "SELECT identifier, datestamp, raw_xml FROM rijks_objects"
        ).fetchall()

        updated = 0
        for identifier, datestamp, raw_xml in rows:
            record_el = ET.fromstring(raw_xml)
            rec = _parse_record_metadata(record_el, identifier, str(datestamp) if datestamp else None)
            if rec is None:
                continue
            self._upsert_record(rec)
            updated += 1

        with_image = self.conn.execute(
            "SELECT count(*) FROM rijks_objects WHERE image_url IS NOT NULL"
        ).fetchone()[0]
        print(f"Rijks: reparsed {updated:,} objects ({with_image:,} with images)")

    def run(self, cfg: RijksConfig):
        self.sync_sets()
        self.harvest(cfg)


