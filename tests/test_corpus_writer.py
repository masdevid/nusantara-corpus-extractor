import json

from corpus_writer import CorpusWriter
from models import BookProfile, FlaggedTerm, IssueType, PatternInsight, QualityReport


def test_write_corpus_language_mode(tmp_path, make_entry):
    writer = CorpusWriter(str(tmp_path), "shj")
    entries = [make_entry(headword="abara", gloss_pivot="burung")]
    path = writer.write_corpus(entries)
    assert path.endswith("corpus_shj.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    assert rows[0]["headword"] == "abara"


def test_write_corpus_book_mode(tmp_path, make_entry):
    writer = CorpusWriter(str(tmp_path), "shj", book_id="set")
    entries = [make_entry(headword="abara", gloss_pivot="burung")]
    path = writer.write_corpus(entries)
    assert path.endswith("books/set/entries.jsonl")
    assert path.startswith(str(tmp_path))


def test_write_flagged_terms(tmp_path, make_entry):
    writer = CorpusWriter(str(tmp_path), "shj")
    flag = FlaggedTerm(entry_id="e1", headword="abara",
                       issue_type=IssueType.OCR_TYPO, note="n",
                       raised_at_pass=1)
    path = writer.write_flagged_terms([flag])
    content = open(path, encoding="utf-8").read()
    assert "abara" in content
    assert "ocr_typo" in content


def test_write_book_profile(tmp_path):
    writer = CorpusWriter(str(tmp_path), "shj")
    profile = BookProfile(book_kind="dictionary", front_matter_pages=[],
                          body_pages=[1], back_matter_pages=[],
                          unreadable_pages=[], notes=[])
    path = writer.write_book_profile(profile)
    assert "dictionary" in open(path, encoding="utf-8").read()


def test_write_quality_report(tmp_path):
    writer = CorpusWriter(str(tmp_path), "shj")
    report = QualityReport(pass_number=3, entries_in=5, entries_out=5,
                           typo_fixes_applied=1, flags_raised=1,
                           flags_resolved=0, converged=False)
    path = writer.write_quality_report(report)
    assert path.endswith("quality_report_3.md")


def test_write_pattern_insights_empty(tmp_path):
    writer = CorpusWriter(str(tmp_path), "shj")
    path = writer.write_pattern_insights([])
    assert "No systematic patterns" in open(path, encoding="utf-8").read()


def test_write_pattern_insights_nonempty(tmp_path):
    writer = CorpusWriter(str(tmp_path), "shj")
    insight = PatternInsight(pattern_type="recurring_ocr_substitution",
                             description="d", affected_entry_ids=["a"],
                             suggested_action="fix")
    path = writer.write_pattern_insights([insight])
    assert "recurring_ocr_substitution" in open(path, encoding="utf-8").read()
