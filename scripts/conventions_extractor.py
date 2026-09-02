"""
ConventionsExtractor: analyzes dictionary pages and extracts entry
conventions, headword shapes, gloss patterns, and cross-reference
markers. 📐

This module does NOT do web search or linguistic judgment — it does
structural analysis: "what patterns exist in this text?" The agent
(decision about what to trust) and the conventions file (persistent
memory) handle the rest.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from models import RawPage, BookProfile

logger = logging.getLogger("indo_corpus_extractor.conventions_extractor")

# Common cross-reference markers in Nusantara dictionaries
CROSS_REF_PATTERNS = {
    "KS": re.compile(r"\bKS\s*:", re.I),
    "lht_jg": re.compile(r"\blht\s+jg\s*:", re.I),
    "cf": re.compile(r"\b(?:cf|compare)\s*:", re.I),
    "see_also": re.compile(r"\bsee\s+also\s*:", re.I),
    "lit": re.compile(r"\blit\s*:", re.I),
}

# POS codes commonly found in dictionaries
POS_CODES = re.compile(
    r"(?<![A-Za-z])(?:n|v|adj|adv|num|pron|prep|conj|part|interj|m|f|pl|sg)\.?\s",
    re.I,
)

# Dotted aspect markers (Sentani-specific, but common in Papuan dicts)
DOTTED_MARKER = re.compile(r"[•·.]{1,4}")

# Parenthetical variants: (variant), (pl), (dim), etc.
PAREN_VARIANT = re.compile(r"\([a-zà-ÿ''\-]{2,}\)")

# Multi-sense markers
SENSE_MARKERS = re.compile(r"(?:^|\s)(\d+)[.)]\s", re.M)

# Numbered entries (teaching books, vocabulary lists)
NUMBERED_ENTRY = re.compile(r"^\s*\d{1,4}\.\s+", re.M)


class ConventionsExtractor:
    """Extracts structural conventions from dictionary pages."""

    def extract(
        self,
        pages: list[RawPage],
        profile: BookProfile | None = None,
    ) -> dict:
        """Analyzes pages and returns a conventions dict.

        The conventions dict has keys:
        - entry_split_mode: "line" | "marker" | "hybrid"
        - headword_patterns: list of detected headword shapes
        - gloss_languages: list of detected gloss languages
        - cross_refs: dict of marker → count
        - pos_codes: list of detected POS codes
        - dotted_markers: bool (whether the book uses dotted markers)
        - multi_sense: bool (whether entries have numbered senses)
        - morphology_hints: list of detected affix patterns
        - abbreviations: dict of abbreviation → expansion (if detected)
        """
        conventions: dict = {}

        # Analyze entry splitting
        conventions["entry_split_mode"] = self._detect_split_mode(pages)

        # Analyze headword patterns
        conventions["headword_patterns"] = self._detect_headword_patterns(pages)

        # Analyze gloss languages
        conventions["gloss_languages"] = self._detect_gloss_languages(pages)

        # Detect cross-reference markers
        conventions["cross_refs"] = self._detect_cross_refs(pages)

        # Detect POS codes
        conventions["pos_codes"] = self._detect_pos_codes(pages)

        # Detect dotted markers
        conventions["dotted_markers"] = self._has_dotted_markers(pages)

        # Detect multi-sense markers
        conventions["multi_sense"] = self._has_multi_sense(pages)

        # Detect morphology hints
        conventions["morphology_hints"] = self._detect_morphology_hints(pages)

        logger.info(
            "📐 Extracted conventions: split=%s, %d headword patterns, "
            "%d cross-ref types, %d POS codes.",
            conventions["entry_split_mode"],
            len(conventions["headword_patterns"]),
            len(conventions["cross_refs"]),
            len(conventions["pos_codes"]),
        )

        return conventions

    def suggest_split_pattern(self, conventions: dict) -> str | None:
        """Suggests a split_before regex based on detected conventions.

        Returns None if line-based extraction is sufficient.
        """
        mode = conventions.get("entry_split_mode", "line")
        if mode == "line":
            return None

        has_dots = conventions.get("dotted_markers", False)
        has_cross_refs = bool(conventions.get("cross_refs", {}))

        # Build a split pattern from detected markers
        parts = []

        # If dotted markers exist, split before them when followed by a headword
        if has_dots:
            parts.append(r"(?<=\s)(?=[•·.]{1,4}\s*[a-z])")

        # If cross-references exist, split before them
        if has_cross_refs:
            ref_markers = "|".join(
                re.escape(m.replace(r"\b", "").replace(r"\s+", " ").rstrip(":"))
                for m in conventions["cross_refs"]
                if conventions["cross_refs"][m] > 0
            )
            if ref_markers:
                parts.append(f"(?<=\\s)(?={ref_markers})")

        if not parts:
            return None

        return "|".join(parts)

    def suggest_entry_pattern(self, conventions: dict) -> str | None:
        """Suggests an entry pattern regex based on detected conventions.

        Returns None if the default pattern is sufficient.
        """
        headword_patterns = conventions.get("headword_patterns", [])
        if not headword_patterns:
            return None

        # If all headwords are simple (no compounds, no dots), default is fine
        has_compounds = any(p.get("has_hyphen") for p in headword_patterns)
        has_dots = conventions.get("dotted_markers", False)

        if not has_compounds and not has_dots:
            return None

        # Build a more permissive headword pattern
        parts = []
        parts.append(r"^(?:a\s+)?")  # optional POS marker
        if has_dots:
            parts.append(r"[•·.]{0,4}\s*")  # optional dotted markers
        parts.append(r"(?P<headword>[a-zà-ÿ''\-]+")
        if has_compounds:
            parts.append(r"(?:[\s\-]+[a-zà-ÿ''\-]+){0,2}")  # compound headwords
        parts.append(r")")
        parts.append(r"\s*(?P<gloss>.+)$")

        return "".join(parts)

    # -- internals -----------------------------------------------------

    def _detect_split_mode(self, pages: list[RawPage]) -> str:
        """Determines whether entries are line-based, marker-based, or hybrid."""
        if not pages:
            return "line"

        multi_entry_lines = 0
        single_entry_lines = 0
        total_lines = 0

        for page in pages[:10]:  # sample first 10 pages
            lines = [l.strip() for l in page.text.splitlines() if l.strip()]
            for line in lines:
                total_lines += 1
                # Heuristic: if a line has multiple headword-like patterns,
                # it's a multi-entry line
                headword_matches = re.findall(
                    r"(?:^|\s)[a-z][a-z''\-]+(?:\s+[a-z][a-z''\-]+)?\s+[a-z(]",
                    line,
                )
                if len(headword_matches) > 1:
                    multi_entry_lines += 1
                else:
                    single_entry_lines += 1

        if total_lines == 0:
            return "line"

        multi_ratio = multi_entry_lines / total_lines
        if multi_ratio > 0.3:
            return "marker"  # many lines have multiple entries
        elif multi_ratio > 0.1:
            return "hybrid"  # some lines have multiple entries
        else:
            return "line"  # most lines have one entry

    def _detect_headword_patterns(self, pages: list[RawPage]) -> list[dict]:
        """Detects patterns in headword shapes."""
        patterns: list[dict] = []
        word_counts: Counter = Counter()
        has_hyphen = False
        has_apostrophe = False
        max_length = 0

        for page in pages[:10]:
            lines = [l.strip() for l in page.text.splitlines() if l.strip()]
            for line in lines:
                # Try to match headword at line start
                m = re.match(
                    r"^(?:a\s+)?[•·.]{0,3}\s*([a-zà-ÿ''\-]+)", line, re.I
                )
                if m:
                    hw = m.group(1)
                    word_counts[len(hw.split())] += 1
                    if "-" in hw:
                        has_hyphen = True
                    if "'" in hw or "\u2019" in hw:
                        has_apostrophe = True
                    max_length = max(max_length, len(hw))

        if word_counts:
            most_common_len = word_counts.most_common(1)[0][0]
            patterns.append({
                "most_common_word_count": most_common_len,
                "has_hyphen": has_hyphen,
                "has_apostrophe": has_apostrophe,
                "max_headword_length": max_length,
            })

        return patterns

    def _detect_gloss_languages(self, pages: list[RawPage]) -> list[str]:
        """Detects which pivot languages appear in glosses."""
        from book_profiler import FUNCTION_WORDS

        lang_counts: Counter = Counter()

        for page in pages[:10]:
            words = page.text.split()
            for word in words:
                clean = word.lower().strip(".,;:()'\"")
                for lang, vocab in FUNCTION_WORDS.items():
                    if clean in vocab:
                        lang_counts[lang] += 1

        return [lang for lang, _ in lang_counts.most_common(3) if _ > 5]

    def _detect_cross_refs(self, pages: list[RawPage]) -> dict[str, int]:
        """Counts cross-reference markers across pages."""
        counts: Counter = Counter()

        for page in pages[:10]:
            for name, pattern in CROSS_REF_PATTERNS.items():
                counts[name] += len(pattern.findall(page.text))

        return dict(counts)

    def _detect_pos_codes(self, pages: list[RawPage]) -> list[str]:
        """Detects part-of-speech codes used in the dictionary."""
        codes: Counter = Counter()

        for page in pages[:10]:
            for m in POS_CODES.finditer(page.text):
                codes[m.group(0).strip().rstrip(".")] += 1

        return [code for code, _ in codes.most_common(10)]

    def _has_dotted_markers(self, pages: list[RawPage]) -> bool:
        """Checks if the dictionary uses dotted aspect markers."""
        for page in pages[:10]:
            if len(DOTTED_MARKER.findall(page.text)) > 5:
                return True
        return False

    def _has_multi_sense(self, pages: list[RawPage]) -> bool:
        """Checks if entries have numbered senses."""
        for page in pages[:10]:
            if len(SENSE_MARKERS.findall(page.text)) > 3:
                return True
        return False

    def _detect_morphology_hints(self, pages: list[RawPage]) -> list[dict]:
        """Detects morphology patterns (reduplication, affixes)."""
        hints: list[dict] = []

        # Check for reduplication (common in Austronesian languages)
        redup_count = 0
        for page in pages[:10]:
            # Pattern: word-word (hyphenated reduplication)
            redup_count += len(
                re.findall(r"\b([a-z]+)-\1\b", page.text, re.I)
            )
            # Pattern: word word (full reduplication)
            redup_count += len(
                re.findall(r"\b([a-z]+)\s+\1\b", page.text, re.I)
            )

        if redup_count > 3:
            hints.append({
                "type": "reduplication",
                "count": redup_count,
                "description": "Dictionary contains reduplicated forms (plurals, emphasis)",
            })

        # Check for common Austronesian affixes
        affix_patterns = {
            "meN-": re.compile(r"\bme[nmblryksw]([a-z]+)", re.I),
            "peN-": re.compile(r"\bpe[nmblryksw]([a-z]+)", re.I),
            "-an": re.compile(r"\b([a-z]+)an\b", re.I),
            "me-...-i": re.compile(r"\bme([a-z]+)i\b", re.I),
            "ber-": re.compile(r"\bber([a-z]+)\b", re.I),
        }

        for affix, pattern in affix_patterns.items():
            count = sum(
                len(pattern.findall(page.text)) for page in pages[:10]
            )
            if count > 5:
                hints.append({
                    "type": "affix",
                    "pattern": affix,
                    "count": count,
                })

        return hints
