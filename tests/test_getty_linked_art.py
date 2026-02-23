"""Tests for Getty Linked Art converter against the corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from artdig.getty.linked_art import GettyObject, convert

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "getty" / "corpus"


def _load(uuid: str) -> dict:
    path = CORPUS_DIR / f"{uuid}.json"
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Corpus fixture: parametrize over all files
# ---------------------------------------------------------------------------

CORPUS_FILES = sorted(CORPUS_DIR.glob("*.json"))
CORPUS_IDS = [f.stem for f in CORPUS_FILES]


@pytest.fixture(params=CORPUS_FILES, ids=CORPUS_IDS)
def corpus_object(request: pytest.FixtureRequest) -> tuple[str, dict, GettyObject]:
    path: Path = request.param
    raw = json.loads(path.read_text())
    obj = convert(raw)
    return path.stem, raw, obj


class TestConvertAll:
    """Smoke tests that run over every object in the corpus."""

    def test_returns_getty_object(self, corpus_object: tuple[str, dict, GettyObject]):
        _, _, obj = corpus_object
        assert isinstance(obj, GettyObject)

    def test_has_id(self, corpus_object: tuple[str, dict, GettyObject]):
        uuid, _, obj = corpus_object
        assert obj.id == uuid

    def test_has_title(self, corpus_object: tuple[str, dict, GettyObject]):
        _, _, obj = corpus_object
        assert obj.title is not None and len(obj.title) > 0

    def test_to_dict_roundtrip(self, corpus_object: tuple[str, dict, GettyObject]):
        _, _, obj = corpus_object
        d = obj.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == obj.id
        assert d["title"] == obj.title


# ---------------------------------------------------------------------------
# Specific object tests
# ---------------------------------------------------------------------------


class TestLittleGirlInTuileries:
    """Detailed tests for the known sample object."""

    UUID = "00007c19-13a5-4ed4-adfd-78b08df2b92c"

    @pytest.fixture
    def obj(self) -> GettyObject:
        return convert(_load(self.UUID))

    def test_title(self, obj: GettyObject):
        assert obj.title == "Little Girl in the Tuileries"

    def test_accession_number(self, obj: GettyObject):
        assert obj.accession_number == "99.XM.42.4"

    def test_classification(self, obj: GettyObject):
        assert "Photographs" in obj.classifications

    def test_object_type(self, obj: GettyObject):
        assert obj.object_type == "Print"

    def test_medium(self, obj: GettyObject):
        assert obj.medium == "Gelatin silver print"

    def test_date(self, obj: GettyObject):
        assert obj.date == "1980"

    def test_date_begin(self, obj: GettyObject):
        assert obj.date_begin == "1980-01-01T00:00:00"

    def test_culture(self, obj: GettyObject):
        assert obj.culture == "French"

    def test_place_created(self, obj: GettyObject):
        assert obj.place_created == "Paris, France"

    def test_description(self, obj: GettyObject):
        assert obj.description is not None
        assert "young girl" in obj.description.lower()

    def test_dimensions_image(self, obj: GettyObject):
        assert "image" in obj.dimensions
        d = obj.dimensions["image"]
        assert d.height == 24.6
        assert d.width == 19.6
        assert d.unit == "cm"

    def test_dimensions_sheet(self, obj: GettyObject):
        assert "sheet" in obj.dimensions
        d = obj.dimensions["sheet"]
        assert d.height == 25.3
        assert d.width == 20.3

    def test_artist_name(self, obj: GettyObject):
        assert len(obj.artists) >= 1
        assert obj.artists[0].name == "André Kertész"

    def test_artist_role(self, obj: GettyObject):
        assert obj.artists[0].role == "Photographer"

    def test_artist_nationality(self, obj: GettyObject):
        assert obj.artists[0].nationality_and_dates == "American, born Hungary, 1894 - 1985"

    def test_copyright(self, obj: GettyObject):
        assert obj.copyright is not None
        assert "Kertész" in obj.copyright

    def test_credit_line(self, obj: GettyObject):
        assert obj.credit_line == "The J. Paul Getty Museum, Los Angeles"

    def test_department(self, obj: GettyObject):
        assert obj.department == "Photographs (Curatorial Department)"

    def test_current_location(self, obj: GettyObject):
        assert obj.current_location == "Storage"

    def test_inscriptions(self, obj: GettyObject):
        assert len(obj.inscriptions) >= 1
        assert "Kertesz" in obj.inscriptions[0]

    def test_signatures(self, obj: GettyObject):
        assert len(obj.signatures) >= 1

    def test_homepage(self, obj: GettyObject):
        assert obj.homepage is not None
        assert "108FPV" in obj.homepage

    def test_image_url(self, obj: GettyObject):
        assert obj.image_url is not None
        assert "iiif/image/" in obj.image_url

    def test_iiif_manifest(self, obj: GettyObject):
        assert obj.iiif_manifest is not None
        assert "iiif/manifest/" in obj.iiif_manifest

    def test_rights_in_copyright(self, obj: GettyObject):
        assert obj.rights == "In Copyright"
        assert obj.is_public_domain is False

    def test_identifiers(self, obj: GettyObject):
        assert obj.identifiers["dor_id"] == "127931"
        assert obj.identifiers["tms_id"] == "136124"
        assert obj.identifiers["slug"] == "108FPV"


class TestPortraitMiddleAgedMan:
    """Test a daguerreotype with different structure."""

    UUID = "00004bde-6850-4a78-9c1b-4e2b927b7a5c"

    @pytest.fixture
    def obj(self) -> GettyObject:
        return convert(_load(self.UUID))

    def test_title(self, obj: GettyObject):
        assert "Portrait" in obj.title or "Middle-aged" in (obj.title or "")

    def test_has_artist(self, obj: GettyObject):
        # May be unknown artist
        assert isinstance(obj.artists, list)

    def test_has_dimensions(self, obj: GettyObject):
        assert len(obj.dimensions) > 0


class TestVaseFragment:
    """Test an object without an image."""

    UUID = "00013555-8dca-4bd5-b487-c1ab1cd5e5e2"

    @pytest.fixture
    def obj(self) -> GettyObject:
        return convert(_load(self.UUID))

    def test_title(self, obj: GettyObject):
        assert "Vase Fragment" in (obj.title or "")

    def test_no_image(self, obj: GettyObject):
        assert obj.image_url is None

    def test_has_dimensions(self, obj: GettyObject):
        assert len(obj.dimensions) > 0


class TestCoin:
    """Test a coin (numismatics)."""

    UUID = "00041047-ced1-4199-ab62-735ccc9aac8d"

    @pytest.fixture
    def obj(self) -> GettyObject:
        return convert(_load(self.UUID))

    def test_title(self, obj: GettyObject):
        assert "Coin" in (obj.title or "")

    def test_no_image(self, obj: GettyObject):
        # Coins in this corpus don't have representation
        assert obj.image_url is None


class TestMissal:
    """Test a manuscript (complex object with many images)."""

    UUID = "00015a8d-3b06-4373-911e-2d867ff862f4"

    @pytest.fixture
    def obj(self) -> GettyObject:
        return convert(_load(self.UUID))

    def test_title(self, obj: GettyObject):
        assert "Missal" in (obj.title or "")

    def test_has_image(self, obj: GettyObject):
        assert obj.image_url is not None
