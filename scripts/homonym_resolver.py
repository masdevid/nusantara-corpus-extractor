"""
HomonymResolver: detects and resolves homonyms vs. variant spellings
in extracted dictionary entries. 🔀

This module provides:
- Homonym detection (same spelling, different meanings)
- Variant detection (same word, different OCR spellings)
- Merge/split decisions for duplicate headwords
- Conventions file updates for discovered homonym pairs

It does NOT make final decisions — it prepares evidence for the agent.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from difflib import SequenceMatcher

from models import DictionaryEntry, FlaggedTerm, IssueType

logger = logging.getLogger("indo_corpus_extractor.homonym_resolver")

# Levenshtein-like similarity threshold for variant detection
VARIANT_SIMILARITY_THRESHOLD = 0.85


class HomonymResolver:
    """Detects and classifies homonyms vs. variant spellings."""

    def __init__(
        self,
        similarity_threshold: float = VARIANT_SIMILARITY_THRESHOLD,
    ):
        """Initialize with configurable similarity threshold."""
        self.similarity_threshold = similarity_threshold

    def analyze(
        self,
        entries: list[DictionaryEntry],
    ) -> list[dict]:
        """Analyze entries for homonyms and variants.

        Returns a list of analysis results:
        [
            {
                "type": "polysemy" | "homonym" | "ocr_variant" | "dialect_variant",
                "headword": "bo",
                "entries": [entry1, entry2],
                "evidence": "Same spelling, different glosses...",
                "action": "merge_with_senses" | "keep_separate" | "merge_as_variant",
                "suggested_senses": ["sense 1", "sense 2"] or None,
            },
            ...
        ]
        """
        results = []

        # Group by headword (exact match)
        by_headword: dict[str, list[DictionaryEntry]] = defaultdict(list)
        for entry in entries:
            by_headword[entry.headword.lower()].append(entry)

        # Group by similarity (fuzzy match)
        all_headwords = list(by_headword.keys())
        similar_pairs = self._find_similar_pairs(all_headwords)

        # Analyze exact duplicates
        for hw, group in by_headword.items():
            if len(group) < 2:
                continue

            glosses = {e.gloss_pivot.lower().strip() for e in group}
            if len(glosses) <= 1:
                continue  # Same gloss, not a real duplicate

            # Classify: polysemy or homonym?
            classification = self._classify_by_glosses(group)
            results.append({
                **classification,
                "headword": hw,
                "entries": group,
            })

        # Analyze similar headwords
        for hw1, hw2, similarity in similar_pairs:
            group1 = by_headword.get(hw1, [])
            group2 = by_headword.get(hw2, [])
            if not group1 or not group2:
                continue

            all_entries = group1 + group2
            classification = self._classify_variant(
                hw1, hw2, group1, group2, similarity
            )
            results.append({
                **classification,
                "entries": all_entries,
            })

        logger.info(
            "🔀 Homonym analysis: %d findings from %d entries.",
            len(results), len(entries),
        )
        return results

    def check_conventions(
        self,
        entries: list[DictionaryEntry],
        known_homonyms: list[tuple[str, str]] | None = None,
    ) -> list[FlaggedTerm]:
        """Check if entries violate known homonym/variant conventions.

        Args:
            entries: All extracted entries
            known_homonyms: List of (word1, word2) pairs that are known
                homonyms in this language (from conventions file)
        """
        flags = []
        if not known_homonyms:
            return flags

        entries_by_hw: dict[str, list[DictionaryEntry]] = defaultdict(list)
        for entry in entries:
            entries_by_hw[entry.headword.lower()].append(entry)

        for hw1, hw2 in known_homonyms:
            group1 = entries_by_hw.get(hw1.lower(), [])
            group2 = entries_by_hw.get(hw2.lower(), [])

            if group1 and group2:
                # Both homonyms exist — check if they have different glosses
                glosses1 = {e.gloss_pivot for e in group1}
                glosses2 = {e.gloss_pivot for e in group2}
                if glosses1 == glosses2:
                    # Same glosses for homonyms — might be an error
                    for entry in group1 + group2:
                        flags.append(FlaggedTerm(
                            entry_id=entry.id,
                            headword=entry.headword,
                            issue_type=IssueType.MEANING_CONFLICT,
                            note=(
                                f"Known homonym pair ({hw1}/{hw2}) has "
                                f"identical glosses: {glosses1}. "
                                f"Are these really different words?"
                            ),
                            raised_at_pass=0,
                        ))

        return flags

    def as_conventions_section(
        self,
        analysis_results: list[dict],
    ) -> str:
        """Generate a homonyms/variants section for the conventions file."""
        lines = ["## Homonyms and Variants", ""]

        polysemy = [r for r in analysis_results if r["type"] == "polysemy"]
        homonyms = [r for r in analysis_results if r["type"] == "homonym"]
        ocr_variants = [r for r in analysis_results if r["type"] == "ocr_variant"]
        dialect_variants = [r for r in analysis_results if r["type"] == "dialect_variant"]

        if polysemy:
            lines.append("### Polysemy (same word, multiple senses)")
            for r in polysemy:
                senses = r.get("suggested_senses", [])
                if senses:
                    lines.append(f"- {r['headword']}: {'; '.join(senses)}")
                else:
                    glosses = [e.gloss_pivot for e in r["entries"][:3]]
                    lines.append(f"- {r['headword']}: {', '.join(glosses)}")
            lines.append("")

        if homonyms:
            lines.append("### Homonyms (different words, same spelling)")
            for r in homonyms:
                glosses = [e.gloss_pivot for e in r["entries"][:3]]
                lines.append(f"- {r['headword']}: {', '.join(glosses)}")
            lines.append("")

        if ocr_variants:
            lines.append("### OCR Variants (same word, different spelling)")
            for r in ocr_variants:
                hw_variants = list({e.headword for e in r["entries"]})
                lines.append(f"- {', '.join(hw_variants)} (keep: {hw_variants[0]})")
            lines.append("")

        if dialect_variants:
            lines.append("### Dialect Variants (regional spelling differences)")
            for r in dialect_variants:
                hw_variants = list({e.headword for e in r["entries"]})
                lines.append(
                    f"- {', '.join(hw_variants)} "
                    f"(cross-reference, keep both)"
                )
            lines.append("")

        return "\n".join(lines) + "\n"

    # -- internals -----------------------------------------------------

    def _find_similar_pairs(
        self, headwords: list[str]
    ) -> list[tuple[str, str, float]]:
        """Find pairs of headwords that are similar but not identical."""
        pairs = []
        seen = set()

        for i, hw1 in enumerate(headwords):
            for hw2 in headwords[i + 1:]:
                pair = tuple(sorted([hw1, hw2]))
                if pair in seen:
                    continue
                seen.add(pair)

                similarity = SequenceMatcher(None, hw1, hw2).ratio()
                if similarity >= self.similarity_threshold:
                    pairs.append((hw1, hw2, similarity))

        return pairs

    def _classify_by_glosses(
        self, group: list[DictionaryEntry]
    ) -> dict:
        """Classify a group of same-headword entries by their glosses."""
        glosses = [e.gloss_pivot.lower().strip() for e in group]

        # Check if glosses are related (share words)
        all_words = [set(g.split()) for g in glosses]
        if len(all_words) >= 2:
            overlap = all_words[0].intersection(*all_words[1:])
            if overlap and len(overlap) >= 2:
                # Glosses share significant vocabulary → polysemy
                return {
                    "type": "polysemy",
                    "evidence": (
                        f"Same headword, glosses share words: {overlap}. "
                        f"Glosses: {glosses}"
                    ),
                    "action": "merge_with_senses",
                    "suggested_senses": glosses,
                }

        # Glosses are different → homonym
        return {
            "type": "homonym",
            "evidence": f"Same headword, different glosses: {glosses}",
            "action": "keep_separate",
            "suggested_senses": None,
        }

    def _classify_variant(
        self,
        hw1: str,
        hw2: str,
        group1: list[DictionaryEntry],
        group2: list[DictionaryEntry],
        similarity: float,
    ) -> dict:
        """Classify a pair of similar headwords."""
        glosses1 = {e.gloss_pivot.lower().strip() for e in group1}
        glosses2 = {e.gloss_pivot.lower().strip() for e in group2}

        # If glosses are identical, it's likely an OCR variant
        if glosses1 == glosses2:
            return {
                "type": "ocr_variant",
                "headword": hw1,
                "evidence": (
                    f"Similar headwords ({hw1}/{hw2}, "
                    f"similarity={similarity:.2f}) with identical glosses. "
                    f"Likely OCR variant."
                ),
                "action": "merge_as_variant",
            }

        # If glosses are related, might be dialect variants
        overlap = glosses1.intersection(glosses2)
        if overlap:
            return {
                "type": "dialect_variant",
                "headword": hw1,
                "evidence": (
                    f"Similar headwords ({hw1}/{hw2}, "
                    f"similarity={similarity:.2f}) with shared glosses: "
                    f"{overlap}. Likely dialect variant."
                ),
                "action": "keep_separate",
            }

        # Different glosses entirely → separate words that happen to be similar
        return {
            "type": "homonym",
            "headword": hw1,
            "evidence": (
                f"Similar headwords ({hw1}/{hw2}, "
                f"similarity={similarity:.2f}) with different glosses. "
                f"Likely different words."
            ),
            "action": "keep_separate",
        }
