"""
TypoCorrector: OCR-confusion-aware + orthography-aware correction pass. 🩹

Two tiers:
  1. Confident auto-fix — a known OCR confusion pair (e.g. "rn"→"m",
     "l"→"1"→"I") that, once swapped, matches the language's declared
     orthography. Applied in place, confidence nudged down slightly to
     record that it was touched.
  2. Ambiguous → FlaggedTerm. Never silently guessed.

Confusion pairs + orthography rules live in the language's phonology
reference file (see references/phonology_template.md), not hardcoded here,
so this module works unchanged for Biak, Sentani, Lani, or the next one.
"""

from __future__ import annotations

import logging
import re

from models import DictionaryEntry, FlaggedTerm, IssueType

logger = logging.getLogger("indo_corpus_extractor.typo_corrector")

CONFIDENCE_FLOOR = 0.75  # below this, always flag rather than auto-fix
CONFIDENCE_PENALTY_PER_FIX = 0.03


class PhonologyReference:
    """Parsed view of a `<language>_phonology.md` file."""

    def __init__(
        self,
        valid_chars: set[str],
        confusion_pairs: dict[str, str],
        digital_text_trusted: bool = True,
        entry_split: re.Pattern | None = None,
        entry_pattern: re.Pattern | None = None,
        headword_shape: re.Pattern | None = None,
    ) -> None:
        self.valid_chars = valid_chars
        self.confusion_pairs = confusion_pairs  # e.g. {"rn": "m", "1": "l"}
        # Some "digital" PDFs carry an OCR-derived text layer of publisher
        # scans — noisy even though no tesseract runs. Declare those
        # untrusted (`## Digital text layer` → `- trusted: no`) so the
        # correction pass still applies to them.
        self.digital_text_trusted = digital_text_trusted
        # Optional per-dictionary layout config (see phonology_template.md):
        # entry_split splits page text into entry chunks; entry_pattern
        # overrides the default headword/gloss matcher.
        self.entry_split = entry_split
        self.entry_pattern = entry_pattern
        # Optional shape a headword must match to be correction-eligible —
        # keeps e.g. `rn`→`m` from "fixing" English prose like Government.
        self.headword_shape = headword_shape

    @classmethod
    def from_markdown(cls, path: str) -> "PhonologyReference":
        text = open(path, encoding="utf-8").read()

        chars_section = re.search(
            r"## Valid characters\n(.+?)\n##", text, re.S
        )
        valid_chars = set()
        if chars_section:
            valid_chars = {c for c in chars_section.group(1) if not c.isspace()}

        pairs_section = re.search(
            r"## OCR confusion pairs\n(.+?)(\n##|\Z)", text, re.S
        )
        confusion_pairs: dict[str, str] = {}
        if pairs_section:
            for line in pairs_section.group(1).splitlines():
                m = re.match(r"\s*-\s*`(.+?)`\s*→\s*`(.+?)`", line)
                if m:
                    confusion_pairs[m.group(1)] = m.group(2)

        trusted = True
        trusted_section = re.search(
            r"## Digital text layer\n(.+?)(\n##|\Z)", text, re.S
        )
        if trusted_section and re.search(r"trusted:\s*no", trusted_section.group(1)):
            trusted = False

        entry_split = cls._parse_pattern_setting(text, "## Entry splitting", "split_before")
        entry_pattern = cls._parse_pattern_setting(text, "## Entry pattern", "pattern")
        headword_shape = cls._parse_pattern_setting(
            text, "## Headword shape", "pattern"
        )

        return cls(
            valid_chars=valid_chars,
            confusion_pairs=confusion_pairs,
            digital_text_trusted=trusted,
            entry_split=entry_split,
            entry_pattern=entry_pattern,
            headword_shape=headword_shape,
        )

    @staticmethod
    def _parse_pattern_setting(text: str, section_header: str, key: str) -> re.Pattern | None:
        """Reads ``key: `regex``` from a section and compiles it. A bad or
        missing regex is logged and ignored — layout config is optional."""
        section = re.search(re.escape(section_header) + r"\n(.+?)(\n##|\Z)", text, re.S)
        if not section:
            return None
        for line in section.group(1).splitlines():
            m = re.match(r"\s*-\s*" + re.escape(key) + r":\s*`(.+?)`\s*$", line)
            if m:
                try:
                    return re.compile(m.group(1))
                except re.error as exc:
                    logger.warning(
                        "⚠️ Invalid regex in '%s' (%s): %s — ignoring.",
                        section_header, key, exc,
                    )
                return None
        return None


class TypoCorrector:
    def __init__(self, phonology: PhonologyReference, pass_number: int) -> None:
        self.phonology = phonology
        self.pass_number = pass_number
        self.last_fixes_applied = 0

    def correct(
        self, entries: list[DictionaryEntry]
    ) -> tuple[list[DictionaryEntry], list[FlaggedTerm]]:
        flags: list[FlaggedTerm] = []
        fixes_applied = 0

        for entry in entries:
            if entry.confidence >= 1.0 and self.phonology.digital_text_trusted:
                continue  # trusted digital text, untouched — nothing to correct

            if (
                self.phonology.headword_shape is not None
                and not self.phonology.headword_shape.match(entry.headword)
            ):
                continue  # not this language's word shape — don't "fix" it

            original = entry.headword
            candidate = self._apply_confusion_fixes(original)

            if candidate != original:
                if self._is_valid_orthography(candidate):
                    logger.info("🩹 Fixed headword '%s' → '%s'", original, candidate)
                    entry.headword = candidate
                    entry.confidence = max(
                        0.0, entry.confidence - CONFIDENCE_PENALTY_PER_FIX
                    )
                    fixes_applied += 1
                else:
                    flags.append(self._flag(entry, original, candidate))

            if entry.confidence < CONFIDENCE_FLOOR:
                # Web-check is worth suggesting once we're past pass 1 — on
                # the first pass this might just be a noisy scan that a
                # later correction pass clears up on its own; if it's still
                # low-confidence on a later pass, a quick search is more
                # useful than staring at the same OCR guess again.
                stuck = self.pass_number > 1
                flags.append(
                    FlaggedTerm(
                        entry_id=entry.id,
                        headword=entry.headword,
                        issue_type=IssueType.LOW_CONFIDENCE,
                        note=(
                            f"Confidence {entry.confidence:.2f} is below the "
                            f"{CONFIDENCE_FLOOR} floor — needs a human read."
                            + (" Stuck across multiple passes." if stuck else "")
                        ),
                        raised_at_pass=self.pass_number,
                        needs_web_check=stuck,
                        suggested_query=(
                            f'"{entry.headword}" meaning definition'
                            if stuck else None
                        ),
                    )
                )

        logger.info(
            "🩹 Typo pass %d: %d auto-fixes applied, %d flags raised.",
            self.pass_number, fixes_applied, len(flags),
        )
        self.last_fixes_applied = fixes_applied
        return entries, flags

    # -- internals -----------------------------------------------------

    def _apply_confusion_fixes(self, headword: str) -> str:
        candidate = headword
        for bad, good in self.phonology.confusion_pairs.items():
            candidate = candidate.replace(bad, good)
        return candidate

    def _is_valid_orthography(self, word: str) -> bool:
        if not self.phonology.valid_chars:
            return True  # no reference loaded — don't block on an empty rule set
        return all(c in self.phonology.valid_chars for c in word.lower())

    def _flag(self, entry: DictionaryEntry, original: str, candidate: str) -> FlaggedTerm:
        return FlaggedTerm(
            entry_id=entry.id,
            headword=original,
            issue_type=IssueType.OCR_TYPO,
            note=(
                f"Confusion-pair fix produced '{candidate}', which still isn't "
                f"valid orthography for this language — needs a human read."
            ),
            raised_at_pass=self.pass_number,
            # Recorded (not just noted) so PatternSpotter can look for this
            # exact substitution recurring across many entries — a single
            # bad fix is noise, the same bad fix on 8 entries is a pattern.
            attempted_fix=(original, candidate),
        )
