from conventions_extractor import ConventionsExtractor
from models import RawPage, BookProfile


def _page(text):
    return RawPage(page_number=1, text=text, was_ocr=False, ocr_confidence=1.0)


def test_extract_line_mode():
    ce = ConventionsExtractor()
    pages = [_page("kata word\nbawah low\n")]
    conv = ce.extract(pages)
    assert conv["entry_split_mode"] == "line"


def test_extract_marker_mode():
    ce = ConventionsExtractor()
    text = ("a kata •• word a bawah •• low a tempat •• place a atas •• high "
            "a depan •• front a belakang •• back a kiri •• left\n")
    conv = ce.extract([_page(text)])
    assert conv["dotted_markers"] is True


def test_detect_cross_refs():
    ce = ConventionsExtractor()
    pages = [_page("abara KS: anuwau. kata KS: x. bawah KS: y.")]
    refs = ce._detect_cross_refs(pages)
    assert refs["KS"] == 3


def test_detect_pos_codes():
    ce = ConventionsExtractor()
    pages = [_page("kata n. word v. bawah adj. low adv. num.")]
    codes = ce._detect_pos_codes(pages)
    assert "n" in codes
    assert "v" in codes


def test_has_multi_sense():
    ce = ConventionsExtractor()
    pages = [_page("1) air 2) kata 3) tempat 4) bawah 5) atas")]
    assert ce._has_multi_sense(pages) is True


def test_suggest_split_pattern_line_returns_none():
    ce = ConventionsExtractor()
    assert ce.suggest_split_pattern({"entry_split_mode": "line"}) is None


def test_suggest_split_pattern_dotted():
    ce = ConventionsExtractor()
    pattern = ce.suggest_split_pattern({"entry_split_mode": "marker",
                                        "dotted_markers": True,
                                        "cross_refs": {}})
    assert pattern is not None
    assert "•" in pattern


def test_suggest_entry_pattern_default_none():
    ce = ConventionsExtractor()
    conv = {"headword_patterns": [{"has_hyphen": False}], "dotted_markers": False}
    assert ce.suggest_entry_pattern(conv) is None


def test_suggest_entry_pattern_compound():
    ce = ConventionsExtractor()
    conv = {"headword_patterns": [{"has_hyphen": True}], "dotted_markers": False}
    pattern = ce.suggest_entry_pattern(conv)
    assert pattern is not None
    assert "headword" in pattern


def test_detect_morphology_hints_reduplication():
    ce = ConventionsExtractor()
    pages = [_page("bo-bo bo-bo bo-bo bo-bo")]
    hints = ce._detect_morphology_hints(pages)
    assert any(h["type"] == "reduplication" for h in hints)


def test_extract_accepts_profile():
    ce = ConventionsExtractor()
    profile = BookProfile(book_kind="dictionary", body_pages=[1])
    conv = ce.extract([_page("kata word")], profile=profile)
    assert "entry_split_mode" in conv
