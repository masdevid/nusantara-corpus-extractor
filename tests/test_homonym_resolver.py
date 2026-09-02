from homonym_resolver import HomonymResolver
from models import IssueType


def test_analyze_no_duplicates(make_entry):
    resolver = HomonymResolver()
    entries = [make_entry(headword="abara"), make_entry(headword="abiya")]
    assert resolver.analyze(entries) == []


def test_analyze_homonym_same_spelling(make_entry):
    resolver = HomonymResolver()
    entries = [make_entry(headword="bo", gloss_pivot="air"),
               make_entry(headword="bo", gloss_pivot="kata")]
    results = resolver.analyze(entries)
    assert len(results) == 1
    assert results[0]["type"] == "homonym"
    assert results[0]["action"] == "keep_separate"


def test_analyze_polysemy_shared_words(make_entry):
    resolver = HomonymResolver()
    entries = [make_entry(headword="bo", gloss_pivot="air sungai besar"),
               make_entry(headword="bo", gloss_pivot="air sungai kecil")]
    results = resolver.analyze(entries)
    assert len(results) == 1
    assert results[0]["type"] == "polysemy"
    assert results[0]["action"] == "merge_with_senses"


def test_analyze_ocr_variant(make_entry):
    resolver = HomonymResolver()
    entries = [make_entry(headword="abara", gloss_pivot="burung"),
               make_entry(headword="abarra", gloss_pivot="burung")]
    results = resolver.analyze(entries)
    assert any(r["type"] == "ocr_variant" for r in results)


def test_check_conventions_no_known(make_entry):
    resolver = HomonymResolver()
    entries = [make_entry(headword="bo")]
    assert resolver.check_conventions(entries) == []


def test_check_conventions_identical_glosses(make_entry):
    resolver = HomonymResolver()
    entries = [make_entry(headword="bo", gloss_pivot="air"),
               make_entry(headword="boo", gloss_pivot="air")]
    flags = resolver.check_conventions(entries, known_homonyms=[("bo", "boo")])
    assert len(flags) == 2
    assert flags[0].issue_type == IssueType.MEANING_CONFLICT


def test_as_conventions_section(make_entry):
    resolver = HomonymResolver()
    entries = [make_entry(headword="bo", gloss_pivot="air"),
               make_entry(headword="bo", gloss_pivot="kata")]
    results = resolver.analyze(entries)
    section = resolver.as_conventions_section(results)
    assert "## Homonyms and Variants" in section
    assert "bo" in section


def test_find_similar_pairs_threshold():
    resolver = HomonymResolver(similarity_threshold=0.8)
    pairs = resolver._find_similar_pairs(["abara", "abarra", "xyz"])
    assert ("abara", "abarra") in [tuple(sorted(p[:2])) for p in pairs]
