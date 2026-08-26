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
class BookProfile:
    """What the profiler learned about THIS book before extraction runs.
    🔍

    Not every source looks like a standard headword–gloss dictionary:
    kids' picture books, morphology/grammar booklets, and dictionaries
    with long front-matter guides all need different handling. The
    profile records the book kind, its page zones, the entry conventions
    it detected, and suggested phonology-ref settings — so extraction is
    driven by what the book actually is, not by an assumed format.
    """

    book_kind: str = "unknown"        # dictionary | kids_picture_book | grammar_morphology | mixed | unknown
    front_matter_pages: list[int] = field(default_factory=list)
    body_pages: list[int] = field(default_factory=list)
    back_matter_pages: list[int] = field(default_factory=list)
    unreadable_pages: list[int] = field(default_factory=list)
    conventions: dict = field(default_factory=dict)   # markers, gloss mix, densities
    suggested_settings: list[str] = field(default_factory=list)  # ready-to-paste phonology lines
    notes: list[str] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = [
            "# Book Profile 🔍",
            "",
            f"Detected before extraction — check these findings against the",
            f"actual pages before trusting them.",
            "",
            f"**Book kind:** {self.book_kind}",
            "",
            "## Page zones",
            "",
        ]
        def _rng(pages: list[int]) -> str:
            if not pages:
                return "_none_"
            return f"{len(pages)} pages ({pages[0]}–{pages[-1]})" if len(pages) > 1 else f"page {pages[0]}"
        lines += [
            f"- Front matter: {_rng(self.front_matter_pages)} — guides/preface, skipped for entry extraction",
            f"- Body: {_rng(self.body_pages)}",
            f"- Back matter: {_rng(self.back_matter_pages)}",
            f"- Unreadable (bad scans): {', '.join(map(str, self.unreadable_pages)) or '_none_'}",
            "",
            "## Conventions detected",
            "",
        ]
        for k, v in self.conventions.items():
            lines.append(f"- {k}: {v}")
        if self.suggested_settings:
            lines += ["", "## Suggested phonology-ref settings", ""]
            lines += [f"- `{s}`" for s in self.suggested_settings]
        if self.notes:
            lines += ["", "## Notes", ""]
            lines += [f"- {n}" for n in self.notes]
        return "\n".join(lines) + "\n"


@dataclass
class ExtractionSession:
    """The full checkpointable state of one language's extraction run."""

    language: Language
    source_pdf: str
    entries: list[DictionaryEntry] = field(default_factory=list)
    flagged_terms: list[FlaggedTerm] = field(default_factory=list)
    patterns: list[PatternInsight] = field(default_factory=list)
    reports: list[QualityReport] = field(default_factory=list)
    profile: Optional[BookProfile] = None
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
