from models import (
    BookProfile,
    DictionaryEntry,
    ExtractionSession,
    FlaggedTerm,
    IssueType,
    Language,
    PatternInsight,
    QualityReport,
    Script,
)


def test_language_defaults():
    lang = Language(code="shj", name="Sentani", family="Sentanic",
                    pivot_code="ind", pivot_name="Bahasa Indonesia")
    assert lang.script == Script.LATIN_DIACRITIC


def test_dictionary_entry_as_corpus_row(make_entry):
    entry = make_entry(id="abc123", headword="abara", part_of_speech="n",
                       examples=["ex1"], page_ref=26, confidence=0.95,
                       source_book="set", source_page=26)
    row = entry.as_corpus_row()
    assert row["id"] == "abc123"
    assert row["headword"] == "abara"
    assert row["pos"] == "n"
    assert row["gloss_pivot"] == "burung gagak butcher bird"
    assert row["examples"] == ["ex1"]
    assert row["page_ref"] == 26
    assert row["confidence"] == 0.95
    assert row["source_language"] == "shj"
    assert row["source_book"] == "set"
    assert row["source_page"] == 26


def test_flagged_term_markdown_row_open():
    flag = FlaggedTerm(entry_id="e1", headword="abara",
                       issue_type=IssueType.OCR_TYPO, note="n", raised_at_pass=1)
    assert "🚩 open" in flag.as_markdown_row()


def test_flagged_term_markdown_row_resolved_web():
    flag = FlaggedTerm(entry_id="e1", headword="abara",
                       issue_type=IssueType.OCR_TYPO, note="n", raised_at_pass=1,
                       resolved=True, web_evidence="found it")
    assert "🌐 resolved (web)" in flag.as_markdown_row()


def test_pattern_insight_as_markdown():
    insight = PatternInsight(pattern_type="bad_page_cluster", description="d",
                             affected_entry_ids=["a", "b"], suggested_action="s")
    md = insight.as_markdown()
    assert "bad_page_cluster" in md
    assert "Suggested action" in md


def test_quality_report_as_markdown():
    report = QualityReport(pass_number=1, entries_in=10, entries_out=8,
                           typo_fixes_applied=2, flags_raised=3,
                           flags_resolved=1, converged=False)
    md = report.as_markdown()
    assert "Pass 1" in md
    assert "no — another pass needed" in md


def test_book_profile_as_markdown():
    profile = BookProfile(book_kind="dictionary", body_pages=[5, 6, 7],
                          conventions={"marker density (body)": "1.0 per page"},
                          suggested_settings=["- split_before: `x`"])
    md = profile.as_markdown()
    assert "dictionary" in md
    assert "3 pages (5–7)" in md
    assert "split_before" in md


def test_extraction_session_open_flags():
    session = ExtractionSession(language=Language(code="shj", name="Sentani",
                                                  family="Sentanic", pivot_code="ind",
                                                  pivot_name="Bahasa Indonesia"),
                                source_pdf="x.pdf")
    session.flagged_terms = [
        FlaggedTerm(entry_id="a", headword="h", issue_type=IssueType.OCR_TYPO,
                    note="n", raised_at_pass=1, resolved=False),
        FlaggedTerm(entry_id="b", headword="h", issue_type=IssueType.OCR_TYPO,
                    note="n", raised_at_pass=1, resolved=True),
    ]
    assert len(session.open_flags()) == 1
    assert session.flags_needing_web_check() == []


def test_extraction_session_flags_needing_web_check():
    session = ExtractionSession(language=Language(code="shj", name="Sentani",
                                                  family="Sentanic", pivot_code="ind",
                                                  pivot_name="Bahasa Indonesia"),
                                source_pdf="x.pdf")
    session.flagged_terms = [
        FlaggedTerm(entry_id="a", headword="h", issue_type=IssueType.OCR_TYPO,
                    note="n", raised_at_pass=1, needs_web_check=True),
    ]
    assert len(session.flags_needing_web_check()) == 1


def test_extraction_session_entries_by_headword(make_entry):
    session = ExtractionSession(language=Language(code="shj", name="Sentani",
                                                  family="Sentanic", pivot_code="ind",
                                                  pivot_name="Bahasa Indonesia"),
                                source_pdf="x.pdf")
    session.entries = [make_entry(headword="abara"), make_entry(headword="abiya")]
    buckets = session.entries_by_headword()
    assert set(buckets.keys()) == {"abara", "abiya"}
