"""Convert Getty Linked Art JSON-LD objects to a flat, human-friendly dict."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Getty AAT vocabulary URIs used for classification lookups.
AAT_PREFERRED_TERM = "http://vocab.getty.edu/aat/300404670"
AAT_PRIMARY_TITLE = "https://data.getty.edu/local/thesaurus/object-title-primary"
AAT_ACCESSION_NUMBER = "http://vocab.getty.edu/aat/300312355"
AAT_DESCRIPTION = "http://vocab.getty.edu/aat/300080091"
AAT_MATERIALS = "http://vocab.getty.edu/aat/300435429"
AAT_CREDIT_LINE = "http://vocab.getty.edu/aat/300435418"
AAT_COPYRIGHT = "http://vocab.getty.edu/aat/300435434"
AAT_CULTURE = "http://vocab.getty.edu/aat/300055768"
AAT_OBJECT_TYPE = "http://vocab.getty.edu/aat/300435443"
AAT_PLACE_CREATED = "http://vocab.getty.edu/aat/300435448"
AAT_DIMENSIONS_DESC = "http://vocab.getty.edu/aat/300435430"
AAT_INSCRIPTION = "http://vocab.getty.edu/aat/300435414"
AAT_SIGNATURE = "http://vocab.getty.edu/aat/300028705"
AAT_HEIGHT = "http://vocab.getty.edu/aat/300055644"
AAT_WIDTH = "http://vocab.getty.edu/aat/300055647"
AAT_CLASSIFICATION_CATEGORY = "http://vocab.getty.edu/aat/300435444"
AAT_CC0 = "http://creativecommons.org/publicdomain/zero/1.0/"

LOCAL_DOR_ID = "https://data.getty.edu/local/thesaurus/dor-id"
LOCAL_TMS_ID = "https://data.getty.edu/local/thesaurus/tms-id"
LOCAL_SLUG = "https://data.getty.edu/local/thesaurus/slug-identifier"
LOCAL_ASSET_ID = "https://data.getty.edu/local/thesaurus/asset-identifier"
LOCAL_PRODUCER_DESC = "https://data.getty.edu/local/thesaurus/producer-description"
LOCAL_PRODUCER_NAME = "https://data.getty.edu/local/thesaurus/producer-name"
LOCAL_PRODUCER_NAT_DATES = "https://data.getty.edu/local/thesaurus/nationality-and-dates"
LOCAL_PRODUCER_ROLE = "https://data.getty.edu/local/thesaurus/producer-role-statement"
LOCAL_IIIF_MANIFEST = "https://data.getty.edu/local/thesaurus/iiif-manifest"
LOCAL_RIGHTS_STATEMENT = "https://data.getty.edu/local/thesaurus/rights-statement"
LOCAL_DIMS_IMAGE = "https://data.getty.edu/local/thesaurus/dimensions-measured-image"
LOCAL_DIMS_SHEET = "https://data.getty.edu/local/thesaurus/dimensions-measured-sheet"

OBJECT_PREFIX = "https://data.getty.edu/museum/collection/object/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_class(item: dict, aat_id: str) -> bool:
    """Check if a Linked Art node is classified_as the given AAT URI."""
    for cls in item.get("classified_as", []):
        if cls.get("id") == aat_id:
            return True
        # Also check nested classified_as (e.g. classification category)
        for inner in cls.get("classified_as", []):
            if inner.get("id") == aat_id:
                return True
    return False


def _has_technique(item: dict, technique_id: str) -> bool:
    """Check if a node's assigned_by contains the given technique."""
    for assignment in item.get("assigned_by", []):
        for tech in assignment.get("technique", []):
            if tech.get("id") == technique_id:
                return True
    return False


def _find_by_class(items: list[dict], aat_id: str) -> dict | None:
    """Find the first item classified_as the given AAT URI."""
    for item in items:
        if _has_class(item, aat_id):
            return item
    return None


def _find_all_by_class(items: list[dict], aat_id: str) -> list[dict]:
    """Find all items classified_as the given AAT URI."""
    return [item for item in items if _has_class(item, aat_id)]


def _content(item: dict | None) -> str | None:
    if item is None:
        return None
    val = item.get("content")
    return val.strip() if isinstance(val, str) and val.strip() else None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Artist:
    name: str | None = None
    role: str | None = None
    nationality_and_dates: str | None = None
    description: str | None = None
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Dimensions:
    height: float | None = None
    width: float | None = None
    unit: str | None = None
    display: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class GettyObject:
    """Human-friendly representation of a Getty Linked Art object."""

    id: str | None = None
    title: str | None = None
    accession_number: str | None = None
    classifications: list[str] = field(default_factory=list)
    object_type: str | None = None
    medium: str | None = None
    date: str | None = None
    date_begin: str | None = None
    date_end: str | None = None
    culture: str | None = None
    place_created: str | None = None
    description: str | None = None
    dimensions: dict[str, Dimensions] = field(default_factory=dict)
    artists: list[Artist] = field(default_factory=list)
    copyright: str | None = None
    rights: str | None = None
    credit_line: str | None = None
    department: str | None = None
    current_location: str | None = None
    inscriptions: list[str] = field(default_factory=list)
    signatures: list[str] = field(default_factory=list)
    homepage: str | None = None
    image_url: str | None = None
    iiif_manifest: str | None = None
    is_public_domain: bool = False
    identifiers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for k, v in self.__dict__.items():
            if v is None or v == [] or v == {}:
                continue
            if k == "dimensions":
                d[k] = {name: dim.to_dict() for name, dim in v.items()}
            elif k == "artists":
                d[k] = [a.to_dict() for a in v]
            else:
                d[k] = v
        return d


# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------


def convert(raw: dict) -> GettyObject:
    """Convert a Getty Linked Art JSON-LD dict to a flat GettyObject."""
    obj = GettyObject()

    # ID (UUID from the object URL)
    obj_id = raw.get("id", "")
    if obj_id.startswith(OBJECT_PREFIX):
        obj.id = obj_id[len(OBJECT_PREFIX):]
    else:
        obj.id = obj_id.rstrip("/").split("/")[-1] if obj_id else None

    identified_by = raw.get("identified_by", [])
    referred_to_by = raw.get("referred_to_by", [])

    # Title: prefer Name with Preferred Term classification
    obj.title = _extract_title(identified_by, raw.get("_label"))

    # Accession number
    acc = _find_by_class(identified_by, AAT_ACCESSION_NUMBER)
    obj.accession_number = _content(acc)

    # Classifications (types with classification category)
    for cls in raw.get("classified_as", []):
        if _has_class(cls, AAT_CLASSIFICATION_CATEGORY):
            label = cls.get("_label")
            if label:
                obj.classifications.append(label)

    # Object type, medium, culture, place created, description, copyright,
    # credit line, dimensions statement, inscriptions, signatures
    # — all live in referred_to_by
    obj.object_type = _content(_find_by_class(referred_to_by, AAT_OBJECT_TYPE))
    obj.medium = _content(_find_by_class(referred_to_by, AAT_MATERIALS))
    obj.culture = _content(_find_by_class(referred_to_by, AAT_CULTURE))
    obj.place_created = _content(_find_by_class(referred_to_by, AAT_PLACE_CREATED))
    obj.copyright = _content(_find_by_class(referred_to_by, AAT_COPYRIGHT))
    obj.credit_line = _content(_find_by_class(referred_to_by, AAT_CREDIT_LINE))

    # Description: prefer markdown format
    for desc in _find_all_by_class(referred_to_by, AAT_DESCRIPTION):
        fmt = desc.get("format", "")
        content = _content(desc)
        if content and fmt == "text/markdown":
            obj.description = content
            break
        if content and not obj.description:
            obj.description = content

    # Inscriptions and signatures (live in "carries", not "referred_to_by")
    carries = raw.get("carries", [])
    obj.inscriptions = [
        _content(i) for i in _find_all_by_class(carries, AAT_INSCRIPTION) if _content(i)
    ]
    obj.signatures = [
        _content(i) for i in _find_all_by_class(carries, AAT_SIGNATURE) if _content(i)
    ]

    # Dimensions (structured from dimension array)
    _extract_dimensions(raw.get("dimension", []), referred_to_by, obj)

    # Production / artist info
    produced_by = raw.get("produced_by", {})
    _extract_artists(produced_by, obj)

    # Date from production timespan
    timespan = produced_by.get("timespan", {})
    for ident in timespan.get("identified_by", []):
        content = _content(ident)
        if content:
            obj.date = content
            break
    obj.date_begin = timespan.get("begin_of_the_begin")
    obj.date_end = timespan.get("end_of_the_end")

    # Department
    for keeper in raw.get("current_keeper", []):
        label = keeper.get("_label")
        if label:
            obj.department = label
            break

    # Current location
    location = raw.get("current_location")
    if isinstance(location, dict):
        for ident in location.get("identified_by", []):
            content = _content(ident)
            if content:
                obj.current_location = content
                break

    # URLs
    for item in raw.get("subject_of", []):
        item_id = item.get("id", "")
        if "getty.edu/art/collection/object/" in item_id:
            obj.homepage = item_id
        elif _has_class(item, LOCAL_IIIF_MANIFEST):
            obj.iiif_manifest = item_id

    # Image URL
    rep = raw.get("representation", [])
    if rep and isinstance(rep[0], dict):
        obj.image_url = rep[0].get("id")

    # Rights / public domain
    for right in raw.get("subject_to", []):
        if _has_class(right, AAT_CC0):
            obj.is_public_domain = True
        for cls in right.get("classified_as", []):
            if cls.get("id") == LOCAL_RIGHTS_STATEMENT:
                desc = right.get("referred_to_by", [])
                for d in desc:
                    content = _content(d)
                    if content:
                        obj.rights = content
                        break

    # Identifiers
    _extract_identifiers(identified_by, obj)

    return obj


def _extract_title(identified_by: list[dict], fallback: str | None) -> str | None:
    """Extract preferred title from identified_by entries."""
    preferred = None
    first_name = None
    for entry in identified_by:
        if entry.get("type") != "Name":
            continue
        content = _content(entry)
        if not content:
            continue
        if first_name is None:
            first_name = content
        if _has_class(entry, AAT_PREFERRED_TERM) or _has_class(entry, AAT_PRIMARY_TITLE):
            preferred = content
            break
    return preferred or first_name or fallback


def _extract_dimensions(
    dimension_items: list[dict], referred_to_by: list[dict], obj: GettyObject
) -> None:
    """Extract structured dimensions from dimension array and display strings."""
    # Group measurements by their dimension set
    sets: dict[str, dict[str, float | str | None]] = {}

    for dim in dimension_items:
        # Skip sort numbers and sequence attributes
        if _has_class(dim, AAT_HEIGHT) or _has_class(dim, AAT_WIDTH):
            # Determine which measurement set this belongs to
            set_name = "default"
            for member in dim.get("member_of", []):
                label = member.get("_label", "")
                if "Image" in label:
                    set_name = "image"
                elif "Sheet" in label:
                    set_name = "sheet"
                elif "Overall" in label:
                    set_name = "overall"
                elif "Mount" in label:
                    set_name = "mount"
                else:
                    # Try to extract a name from the label
                    parts = label.replace("Dimensions Set:", "").strip()
                    if parts:
                        set_name = parts.lower()

            if set_name not in sets:
                sets[set_name] = {}

            unit_label = dim.get("unit", {}).get("_label", "")
            if "Centimeters" in unit_label:
                sets[set_name]["unit"] = "cm"
            elif unit_label:
                sets[set_name]["unit"] = unit_label

            if _has_class(dim, AAT_HEIGHT):
                sets[set_name]["height"] = dim.get("value")
            elif _has_class(dim, AAT_WIDTH):
                sets[set_name]["width"] = dim.get("value")

    # Also grab display strings from referred_to_by
    display_strings: dict[str, str] = {}
    for ref in _find_all_by_class(referred_to_by, AAT_DIMENSIONS_DESC):
        content = _content(ref)
        if not content:
            continue
        # Figure out which set this belongs to
        set_name = "default"
        for assignment in ref.get("assigned_by", []):
            for tech in assignment.get("technique", []):
                label = tech.get("_label", "")
                if "Image" in label:
                    set_name = "image"
                elif "Sheet" in label:
                    set_name = "sheet"
                elif "Overall" in label:
                    set_name = "overall"
                elif "Mount" in label:
                    set_name = "mount"
        display_strings[set_name] = content

    # Build Dimensions objects
    all_set_names = set(sets.keys()) | set(display_strings.keys())
    for name in sorted(all_set_names):
        vals = sets.get(name, {})
        dims = Dimensions(
            height=vals.get("height"),
            width=vals.get("width"),
            unit=vals.get("unit"),
            display=display_strings.get(name),
        )
        obj.dimensions[name] = dims


def _extract_artists(produced_by: dict, obj: GettyObject) -> None:
    """Extract artist info from produced_by."""
    referred = produced_by.get("referred_to_by", [])
    carried_out_by = produced_by.get("carried_out_by", [])

    # Build a lookup of role statements per person
    for person in carried_out_by:
        artist = Artist()
        artist.name = person.get("_label")
        person_id = person.get("id", "")
        if "/person/" in person_id:
            artist.id = person_id.split("/person/")[-1]

        # Role statement is inside the person's referred_to_by
        for ref in person.get("referred_to_by", []):
            if _has_class(ref, LOCAL_PRODUCER_ROLE):
                artist.role = _content(ref)

        obj.artists.append(artist)

    # Producer description and nationality from production-level referred_to_by
    name_from_ref = _content(_find_by_class(referred, LOCAL_PRODUCER_NAME))
    desc_from_ref = _content(_find_by_class(referred, LOCAL_PRODUCER_DESC))
    nat_from_ref = _content(_find_by_class(referred, LOCAL_PRODUCER_NAT_DATES))

    # Attach to matching artist, or create one if none exist
    if obj.artists:
        obj.artists[0].description = desc_from_ref
        obj.artists[0].nationality_and_dates = nat_from_ref
        if not obj.artists[0].name and name_from_ref:
            obj.artists[0].name = name_from_ref
    elif name_from_ref or desc_from_ref:
        obj.artists.append(
            Artist(
                name=name_from_ref,
                description=desc_from_ref,
                nationality_and_dates=nat_from_ref,
            )
        )


def _extract_identifiers(identified_by: list[dict], obj: GettyObject) -> None:
    """Extract known identifiers (DOR ID, TMS ID, slug)."""
    mapping = {
        LOCAL_DOR_ID: "dor_id",
        LOCAL_TMS_ID: "tms_id",
        LOCAL_SLUG: "slug",
    }
    for entry in identified_by:
        content = _content(entry)
        if not content:
            continue
        for aat_id, key in mapping.items():
            if _has_class(entry, aat_id):
                # Clean up slug prefix
                if key == "slug" and content.startswith("urn:getty-local:idm:object:slug/"):
                    content = content.split("/")[-1]
                obj.identifiers[key] = content
                break
