"""Rijksmuseum LIDO XML parser.

Parses individual <lido:lido> records from the Rijksmuseum's LIDO collection dump.
The dump uses LIDO (Lightweight Information Describing Objects) XML with the namespace
http://www.lido-schema.org and includes AAT URIs, structured dimensions, bilingual
titles/descriptions, inscriptions, and Iconclass subject codes.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

LIDO_NS = "http://www.lido-schema.org"
NS = {"lido": LIDO_NS}
L = f"{{{LIDO_NS}}}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

# LIDO type URIs for materials vs techniques
_MATERIAL_TYPE = "http://terminology.lido-schema.org/termMaterialsTech_type/material"
_TECHNIQUE_TYPE = "http://terminology.lido-schema.org/termMaterialsTech_type/technique"

# Extent labels to prefer for primary dimensions (support = the object itself)
_PRIMARY_EXTENTS = {"support", "drager"}
# Extent labels to skip (frame, sight size, etc.)
_SKIP_EXTENTS = {"frame", "lijst", "sight size", "dagmaat", "rand"}


def _text(el: ET.Element | None, path: str, lang: str | None = None) -> str | None:
    """Extract text from a child element, optionally filtering by xml:lang."""
    if el is None:
        return None
    if lang:
        for child in el.findall(path, NS):
            if child.get(XML_LANG) == lang:
                t = (child.text or "").strip()
                if t:
                    return t
    child = el.find(path, NS)
    if child is not None:
        t = (child.text or "").strip()
        if t:
            return t
    return None


def _all_text(el: ET.Element | None, path: str, lang: str | None = None) -> list[str]:
    """Extract text from all matching children, optionally filtering by xml:lang."""
    if el is None:
        return []
    results = []
    for child in el.findall(path, NS):
        if lang and child.get(XML_LANG) != lang:
            continue
        t = (child.text or "").strip()
        if t:
            results.append(t)
    return results


def _aat_uri(concept_el: ET.Element | None) -> str | None:
    """Extract AAT URI from a concept element's conceptID children."""
    if concept_el is None:
        return None
    for cid in concept_el.findall("lido:conceptID", NS):
        text = (cid.text or "").strip()
        if "vocab.getty.edu/aat/" in text:
            # Validate it has an actual ID after the slash
            if re.search(r"/aat/\d+", text):
                return text
    return None


def _to_cm(value: float, unit: str) -> float | None:
    """Convert a measurement value to centimeters."""
    u = unit.lower().strip()
    if u == "cm":
        return value
    if u == "mm":
        return value / 10.0
    return None


_YEAR_RE = re.compile(r"(\d{3,4})")


def _parse_year(s: str | None) -> int | None:
    """Extract an integer year from a date string like '1642', 'ca. 1589', '1606-05-12'."""
    if not s:
        return None
    m = _YEAR_RE.search(s)
    if m:
        return int(m.group(1))
    return None


class LIDORecord:
    """Wraps a single <lido:lido> element and exposes parsed fields."""

    def __init__(self, el: ET.Element):
        self._el = el
        # Cache top-level sections
        self._desc_meta = el.find(f"{L}descriptiveMetadata")
        self._admin_meta = el.find(f"{L}administrativeMetadata")
        # Cache frequently accessed wrappers
        self._ident_wrap = (
            self._desc_meta.find(
                "lido:objectIdentificationWrap", NS
            )
            if self._desc_meta is not None
            else None
        )
        self._event_wrap = (
            self._desc_meta.find("lido:eventWrap", NS)
            if self._desc_meta is not None
            else None
        )
        self._creation_event: ET.Element | None = None
        self._creation_event_searched = False

    def _find_creation_event(self) -> ET.Element | None:
        """Find the first Expression creation event."""
        if self._creation_event_searched:
            return self._creation_event
        self._creation_event_searched = True
        if self._event_wrap is None:
            return None
        for event_set in self._event_wrap.findall("lido:eventSet", NS):
            event = event_set.find("lido:event", NS)
            if event is None:
                continue
            event_type = event.find("lido:eventType", NS)
            if event_type is None:
                continue
            # Check by conceptID or by term text
            cid = _text(event_type, "lido:conceptID")
            if cid and "expression_creation" in cid:
                self._creation_event = event
                return event
            term = _text(event_type, "lido:term", lang="en")
            if term and "creation" in term.lower():
                self._creation_event = event
                return event
        return None

    # --- Identifiers ---

    def inventory_number(self) -> str | None:
        """Object inventory number (e.g. 'SK-C-5')."""
        if self._ident_wrap is None:
            return None
        repo = self._ident_wrap.find(
            "lido:repositoryWrap/lido:repositorySet", NS
        )
        if repo is None:
            return None
        return _text(repo, "lido:workID")

    def lido_rec_id(self) -> str | None:
        """LIDO record ID (e.g. 'NL-AsdRM/lido/6813')."""
        return _text(self._el, f"{L}lidoRecID")

    def oai_identifier(self) -> str | None:
        """OAI-PMH identifier from recordInfoID (e.g. 'oai:rijksmuseum.nl:SK-A-447')."""
        if self._admin_meta is None:
            return None
        record_wrap = self._admin_meta.find("lido:recordWrap", NS)
        if record_wrap is None:
            return None
        info_set = record_wrap.find("lido:recordInfoSet", NS)
        if info_set is None:
            return None
        return _text(info_set, "lido:recordInfoID")

    # --- Titles and Descriptions ---

    def titles(self) -> tuple[str | None, str | None]:
        """Bilingual titles: (english, dutch)."""
        if self._ident_wrap is None:
            return None, None
        title_wrap = self._ident_wrap.find("lido:titleWrap", NS)
        if title_wrap is None:
            return None, None
        # Take the first titleSet (preferred title)
        title_set = title_wrap.find("lido:titleSet", NS)
        if title_set is None:
            return None, None
        en = _text(title_set, "lido:appellationValue", lang="en")
        nl = _text(title_set, "lido:appellationValue", lang="nl")
        # If only one language, also check without lang filter
        if en is None and nl is None:
            en = _text(title_set, "lido:appellationValue")
        return en, nl

    def descriptions(self) -> tuple[str | None, str | None]:
        """Bilingual descriptions: (english, dutch)."""
        if self._ident_wrap is None:
            return None, None
        desc_wrap = self._ident_wrap.find("lido:objectDescriptionWrap", NS)
        if desc_wrap is None:
            return None, None
        desc_set = desc_wrap.find("lido:objectDescriptionSet", NS)
        if desc_set is None:
            return None, None
        en = _text(desc_set, "lido:descriptiveNoteValue", lang="en")
        nl = _text(desc_set, "lido:descriptiveNoteValue", lang="nl")
        if en is None and nl is None:
            en = _text(desc_set, "lido:descriptiveNoteValue")
        return en, nl

    # --- Classification ---

    def object_type(self) -> tuple[str | None, str | None, str | None]:
        """Object work type: (label_en, label_nl, aat_uri)."""
        if self._desc_meta is None:
            return None, None, None
        class_wrap = self._desc_meta.find(
            "lido:objectClassificationWrap", NS
        )
        if class_wrap is None:
            return None, None, None
        type_wrap = class_wrap.find("lido:objectWorkTypeWrap", NS)
        if type_wrap is None:
            return None, None, None
        owt = type_wrap.find("lido:objectWorkType", NS)
        if owt is None:
            return None, None, None
        en = _text(owt, "lido:term", lang="en")
        nl = _text(owt, "lido:term", lang="nl")
        uri = _aat_uri(owt)
        return en, nl, uri

    # --- Creator ---

    def creator(self) -> dict:
        """Primary creator from the first Expression creation event.

        Returns dict with: name, role, nationality, qualifier, birth_year, death_year.
        """
        result = {
            "name": None,
            "role": None,
            "nationality": None,
            "qualifier": None,
            "birth_year": None,
            "death_year": None,
        }
        event = self._find_creation_event()
        if event is None:
            return result

        actor_el = event.find(
            "lido:eventActor/lido:actorInRole", NS
        )
        if actor_el is None:
            return result

        actor = actor_el.find("lido:actor", NS)
        if actor is not None:
            result["name"] = (
                _text(actor, "lido:nameActorSet/lido:appellationValue", lang="en")
                or _text(actor, "lido:nameActorSet/lido:appellationValue", lang="nl")
                or _text(actor, "lido:nameActorSet/lido:appellationValue")
            )
            result["nationality"] = (
                _text(actor, "lido:nationalityActor/lido:term", lang="en")
                or _text(actor, "lido:nationalityActor/lido:term", lang="nl")
                or _text(actor, "lido:nationalityActor/lido:term")
            )
            vital = actor.find("lido:vitalDatesActor", NS)
            if vital is not None:
                result["birth_year"] = _parse_year(
                    _text(vital, "lido:earliestDate")
                )
                result["death_year"] = _parse_year(
                    _text(vital, "lido:latestDate")
                )

        # Role
        role_el = actor_el.find("lido:roleActor", NS)
        if role_el is not None:
            result["role"] = (
                _text(role_el, "lido:term", lang="en")
                or _text(role_el, "lido:term", lang="nl")
                or _text(role_el, "lido:term")
            )

        # Attribution qualifier
        result["qualifier"] = (
            _text(actor_el, "lido:attributionQualifierActor", lang="en")
            or _text(actor_el, "lido:attributionQualifierActor", lang="nl")
            or _text(actor_el, "lido:attributionQualifierActor")
        )

        return result

    # --- Dates ---

    def date_range(self) -> tuple[int | None, int | None]:
        """Creation date range: (earliest_year, latest_year)."""
        event = self._find_creation_event()
        if event is None:
            return None, None
        date_el = event.find("lido:eventDate/lido:date", NS)
        if date_el is None:
            return None, None
        earliest = _parse_year(_text(date_el, "lido:earliestDate"))
        latest = _parse_year(_text(date_el, "lido:latestDate"))
        return earliest, latest

    # --- Materials and Techniques ---

    def _materials_and_techniques(self) -> tuple[list[dict], list[dict]]:
        """Parse all materials and techniques from the creation event."""
        materials: list[dict] = []
        techniques: list[dict] = []
        event = self._find_creation_event()
        if event is None:
            return materials, techniques

        for emt in event.findall("lido:eventMaterialsTech", NS):
            mt = emt.find("lido:materialsTech", NS)
            if mt is None:
                continue
            term_el = mt.find("lido:termMaterialsTech", NS)
            if term_el is None:
                continue

            entry = {
                "label_en": _text(term_el, "lido:term", lang="en"),
                "label_nl": _text(term_el, "lido:term", lang="nl"),
                "aat_uri": _aat_uri(term_el),
            }
            # Only include entries that have at least a label
            if not entry["label_en"] and not entry["label_nl"]:
                continue

            mt_type = term_el.get(f"{L}type", "")
            if "technique" in mt_type:
                techniques.append(entry)
            else:
                materials.append(entry)

        return materials, techniques

    def materials(self) -> list[dict]:
        """Materials used: list of {label_en, label_nl, aat_uri}."""
        mats, _ = self._materials_and_techniques()
        return mats

    def techniques(self) -> list[dict]:
        """Techniques used: list of {label_en, label_nl, aat_uri}."""
        _, techs = self._materials_and_techniques()
        return techs

    # --- Dimensions ---

    def all_dimensions(self) -> list[dict]:
        """All measurements: list of {type, value, unit, extent}."""
        if self._ident_wrap is None:
            return []
        meas_wrap = self._ident_wrap.find(
            "lido:objectMeasurementsWrap", NS
        )
        if meas_wrap is None:
            return []

        results = []
        for meas_set in meas_wrap.findall("lido:objectMeasurementsSet", NS):
            obj_meas = meas_set.find("lido:objectMeasurements", NS)
            if obj_meas is None:
                continue

            # Determine extent (support, frame, sight size, etc.)
            extent = (
                _text(obj_meas, "lido:extentMeasurements", lang="en")
                or _text(obj_meas, "lido:extentMeasurements", lang="nl")
                or _text(obj_meas, "lido:extentMeasurements")
            )

            for ms in obj_meas.findall("lido:measurementsSet", NS):
                mtype = (
                    _text(ms, "lido:measurementType", lang="en")
                    or _text(ms, "lido:measurementType", lang="nl")
                    or _text(ms, "lido:measurementType")
                )
                unit = (
                    _text(ms, "lido:measurementUnit", lang="en")
                    or _text(ms, "lido:measurementUnit", lang="nl")
                    or _text(ms, "lido:measurementUnit")
                )
                value_str = _text(ms, "lido:measurementValue")
                if mtype and value_str:
                    try:
                        value = float(value_str)
                    except ValueError:
                        continue
                    results.append({
                        "type": mtype.lower(),
                        "value": value,
                        "unit": unit or "",
                        "extent": extent,
                    })

        return results

    def primary_dimensions_cm(self) -> tuple[float | None, float | None, float | None]:
        """Primary support dimensions in cm: (height, width, depth).

        Prefers measurements with extent 'support'/'drager'.
        Falls back to measurements with no extent label.
        Skips frame, sight size, etc.
        Converts mm to cm.
        """
        dims = self.all_dimensions()
        if not dims:
            return None, None, None

        # Group by extent
        support_dims: dict[str, float] = {}
        no_extent_dims: dict[str, float] = {}

        for d in dims:
            extent = (d["extent"] or "").lower().strip()
            cm = _to_cm(d["value"], d["unit"])
            if cm is None:
                continue

            if extent in _SKIP_EXTENTS:
                continue
            elif extent in _PRIMARY_EXTENTS:
                support_dims[d["type"]] = cm
            elif not extent:
                no_extent_dims[d["type"]] = cm

        # Prefer support, fall back to no-extent
        best = support_dims or no_extent_dims
        return (
            best.get("height"),
            best.get("width") or best.get("breedte"),
            best.get("depth") or best.get("diepte"),
        )

    # --- Subjects ---

    def subjects(self) -> list[dict]:
        """Subject terms: list of {label, uri, scheme}."""
        if self._desc_meta is None:
            return []
        rel_wrap = self._desc_meta.find("lido:objectRelationWrap", NS)
        if rel_wrap is None:
            return []
        subj_wrap = rel_wrap.find("lido:subjectWrap", NS)
        if subj_wrap is None:
            return []

        results = []
        for subj_set in subj_wrap.findall("lido:subjectSet", NS):
            subj = subj_set.find("lido:subject", NS)
            if subj is None:
                continue

            # Concept subjects (Iconclass, etc.)
            for concept in subj.findall("lido:subjectConcept", NS):
                label = (
                    _text(concept, "lido:term", lang="en")
                    or _text(concept, "lido:term", lang="nl")
                    or _text(concept, "lido:term")
                )
                uri = None
                scheme = None
                for cid in concept.findall("lido:conceptID", NS):
                    uri = (cid.text or "").strip() or None
                    scheme = cid.get(f"{L}source") or None
                    break
                if label or uri:
                    results.append({"label": label, "uri": uri, "scheme": scheme})

            # Named person subjects
            for subj_actor in subj.findall("lido:subjectActor", NS):
                actor = subj_actor.find("lido:actor", NS)
                if actor is not None:
                    name = (
                        _text(actor, "lido:nameActorSet/lido:appellationValue", lang="en")
                        or _text(actor, "lido:nameActorSet/lido:appellationValue", lang="nl")
                        or _text(actor, "lido:nameActorSet/lido:appellationValue")
                    )
                    if name:
                        results.append({"label": name, "uri": None, "scheme": "person"})

            # Place subjects
            for subj_place in subj.findall("lido:subjectPlace", NS):
                place = subj_place.find("lido:place", NS)
                if place is not None:
                    name = (
                        _text(place, "lido:namePlaceSet/lido:appellationValue", lang="en")
                        or _text(place, "lido:namePlaceSet/lido:appellationValue", lang="nl")
                        or _text(place, "lido:namePlaceSet/lido:appellationValue")
                    )
                    place_uri = None
                    for pid in place.findall("lido:placeID", NS):
                        place_uri = (pid.text or "").strip() or None
                        break
                    if name or place_uri:
                        results.append({"label": name, "uri": place_uri, "scheme": "place"})

            # Event subjects
            for subj_event in subj.findall("lido:subjectEvent", NS):
                evt = subj_event.find("lido:event", NS)
                if evt is not None:
                    name = _text(evt, "lido:eventName/lido:appellationValue")
                    if name:
                        results.append({"label": name, "uri": None, "scheme": "event"})

        return results

    # --- Inscriptions ---

    def inscriptions(self) -> list[dict]:
        """Inscriptions: list of {text, description}."""
        if self._ident_wrap is None:
            return []
        insc_wrap = self._ident_wrap.find("lido:inscriptionsWrap", NS)
        if insc_wrap is None:
            return []

        results = []
        for insc in insc_wrap.findall("lido:inscriptions", NS):
            text = _text(insc, "lido:inscriptionTranscription")
            desc = (
                _text(insc, "lido:inscriptionDescription/lido:descriptiveNoteValue", lang="en")
                or _text(insc, "lido:inscriptionDescription/lido:descriptiveNoteValue", lang="nl")
                or _text(insc, "lido:inscriptionDescription/lido:descriptiveNoteValue")
            )
            if text or desc:
                results.append({"text": text, "description": desc})

        return results

    # --- Image and Rights ---

    def image_url(self) -> str | None:
        """Image URL from resourceWrap (Google CDN)."""
        if self._admin_meta is None:
            return None
        res_wrap = self._admin_meta.find("lido:resourceWrap", NS)
        if res_wrap is None:
            return None
        res_set = res_wrap.find("lido:resourceSet", NS)
        if res_set is None:
            return None
        rep = res_set.find("lido:resourceRepresentation", NS)
        if rep is None:
            return None
        url = _text(rep, "lido:linkResource")
        return url if url else None

    def rights_url(self) -> str | None:
        """Rights URL for the work (CC license)."""
        if self._admin_meta is None:
            return None
        rights_wrap = self._admin_meta.find("lido:rightsWorkWrap", NS)
        if rights_wrap is None:
            return None
        rights_set = rights_wrap.find("lido:rightsWorkSet", NS)
        if rights_set is None:
            return None
        rights_type = rights_set.find("lido:rightsType", NS)
        if rights_type is None:
            return None
        for cid in rights_type.findall("lido:conceptID", NS):
            text = (cid.text or "").strip()
            if text:
                return text
        return None

    def credit_line(self) -> str | None:
        """Credit line from record rights."""
        if self._admin_meta is None:
            return None
        record_wrap = self._admin_meta.find("lido:recordWrap", NS)
        if record_wrap is None:
            return None
        record_rights = record_wrap.find("lido:recordRights", NS)
        if record_rights is None:
            return None
        return _text(record_rights, "lido:creditLine")

    def record_metadata_date(self) -> str | None:
        """Last modification date of the record metadata."""
        if self._admin_meta is None:
            return None
        record_wrap = self._admin_meta.find("lido:recordWrap", NS)
        if record_wrap is None:
            return None
        info_set = record_wrap.find("lido:recordInfoSet", NS)
        if info_set is None:
            return None
        return _text(info_set, "lido:recordMetadataDate")
