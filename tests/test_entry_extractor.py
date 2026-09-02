import re

from entry_extractor import EntryExtractor, MAX_CHUNK_CHARS
from models import Language, RawPage

LANG = Language(code="shj", name="Sentani", family="Sentanic",
                pivot_code="ind", pivot_name="Bahasa Indonesia")

# Sentani-style entry pattern (from references/sentani_phonology.md)
SENTANI_PATTERN = re.compile(
    r"^(?:a\s+)?[•·.]{0,3}\s*(?P<headword>[a-zà-ÿ''\-]+(?:\s+[a-zà-ÿ''\-]+)?)\s*(?P<gloss>.+)$"
)


def _page(text, number=1):
    return RawPage(page_number=number, text=text, was_ocr=False)


def test_line_mode_uppercase_starts_new_entry():
    # default pattern allows uppercase headwords (line mode is designed for
    # dictionaries where each entry starts a line with a capital headword)
    ext = EntryExtractor(LANG)
    pages = [_page("Abara burung gagak butcher bird\nAbiya layar sail")]
    entries = ext.extract(pages)
    assert len(entries) == 2
    assert entries[0].headword == "Abara"
    assert entries[1].headword == "Abiya"


def test_line_mode_joins_lowercase_continuation():
    ext = EntryExtractor(LANG)
    # lowercase continuation line is glued to the previous line
    pages = [_page("Abara burung gagak\nbutcher bird")]
    entries = ext.extract(pages)
    assert len(entries) == 1
    assert entries[0].headword == "Abara"
    assert "butcher bird" in entries[0].gloss_pivot


def test_split_mode_verb_entries():
    split = re.compile(r"(?<=\s)(?=a\s+[•·.]{0,3}\s*[a-z])")
    ext = EntryExtractor(LANG, entry_pattern=SENTANI_PATTERN, split_pattern=split)
    # pattern captures up to 2 headword tokens, rest is gloss
    pages = [_page("a kata word gloss a bawah low gloss2")]
    entries = ext.extract(pages)
    assert len(entries) == 2
    assert entries[0].headword == "kata word"
    assert entries[0].gloss_pivot == "gloss"
    assert entries[1].headword == "bawah low"
    assert entries[1].gloss_pivot == "gloss2"


def test_split_mode_collapses_inner_newlines():
    split = re.compile(r"(?<=\s)(?=a\s+[•·.]{0,3}\s*[a-z])")
    ext = EntryExtractor(LANG, entry_pattern=SENTANI_PATTERN, split_pattern=split)
    pages = [_page("a kata word\nmore a bawah low")]
    entries = ext.extract(pages)
    assert len(entries) == 2
    assert entries[0].headword == "kata word"
    assert "more" in entries[0].gloss_pivot


def test_oversized_slab_skipped():
    ext = EntryExtractor(LANG, entry_pattern=SENTANI_PATTERN)
    big = "abara " + "x" * MAX_CHUNK_CHARS
    pages = [_page(big)]
    entries = ext.extract(pages)
    assert entries == []


def test_ocr_confidence_inherited():
    ext = EntryExtractor(LANG, entry_pattern=SENTANI_PATTERN)
    page = RawPage(page_number=1, text="abara burung gagak", was_ocr=True,
                   ocr_confidence=0.8)
    entries = ext.extract([page])
    assert entries[0].confidence == 0.8


def test_digital_confidence_default():
    ext = EntryExtractor(LANG, entry_pattern=SENTANI_PATTERN)
    entries = ext.extract([_page("abara burung gagak")])
    assert entries[0].confidence == 1.0


def test_noun_entry_with_pos_marker():
    ext = EntryExtractor(LANG, entry_pattern=SENTANI_PATTERN)
    entries = ext.extract([_page("abara (aye) burung gagak butcher bird")])
    assert len(entries) == 1
    assert entries[0].headword == "abara"
    assert "burung gagak" in entries[0].gloss_pivot
