"""
Domain model for the Indo Corpus Extraction pipeline. 📚

Everything downstream (parser, extractor, corrector, crosschecker, pattern
spotter, web verifier, writer) operates on these types. Keep this file the
single source of truth for "what is a dictionary entry" — no module should
reinvent its own shape.

Nothing in here assumes a specific language pair. `Language.pivot_code` /
`pivot_name` are just "the other language this dictionary glosses into" —
Bahasa Indonesia for Biak/Sentani/Lani by default in the CLI, but could be
anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class Script(str, Enum):
    LATIN = "latin"
    LATIN_DIACRITIC = "latin_diacritic"
    OTHER = "other"


@dataclass(frozen=True)
class Language:
    """Config for one local language. Add a new language by instantiating
    one of these — nothing else in the pipeline should need to change.

    pivot_code / pivot_name describe whatever language this dictionary
    glosses into (Bahasa Indonesia for the current Papuan-language work, but
    could be English, Malay, French — anything). The CLI supplies Bahasa
    Indonesia by default, while explicit values keep this model language-
    agnostic.
    """

    code: str                 # e.g. "lni" (Lani), "bhw" (Biak), "shj" (Sentani)
    name: str                 # e.g. "Lani"
    family: str               # e.g. "Trans-New Guinea"
    pivot_code: str           # tesseract-style OCR lang code for the gloss language
    pivot_name: str           # display name, e.g. "Bahasa Indonesia"
    script: Script = Script.LATIN_DIACRITIC


class IssueType(str, Enum):
    OCR_TYPO = "ocr_typo"
    LOW_CONFIDENCE = "low_confidence"
    MEANING_CONFLICT = "meaning_conflict"
    DUPLICATE_HEADWORD = "duplicate_headword"
    BAD_PAGE = "bad_page"


@dataclass
class RawPage:
    """One page's worth of extracted text, before entry parsing."""

    page_number: int
    text: str
    was_ocr: bool                      # True if this page needed OCR (image-PDF)
    ocr_confidence: Optional[float] = None   # None if digital text (no OCR needed)


@dataclass
class DictionaryEntry:
    """One dictionary entry: local-language headword ⇄ pivot-language gloss."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    headword: str = ""
    part_of_speech: Optional[str] = None
    gloss_pivot: str = ""              # gloss in whatever the pivot language is
    examples: list[str] = field(default_factory=list)
    page_ref: Optional[int] = None
    confidence: float = 1.0            # 1.0 = digital text, degrades with OCR/edits
    source_language: str = ""          # Language.code

    def as_corpus_row(self) -> dict:
        return {
            "id": self.id,
            "headword": self.headword,
            "pos": self.part_of_speech,
            "gloss_pivot": self.gloss_pivot,
            "examples": self.examples,
            "page_ref": self.page_ref,
            "confidence": round(self.confidence, 3),
            "source_language": self.source_language,
        }


@dataclass
class FlaggedTerm:
    """A thing the loop couldn't resolve on its own — needs a human (or a
    web search) to weigh in. 🚩"""

    entry_id: str
    headword: str
    issue_type: IssueType
    note: str
    raised_at_pass: int
    resolved: bool = False
    resolution_note: Optional[str] = None
    # Pattern-spotting support: the raw (original, attempted-fix) pair, so
    # PatternSpotter can look for recurring substitutions across many flags
    # instead of judging each one in isolation.
    attempted_fix: Optional[tuple[str, str]] = None
    # Web-verification support: set by the loop when a flag looks like the
    # kind of thing a quick search could actually help with. The pipeline
    # never searches on its own (no general internet access from the
    # sandboxed scripts) — this just prepares the query for the agent
    # (which has web_search) to run and record evidence for.
    needs_web_check: bool = False
    suggested_query: Optional[str] = None
    web_evidence: Optional[str] = None
    web_sources: list[str] = field(default_factory=list)

    def as_markdown_row(self) -> str:
        if self.resolved and self.web_evidence:
            status = "🌐 resolved (web)"
        elif self.resolved:
            status = "✅ resolved"
        elif self.needs_web_check:
            status = "🚩🌐 open — web check suggested"
        else:
            status = "🚩 open"
        return (
            f"| `{self.entry_id}` | {self.headword} | {self.issue_type.value} "
            f"| {self.note} | pass {self.raised_at_pass} | {status} |"
        )


@dataclass
class PatternInsight:
    """A systematic issue spotted across multiple flags — smarter than
    reviewing flags one at a time. See scripts/pattern_spotter.py."""

    pattern_type: str          # e.g. "recurring_ocr_substitution", "bad_page_cluster"
    description: str
    affected_entry_ids: list[str]
    suggested_action: str
    confidence: float = 0.0    # how sure the spotter is this is a real pattern (0-1)

    def as_markdown(self) -> str:
        return (
            f"### {self.pattern_type} (confidence {self.confidence:.2f})\n\n"
            f"{self.description}\n\n"
            f"**Suggested action:** {self.suggested_action}\n\n"
            f"Affects {len(self.affected_entry_ids)} entries: "
            f"{', '.join(self.affected_entry_ids[:10])}"
            f"{' ...' if len(self.affected_entry_ids) > 10 else ''}\n"
        )


@dataclass
class QualityReport:
    """Stats for a single pass of the loop."""

    pass_number: int
    entries_in: int
    entries_out: int
    typo_fixes_applied: int
    flags_raised: int
    flags_resolved: int
    converged: bool
    patterns_spotted: int = 0
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def as_markdown(self) -> str:
        return (
            f"# Quality Report — Pass {self.pass_number}\n\n"
            f"- Generated: {self.generated_at.isoformat()}Z\n"
            f"- Entries in / out: {self.entries_in} / {self.entries_out}\n"
            f"- Typo fixes applied: {self.typo_fixes_applied}\n"
            f"- Flags raised this pass: {self.flags_raised}\n"
            f"- Flags resolved this pass: {self.flags_resolved}\n"
            f"- Patterns spotted this pass: {self.patterns_spotted}\n"
            f"- Converged: {'yes 🎉' if self.converged else 'no — another pass needed'}\n"
        )


@dataclass
class ExtractionSession:
    """The full checkpointable state of one language's extraction run."""

    language: Language
    source_pdf: str
    entries: list[DictionaryEntry] = field(default_factory=list)
    flagged_terms: list[FlaggedTerm] = field(default_factory=list)
    patterns: list[PatternInsight] = field(default_factory=list)
    reports: list[QualityReport] = field(default_factory=list)
    current_pass: int = 0

    def open_flags(self) -> list[FlaggedTerm]:
        return [f for f in self.flagged_terms if not f.resolved]

    def flags_needing_web_check(self) -> list[FlaggedTerm]:
        return [f for f in self.flagged_terms if not f.resolved and f.needs_web_check]

    def entries_by_headword(self) -> dict[str, list[DictionaryEntry]]:
        buckets: dict[str, list[DictionaryEntry]] = {}
        for e in self.entries:
            buckets.setdefault(e.headword, []).append(e)
        return buckets
