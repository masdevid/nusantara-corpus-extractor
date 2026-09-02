import re

from typo_corrector import (
    CONFIDENCE_FLOOR,
    PhonologyReference,
    TypoCorrector,
)
from models import IssueType


def _phonology(**kwargs):
    defaults = dict(
        valid_chars=set("abdefghijklmnoprstuvwy'"),
        confusion_pairs={"rn": "m", "1": "l"},
        digital_text_trusted=True,
    )
    defaults.update(kwargs)
    return PhonologyReference(**defaults)


def test_phonology_from_markdown(tmp_path):
    md = tmp_path / "sentani_phonology.md"
    md.write_text(
        "## Valid characters\n\na b c d e f\n\n"
        "## OCR confusion pairs\n- `rn` → `m`\n- `1` → `l`\n\n"
        "## Digital text layer\n- trusted: no\n\n"
        "## Entry splitting\n- split_before: `(?<=\\s)(?=a\\s)`\n\n"
        "## Entry pattern\n- pattern: `^(?P<headword>\\w+)\\s*(?P<gloss>.+)$`\n\n"
        "## Headword shape\n- pattern: `^[a-z]+$`\n",
        encoding="utf-8",
    )
    phon = PhonologyReference.from_markdown(str(md))
    assert phon.valid_chars == set("abcdef")
    assert phon.confusion_pairs == {"rn": "m", "1": "l"}
    assert phon.digital_text_trusted is False
    assert phon.entry_split is not None
    assert phon.entry_pattern is not None
    assert phon.headword_shape is not None


def test_phonology_from_markdown_defaults(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("## Valid characters\n\na b c\n", encoding="utf-8")
    phon = PhonologyReference.from_markdown(str(md))
    assert phon.digital_text_trusted is True
    assert phon.entry_split is None
    assert phon.entry_pattern is None
    assert phon.headword_shape is None


def test_correct_trusted_digital_skipped(make_entry):
    phon = _phonology(digital_text_trusted=True)
    corrector = TypoCorrector(phon, pass_number=1)
    entries = [make_entry(headword="rnendengar", confidence=1.0)]
    out, flags = corrector.correct(entries)
    assert out[0].headword == "rnendengar"  # untouched
    assert flags == []


def test_correct_applies_confusion_fix(make_entry):
    phon = _phonology(digital_text_trusted=False)
    corrector = TypoCorrector(phon, pass_number=1)
    entries = [make_entry(headword="rnendengar", confidence=0.9)]
    out, flags = corrector.correct(entries)
    assert out[0].headword == "mendengar"
    assert out[0].confidence < 0.9
    assert corrector.last_fixes_applied == 1


def test_correct_flags_invalid_orthography(make_entry):
    phon = _phonology(digital_text_trusted=False)
    corrector = TypoCorrector(phon, pass_number=1)
    # 'q' and 'x' not in valid_chars -> candidate invalid
    entries = [make_entry(headword="rnqex", confidence=0.9)]
    out, flags = corrector.correct(entries)
    assert out[0].headword == "rnqex"  # unchanged
    assert len(flags) == 1
    assert flags[0].issue_type == IssueType.OCR_TYPO
    assert flags[0].attempted_fix == ("rnqex", "mqex")


def test_correct_skips_non_headword_shape(make_entry):
    phon = _phonology(digital_text_trusted=False,
                      headword_shape=re.compile(r"^[a-z]+$"))
    corrector = TypoCorrector(phon, pass_number=1)
    entries = [make_entry(headword="Abaele", confidence=0.9)]
    out, flags = corrector.correct(entries)
    assert out[0].headword == "Abaele"  # not "fixed"
    assert flags == []


def test_correct_low_confidence_flag(make_entry):
    phon = _phonology(digital_text_trusted=False)
    corrector = TypoCorrector(phon, pass_number=2)
    entries = [make_entry(headword="abara", confidence=0.5)]
    out, flags = corrector.correct(entries)
    assert any(f.issue_type == IssueType.LOW_CONFIDENCE for f in flags)
    assert any(f.needs_web_check for f in flags)


def test_correct_low_confidence_first_pass_no_web(make_entry):
    phon = _phonology(digital_text_trusted=False)
    corrector = TypoCorrector(phon, pass_number=1)
    entries = [make_entry(headword="abara", confidence=0.5)]
    out, flags = corrector.correct(entries)
    low = [f for f in flags if f.issue_type == IssueType.LOW_CONFIDENCE]
    assert low and not low[0].needs_web_check
