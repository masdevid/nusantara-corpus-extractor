from translation_checker import TranslationChecker
from models import IssueType


def test_no_flags_clean_entries(make_entry):
    checker = TranslationChecker()
    entries = [make_entry(headword="abara", gloss_pivot="burung gagak")]
    assert checker.check_entries(entries) == []


def test_empty_gloss_flagged(make_entry):
    checker = TranslationChecker()
    entries = [make_entry(headword="abara", gloss_pivot="")]
    flags = checker.check_entries(entries)
    assert len(flags) == 1
    assert flags[0].issue_type == IssueType.LOW_CONFIDENCE


def test_duplicate_headword_conflict(make_entry):
    checker = TranslationChecker()
    entries = [make_entry(headword="abara", gloss_pivot="burung"),
               make_entry(headword="abara", gloss_pivot="layar")]
    flags = checker.check_entries(entries)
    assert any(f.issue_type == IssueType.DUPLICATE_HEADWORD for f in flags)
    assert all(f.needs_web_check for f in flags)


def test_example_missing_headword(make_entry):
    checker = TranslationChecker()
    entries = [make_entry(headword="abara", examples=["ini kalimat lain"])]
    flags = checker.check_entries(entries)
    assert len(flags) == 1
    assert flags[0].issue_type == IssueType.LOW_CONFIDENCE


def test_example_contains_headword_no_flag(make_entry):
    checker = TranslationChecker()
    entries = [make_entry(headword="abara", examples=["abara terbang tinggi"])]
    assert checker.check_entries(entries) == []


def test_gloss_wrong_language_flagged():
    checker = TranslationChecker(gloss_language="indonesian")
    from models import DictionaryEntry
    entry = DictionaryEntry(headword="abara",
                            gloss_pivot="the of and in to is was that")
    flags = checker.check_entries([entry])
    assert any(f.issue_type == IssueType.MEANING_CONFLICT for f in flags)


def test_short_headword_flagged(make_entry):
    checker = TranslationChecker()
    entries = [make_entry(headword="a", gloss_pivot="burung")]
    flags = checker.check_entries(entries)
    assert any(f.needs_web_check for f in flags)


def test_headword_with_digit_flagged(make_entry):
    checker = TranslationChecker()
    entries = [make_entry(headword="abara2", gloss_pivot="burung")]
    flags = checker.check_entries(entries)
    assert any("digits" in f.note for f in flags)


def test_build_web_query_indonesian(make_entry):
    checker = TranslationChecker(gloss_language="indonesian")
    query = checker.build_web_query(make_entry(headword="abara",
                                               gloss_pivot="burung"))
    assert "abara" in query
    assert "arti bahasa Indonesia" in query


def test_build_web_query_none_for_empty(make_entry):
    checker = TranslationChecker()
    assert checker.build_web_query(make_entry(headword="", gloss_pivot="")) is None
