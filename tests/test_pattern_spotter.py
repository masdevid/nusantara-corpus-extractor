from pattern_spotter import PatternSpotter
from models import DictionaryEntry, FlaggedTerm, IssueType


def _flag(entry_id, issue_type=IssueType.OCR_TYPO, attempted_fix=None,
          page_ref=None):
    return FlaggedTerm(entry_id=entry_id, headword="h", issue_type=issue_type,
                       note="n", raised_at_pass=1, attempted_fix=attempted_fix)


def test_no_patterns_when_empty():
    spotter = PatternSpotter()
    assert spotter.spot_patterns([], []) == []


def test_recurring_substitution():
    spotter = PatternSpotter()
    flags = [
        _flag("a", attempted_fix=("rn", "m")),
        _flag("b", attempted_fix=("rn", "m")),
        _flag("c", attempted_fix=("rn", "m")),
    ]
    insights = spotter._recurring_substitutions(flags)
    assert len(insights) == 1
    assert insights[0].pattern_type == "recurring_ocr_substitution"
    assert len(insights[0].affected_entry_ids) == 3


def test_recurring_substitution_below_threshold():
    spotter = PatternSpotter()
    flags = [
        _flag("a", attempted_fix=("rn", "m")),
        _flag("b", attempted_fix=("rn", "m")),
    ]
    assert spotter._recurring_substitutions(flags) == []


def test_clustered_pages():
    spotter = PatternSpotter()
    entries = [
        DictionaryEntry(id="a", headword="h", page_ref=5),
        DictionaryEntry(id="b", headword="h", page_ref=5),
        DictionaryEntry(id="c", headword="h", page_ref=5),
    ]
    flags = [_flag("a", page_ref=5), _flag("b", page_ref=5), _flag("c", page_ref=5)]
    insights = spotter._clustered_pages(flags, entries)
    assert len(insights) == 1
    assert insights[0].pattern_type == "bad_page_cluster"


def test_issue_type_hotspot():
    spotter = PatternSpotter()
    flags = [
        _flag("a", IssueType.OCR_TYPO),
        _flag("b", IssueType.OCR_TYPO),
        _flag("c", IssueType.OCR_TYPO),
        _flag("d", IssueType.LOW_CONFIDENCE),
    ]
    insights = spotter._issue_type_hotspots(flags)
    assert len(insights) == 1
    assert insights[0].pattern_type == "issue_type_hotspot"


def test_issue_type_hotspot_not_dominant():
    spotter = PatternSpotter()
    flags = [
        _flag("a", IssueType.OCR_TYPO),
        _flag("b", IssueType.LOW_CONFIDENCE),
        _flag("c", IssueType.MEANING_CONFLICT),
    ]
    assert spotter._issue_type_hotspots(flags) == []


def test_hotspot_suggestion_mapping():
    spotter = PatternSpotter()
    assert "confusion pairs" in spotter._hotspot_suggestion(IssueType.OCR_TYPO)
    assert "web-verification" in spotter._hotspot_suggestion(IssueType.MEANING_CONFLICT)
