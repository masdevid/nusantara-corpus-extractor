from meaning_crosscheck import MeaningCrossChecker
from models import IssueType


def test_no_flags_when_agreeing(sample_language, make_entry):
    checker = MeaningCrossChecker(pass_number=1, language=sample_language)
    entries = [make_entry(headword="abara", gloss_pivot="burung gagak"),
               make_entry(headword="abiya", gloss_pivot="layar")]
    flags = checker.crosscheck(entries)
    assert flags == []


def test_duplicate_headword_different_gloss(sample_language, make_entry):
    checker = MeaningCrossChecker(pass_number=1, language=sample_language)
    entries = [make_entry(headword="abara", gloss_pivot="burung gagak"),
               make_entry(headword="abara", gloss_pivot="layar")]
    flags = checker.crosscheck(entries)
    assert len(flags) == 1
    assert flags[0].issue_type == IssueType.DUPLICATE_HEADWORD
    assert flags[0].needs_web_check


def test_existing_corpus_conflict(sample_language, make_entry):
    checker = MeaningCrossChecker(pass_number=1, language=sample_language)
    existing = [make_entry(headword="abara", gloss_pivot="burung gagak")]
    entries = [make_entry(headword="abara", gloss_pivot="layar")]
    flags = checker.crosscheck(entries, existing_corpus=existing)
    assert len(flags) == 1
    assert flags[0].issue_type == IssueType.MEANING_CONFLICT


def test_existing_corpus_agree_no_flag(sample_language, make_entry):
    checker = MeaningCrossChecker(pass_number=1, language=sample_language)
    existing = [make_entry(headword="abara", gloss_pivot="burung gagak")]
    entries = [make_entry(headword="abara", gloss_pivot="burung gagak")]
    flags = checker.crosscheck(entries, existing_corpus=existing)
    assert flags == []


def test_glosses_agree_normalizes_trailing_period(sample_language, make_entry):
    checker = MeaningCrossChecker(pass_number=1, language=sample_language)
    existing = [make_entry(headword="abara", gloss_pivot="burung gagak.")]
    entries = [make_entry(headword="abara", gloss_pivot="burung gagak")]
    flags = checker.crosscheck(entries, existing_corpus=existing)
    assert flags == []
