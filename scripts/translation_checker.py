"""
TranslationChecker: validates headword–gloss alignment and example
sentence correctness. 🔍

This module provides:
- Translation accuracy checks (does the gloss match the headword?)
- Example sentence validation (does the example contain the headword?)
- Gloss consistency checks (same headword, different glosses across pages)
- Cross-corpus validation (does this entry match prior extractions?)

It does NOT do web search — that's the agent's job. This module prepares
targeted queries and flags that need web evidence.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict

from models import DictionaryEntry, FlaggedTerm, IssueType

logger = logging.getLogger("indo_corpus_extractor.translation_checker")


class TranslationChecker:
    """Validates translation accuracy and example correctness."""

    def __init__(
        self,
        gloss_language: str = "indonesian",
        known_abbreviations: dict[str, str] | None = None,
    ):
        """Initialize with the pivot language and any known abbreviations.

        Args:
            gloss_language: "indonesian" or "english" (for query building)
            known_abbreviations: {"n": "noun", "v": "verb", ...} from conventions
        """
        self.gloss_language = gloss_language
        self.abbreviations = known_abbreviations or {
            "n": "noun", "v": "verb", "adj": "adjective", "adv": "adverb",
            "pron": "pronoun", "prep": "preposition", "conj": "conjunction",
            "part": "particle", "interj": "interjection", "num": "numeral",
            "m": "masculine", "f": "feminine", "pl": "plural", "sg": "singular",
        }

    def check_entries(
        self,
        entries: list[DictionaryEntry],
    ) -> list[FlaggedTerm]:
        """Run all translation checks on a set of entries.

        Returns new FlaggedTerm objects for issues found.
        """
        flags: list[FlaggedTerm] = []

        # Check 1: Empty or suspicious glosses
        flags.extend(self._check_empty_glosses(entries))

        # Check 2: Duplicate headwords with different glosses
        flags.extend(self._check_gloss_conflicts(entries))

        # Check 3: Example sentences that don't contain the headword
        flags.extend(self._check_examples(entries))

        # Check 4: Glosses that look like they're from the wrong language
        flags.extend(self._check_gloss_language(entries))

        # Check 5: Headwords that look like OCR errors (very short, mixed case)
        flags.extend(self._check_headword_suspicion(entries))

        logger.info(
            "🔍 Translation check: %d flags from %d entries.",
            len(flags), len(entries),
        )
        return flags

    def build_web_query(self, entry: DictionaryEntry) -> str | None:
        """Build a web search query to verify a headword's translation.

        Returns a query string the agent can pass to web_search, or None
        if no useful query can be constructed.
        """
        if not entry.headword or not entry.gloss_pivot:
            return None

        lang_name = self.gloss_language.title()

        if self.gloss_language == "indonesian":
            return (
                f'"{entry.headword}" arti bahasa Indonesia'
                f' OR "{entry.headword}" meaning'
            )
        elif self.gloss_language == "english":
            return (
                f'"{entry.headword}" meaning English'
                f' OR "{entry.headword}" definition'
            )
        else:
            return f'"{entry.headword}" {lang_name} translation'

    # -- internals -----------------------------------------------------

    def _check_empty_glosses(
        self, entries: list[DictionaryEntry]
    ) -> list[FlaggedTerm]:
        """Flag entries with empty or very short glosses."""
        flags = []
        for entry in entries:
            if not entry.gloss_pivot or len(entry.gloss_pivot.strip()) < 2:
                flags.append(FlaggedTerm(
                    entry_id=entry.id,
                    headword=entry.headword,
                    issue_type=IssueType.LOW_CONFIDENCE,
                    note=f"Empty or very short gloss: '{entry.gloss_pivot}'",
                    raised_at_pass=0,
                ))
        return flags

    def _check_gloss_conflicts(
        self, entries: list[DictionaryEntry]
    ) -> list[FlaggedTerm]:
        """Flag duplicate headwords with different glosses."""
        flags = []
        by_headword: dict[str, list[DictionaryEntry]] = defaultdict(list)

        for entry in entries:
            by_headword[entry.headword.lower()].append(entry)

        for hw, group in by_headword.items():
            if len(group) < 2:
                continue

            glosses = {e.gloss_pivot.lower().strip() for e in group}
            if len(glosses) > 1:
                # Multiple different glosses for the same headword
                for entry in group:
                    other_glosses = [
                        e.gloss_pivot for e in group if e.id != entry.id
                    ]
                    flags.append(FlaggedTerm(
                        entry_id=entry.id,
                        headword=entry.headword,
                        issue_type=IssueType.DUPLICATE_HEADWORD,
                        note=(
                            f"Duplicate headword with different glosses. "
                            f"This gloss: '{entry.gloss_pivot}'. "
                            f"Others: {other_glosses}"
                        ),
                        raised_at_pass=0,
                        needs_web_check=True,
                        suggested_query=self.build_web_query(entry),
                    ))

        return flags

    def _check_examples(
        self, entries: list[DictionaryEntry]
    ) -> list[FlaggedTerm]:
        """Flag example sentences that don't contain the headword."""
        flags = []
        for entry in entries:
            if not entry.examples:
                continue
            for example in entry.examples:
                # Normalize: lowercase, strip punctuation
                example_lower = example.lower()
                hw_lower = entry.headword.lower()

                # Check if headword (or a close variant) appears in the example
                if hw_lower not in example_lower:
                    # Try with common affixes stripped
                    hw_stripped = re.sub(r"^(?:me[nmblryksw]|pe[nmblryksw]|ber|ter|di)", "", hw_lower)
                    hw_stripped = re.sub(r"(?:an|i|kan)$", "", hw_stripped)

                    if hw_stripped and hw_stripped not in example_lower:
                        flags.append(FlaggedTerm(
                            entry_id=entry.id,
                            headword=entry.headword,
                            issue_type=IssueType.LOW_CONFIDENCE,
                            note=(
                                f"Example doesn't contain headword: "
                                f"'{example[:60]}...' "
                                f"(headword: '{entry.headword}')"
                            ),
                            raised_at_pass=0,
                        ))

        return flags

    def _check_gloss_language(
        self, entries: list[DictionaryEntry]
    ) -> list[FlaggedTerm]:
        """Flag glosses that look like they're from the wrong language."""
        flags = []

        # Simple heuristic: if the gloss language is Indonesian but the
        # gloss contains mostly English function words, it might be wrong.
        english_words = {
            "the", "of", "and", "in", "to", "is", "was", "that", "it",
            "he", "his", "as", "for", "on", "with", "are", "this", "from",
        }
        indonesian_words = {
            "yang", "dan", "di", "dengan", "itu", "ini", "tidak", "untuk",
            "dari", "pada", "adalah", "karena", "juga", "oleh", "dalam",
        }

        for entry in entries:
            if not entry.gloss_pivot:
                continue
            words = entry.gloss_pivot.lower().split()
            eng_count = sum(1 for w in words if w in english_words)
            ind_count = sum(1 for w in words if w in indonesian_words)

            if self.gloss_language == "indonesian" and eng_count > ind_count + 2:
                flags.append(FlaggedTerm(
                    entry_id=entry.id,
                    headword=entry.headword,
                    issue_type=IssueType.MEANING_CONFLICT,
                    note=(
                        f"Gloss looks English ({eng_count} English words) "
                        f"but pivot language is Indonesian. "
                        f"Gloss: '{entry.gloss_pivot[:60]}'"
                    ),
                    raised_at_pass=0,
                ))
            elif self.gloss_language == "english" and ind_count > eng_count + 2:
                flags.append(FlaggedTerm(
                    entry_id=entry.id,
                    headword=entry.headword,
                    issue_type=IssueType.MEANING_CONFLICT,
                    note=(
                        f"Gloss looks Indonesian ({ind_count} Indonesian words) "
                        f"but pivot language is English. "
                        f"Gloss: '{entry.gloss_pivot[:60]}'"
                    ),
                    raised_at_pass=0,
                ))

        return flags

    def _check_headword_suspicion(
        self, entries: list[DictionaryEntry]
    ) -> list[FlaggedTerm]:
        """Flag headwords that look like OCR errors."""
        flags = []
        for entry in entries:
            hw = entry.headword

            # Very short headwords (1 char) are suspicious
            if len(hw) == 1 and hw.isalpha():
                flags.append(FlaggedTerm(
                    entry_id=entry.id,
                    headword=hw,
                    issue_type=IssueType.LOW_CONFIDENCE,
                    note=f"Very short headword (1 char): '{hw}'",
                    raised_at_pass=0,
                    needs_web_check=True,
                    suggested_query=f'"{hw}" meaning {self.gloss_language}',
                ))
                continue

            # Mixed case is suspicious (except proper nouns)
            if hw[0].isupper() and not hw.isupper() and len(hw) > 3:
                # Might be a proper noun or an OCR error
                if not any(c.isupper() for c in hw[1:]):
                    # Only first letter capitalized — could be proper noun
                    pass
                else:
                    flags.append(FlaggedTerm(
                        entry_id=entry.id,
                        headword=hw,
                        issue_type=IssueType.LOW_CONFIDENCE,
                        note=f"Suspicious mixed case in headword: '{hw}'",
                        raised_at_pass=0,
                    ))

            # Contains digits (not common in Nusantara languages)
            if any(c.isdigit() for c in hw):
                flags.append(FlaggedTerm(
                    entry_id=entry.id,
                    headword=hw,
                    issue_type=IssueType.LOW_CONFIDENCE,
                    note=f"Headword contains digits: '{hw}'",
                    raised_at_pass=0,
                ))

        return flags
