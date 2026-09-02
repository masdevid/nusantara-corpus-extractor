from quality_loop import QualityLoop
from models import ExtractionSession, FlaggedTerm, IssueType, Language


def _session():
    lang = Language(code="shj", name="Sentani", family="Sentanic",
                    pivot_code="ind", pivot_name="Bahasa Indonesia")
    return ExtractionSession(language=lang, source_pdf="x.pdf")


def _flag(entry_id, resolved=False):
    return FlaggedTerm(entry_id=entry_id, headword="h",
                       issue_type=IssueType.OCR_TYPO, note="n",
                       raised_at_pass=1, resolved=resolved)


def test_reconcile_flags_resolves_old_not_reraised():
    session = _session()
    session.flagged_terms = [_flag("a"), _flag("b")]
    loop = QualityLoop.__new__(QualityLoop)
    loop.session = session
    new_flags = [_flag("a")]  # 'a' re-raised, 'b' not
    resolved = loop._reconcile_flags(new_flags)
    assert resolved == 1
    assert session.flagged_terms[1].resolved is True


def test_reconcile_flags_dedupes_reraised():
    session = _session()
    session.flagged_terms = [_flag("a")]
    loop = QualityLoop.__new__(QualityLoop)
    loop.session = session
    new_flags = [_flag("a"), _flag("a")]
    loop._reconcile_flags(new_flags)
    # 'a' already open -> not duplicated; only the original remains
    assert len(session.flagged_terms) == 1


def test_reconcile_flags_adds_fresh():
    session = _session()
    loop = QualityLoop.__new__(QualityLoop)
    loop.session = session
    new_flags = [_flag("new1"), _flag("new2")]
    loop._reconcile_flags(new_flags)
    assert len(session.flagged_terms) == 2
