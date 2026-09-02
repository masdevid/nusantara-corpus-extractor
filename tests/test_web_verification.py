from web_verification import WebVerificationQueue
from models import ExtractionSession, FlaggedTerm, IssueType, Language


def _session_with_flags(flags):
    lang = Language(code="shj", name="Sentani", family="Sentanic",
                    pivot_code="ind", pivot_name="Bahasa Indonesia")
    return ExtractionSession(language=lang, source_pdf="x.pdf",
                             flagged_terms=flags)


def _flag(entry_id, needs_web_check=False, suggested_query=None, resolved=False):
    return FlaggedTerm(entry_id=entry_id, headword="h",
                       issue_type=IssueType.OCR_TYPO, note="n",
                       raised_at_pass=1, needs_web_check=needs_web_check,
                       suggested_query=suggested_query, resolved=resolved)


def test_build_queue_only_web_checkable_with_query():
    session = _session_with_flags([
        _flag("a", needs_web_check=True, suggested_query="q1"),
        _flag("b", needs_web_check=True, suggested_query=None),
        _flag("c", needs_web_check=False, suggested_query="q3"),
        _flag("d", needs_web_check=True, suggested_query="q4", resolved=True),
    ])
    queue = WebVerificationQueue(session)
    tasks = queue.build_queue()
    assert len(tasks) == 1
    assert tasks[0].entry_id == "a"
    assert tasks[0].query == "q1"


def test_record_evidence_resolves_flag():
    flag = _flag("a", needs_web_check=True, suggested_query="q1")
    session = _session_with_flags([flag])
    queue = WebVerificationQueue(session)
    result = queue.record_evidence("a", "found it", ["http://x"], resolves_flag=True)
    assert result is flag
    assert flag.resolved
    assert flag.web_evidence == "found it"
    assert flag.web_sources == ["http://x"]


def test_record_evidence_no_match():
    session = _session_with_flags([])
    queue = WebVerificationQueue(session)
    assert queue.record_evidence("nope", "e", [], resolves_flag=True) is None


def test_record_evidence_not_resolving():
    flag = _flag("a", needs_web_check=True, suggested_query="q1")
    session = _session_with_flags([flag])
    queue = WebVerificationQueue(session)
    queue.record_evidence("a", "inconclusive", [], resolves_flag=False)
    assert not flag.resolved
    assert flag.web_evidence == "inconclusive"
