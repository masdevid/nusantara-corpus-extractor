"""
MeaningCrossChecker: sanity-checks glosses against the existing corpus and
flags duplicate headwords whose meanings diverge. 🔎🤝

This module deliberately does NOT try to be clever about semantics — no
embeddings, no fuzzy similarity scoring baked in by default. Two things it
CAN say with confidence:
  1. "This headword already exists in the corpus with a different gloss" —
     mechanical, exact-ish comparison.
  2. "This headword appears twice in THIS extraction pass with different
     glosses" — same mechanism, within-session.
Anything genuinely semantic (is gloss A a plausible paraphrase of gloss B?)
gets flagged for a human — or, when it looks worth the round-trip, for a
quick web check (see needs_web_check / suggested_query on the flag).
"""

from __future__ import annotations

import logging

from models import DictionaryEntry, FlaggedTerm, IssueType, Language

logger = logging.getLogger("indo_corpus_extractor.meaning_crosscheck")


class MeaningCrossChecker:
    def __init__(self, pass_number: int, language: Language) -> None:
        self.pass_number = pass_number
        self.language = language

    def crosscheck(
        self,
        entries: list[DictionaryEntry],
        existing_corpus: list[DictionaryEntry] | None = None,
    ) -> list[FlaggedTerm]:
        flags: list[FlaggedTerm] = []
        existing_by_headword = self._index_by_headword(existing_corpus or [])
        seen_this_pass: dict[str, DictionaryEntry] = {}

        for entry in entries:
            key = entry.headword.strip().lower()

            # within-pass duplicate check
            prior = seen_this_pass.get(key)
            if prior and not self._glosses_agree(prior.gloss_pivot, entry.gloss_pivot):
                flags.append(
                    FlaggedTerm(
                        entry_id=entry.id,
                        headword=entry.headword,
                        issue_type=IssueType.DUPLICATE_HEADWORD,
                        note=(
                            f"Appears twice in this pass with different glosses: "
                            f"'{prior.gloss_pivot}' vs '{entry.gloss_pivot}' — same "
                            f"word, different sense, or one's an OCR misread?"
                        ),
                        raised_at_pass=self.pass_number,
                        needs_web_check=True,
                        suggested_query=self._duplicate_query(
                            entry.headword, prior.gloss_pivot, entry.gloss_pivot
                        ),
                    )
                )
            seen_this_pass[key] = entry

            # cross-check against prior corpus
            prior_entries = existing_by_headword.get(key, [])
            for prior_entry in prior_entries:
                if not self._glosses_agree(prior_entry.gloss_pivot, entry.gloss_pivot):
                    flags.append(
                        FlaggedTerm(
                            entry_id=entry.id,
                            headword=entry.headword,
                            issue_type=IssueType.MEANING_CONFLICT,
                            note=(
                                f"Existing corpus has '{entry.headword}' → "
                                f"'{prior_entry.gloss_pivot}', this pass extracted "
                                f"'{entry.gloss_pivot}' — confirm whether this is a "
                                f"genuine polysemy or one of the two is wrong."
                            ),
                            raised_at_pass=self.pass_number,
                            needs_web_check=True,
                            suggested_query=self._conflict_query(
                                entry.headword, prior_entry.gloss_pivot, entry.gloss_pivot
                            ),
                        )
                    )

        logger.info(
            "🔎 Cross-check pass %d: %d meaning-related flags raised (%d marked "
            "for optional web verification).",
            self.pass_number, len(flags), sum(1 for f in flags if f.needs_web_check),
        )
        return flags

    # -- internals -----------------------------------------------------

    def _index_by_headword(
        self, corpus: list[DictionaryEntry]
    ) -> dict[str, list[DictionaryEntry]]:
        index: dict[str, list[DictionaryEntry]] = {}
        for entry in corpus:
            index.setdefault(entry.headword.strip().lower(), []).append(entry)
        return index

    def _glosses_agree(self, gloss_a: str, gloss_b: str) -> bool:
        """Deliberately conservative: normalized exact match only. Anything
        looser than this belongs in a human's (or a web search's) judgment,
        not a heuristic."""
        norm = lambda s: s.strip().lower().rstrip(".")
        return norm(gloss_a) == norm(gloss_b)

    def _conflict_query(self, headword: str, gloss_a: str, gloss_b: str) -> str:
        return (
            f'"{headword}" {self.language.name} language meaning '
            f'("{gloss_a}" OR "{gloss_b}" in {self.language.pivot_name})'
        )

    def _duplicate_query(self, headword: str, gloss_a: str, gloss_b: str) -> str:
        return (
            f'"{headword}" {self.language.name} dictionary — does it mean '
            f'"{gloss_a}" or "{gloss_b}" ({self.language.pivot_name})?'
        )
