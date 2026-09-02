"""
MorphologyRules: detects and manages morphological patterns (reduplication,
affixation, verb conjugation) in Nusantara languages. 🧬

This module provides:
- Reduplication detection (full, partial, hyphenated)
- Affix pattern detection (meN-, peN-, -an, ber-, etc.)
- Root ↔ derived form cross-referencing
- Conventions file parsing for morphology section

Language-agnostic: patterns are configured per language, not hardcoded.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict

from models import DictionaryEntry

logger = logging.getLogger("indo_corpus_extractor.morphology_rules")

# Common Austronesian affix patterns — loaded as defaults, overridden
# per language via conventions file.
DEFAULT_AFFIXES = {
    "prefix": [
        ("meN-", re.compile(r"^(?:me[nmblryksw])(.+)")),
        ("peN-", re.compile(r"^(?:pe[nmblryksw])(.+)")),
        ("ber-", re.compile(r"^ber(.+)")),
        ("ter-", re.compile(r"^ter(.+)")),
        ("di-", re.compile(r"^di(.+)")),
    ],
    "suffix": [
        ("-an", re.compile(r"^(.+)an$")),
        ("-i", re.compile(r"^(.+)i$")),
        ("-kan", re.compile(r"^(.+)kan$")),
    ],
    "circumfix": [
        ("ke-...-an", re.compile(r"^ke(.+)an$")),
        ("peN-...-an", re.compile(r"^(?:pe[nmblryksw])(.+)an$")),
    ],
}


class MorphologyRules:
    """Manages morphological pattern detection and root cross-referencing."""

    def __init__(
        self,
        custom_affixes: dict | None = None,
        reduplication_patterns: list[str] | None = None,
    ):
        """Initialize with optional custom affix patterns.

        Args:
            custom_affixes: Override default affix patterns. Format:
                {"prefix": [("meN-", regex), ...], "suffix": [...], "circumfix": [...]}
            reduplication_patterns: Additional reduplication patterns (regex strings).
        """
        self.affixes = custom_affixes or DEFAULT_AFFIXES
        self.reduplication_patterns = [
            # Full reduplication: word-word (hyphenated)
            re.compile(r"^([a-z]+)-\1$", re.I),
            # Full reduplication: word word (space)
            re.compile(r"^([a-z]+)\s+\1$", re.I),
            # Partial reduplication: CVCVCV → CVCV (first syllable repeated)
            re.compile(r"^([a-z]{2,3})\1$", re.I),
        ]
        if reduplication_patterns:
            for pat in reduplication_patterns:
                self.reduplication_patterns.append(re.compile(pat, re.I))

        # Learned morphology: headword → root (populated during analysis)
        self._headword_to_root: dict[str, str] = {}
        # Root → derived forms
        self._root_to_derived: dict[str, list[str]] = defaultdict(list)

    def from_conventions_file(self, conventions_text: str) -> "MorphologyRules":
        """Parse morphology section from conventions markdown.

        Expects a section like:
        ## Morphology
        - Reduplication: full (bo-bo), partial (si-siro)
        - Prefixes: meN-, peN-, ber-, ter-
        - Suffixes: -an, -i, -kan
        - Circumfixes: ke-...-an, peN-...-an
        """
        lines = conventions_text.splitlines()
        in_morphology = False
        custom_redup = []
        custom_prefixes = []
        custom_suffixes = []
        custom_circumfixes = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## Morphology"):
                in_morphology = True
                continue
            if in_morphology and stripped.startswith("## "):
                break  # next section
            if not in_morphology or not stripped.startswith("- "):
                continue

            content = stripped[2:].lower()
            if content.startswith("reduplication:"):
                # Extract patterns from the line
                pat_text = content.split(":", 1)[1]
                custom_redup.append(pat_text.strip())
            elif content.startswith("prefix"):
                pat_text = content.split(":", 1)[1]
                for p in pat_text.split(","):
                    p = p.strip().rstrip("-")
                    if p:
                        custom_prefixes.append(p)
            elif content.startswith("suffix"):
                pat_text = content.split(":", 1)[1]
                for p in pat_text.split(","):
                    p = p.strip().lstrip("-")
                    if p:
                        custom_suffixes.append(p)
            elif content.startswith("circumfix"):
                pat_text = content.split(":", 1)[1]
                for p in pat_text.split(","):
                    p = p.strip()
                    if p:
                        custom_circumfixes.append(p)

        # Rebuild affix patterns from parsed data
        if custom_prefixes or custom_suffixes or custom_circumfixes:
            new_affixes: dict[str, list] = {
                "prefix": [],
                "suffix": [],
                "circumfix": [],
            }
            for p in custom_prefixes:
                escaped = re.escape(p).replace("N", "[nmblryksw]")
                pat = re.compile(r"^(?:" + escaped + r")(.+)")
                new_affixes["prefix"].append((p, pat))
            for p in custom_suffixes:
                pat = re.compile(r"^(.+)" + re.escape(p) + r"$")
                new_affixes["suffix"].append(("-" + p, pat))
            for cf in custom_circumfixes:
                parts = re.split(r"\.\.\.", cf)
                if len(parts) == 2:
                    prefix = parts[0].lstrip("-").rstrip("-")
                    suffix = parts[1].lstrip("-").rstrip("-")
                    escaped_prefix = re.escape(prefix).replace("N", "[nmblryksw]")
                    pat = re.compile(
                        r"^(?:" + escaped_prefix + r")(.+)"
                        + re.escape(suffix) + r"$"
                    )
                    new_affixes["circumfix"].append((cf, pat))
            self.affixes = new_affixes

        return self

    def is_reduplication(self, word: str) -> tuple[bool, str | None]:
        """Check if a word is a reduplicated form.

        Returns (is_redup, base_form) where base_form is the root word.
        """
        for pattern in self.reduplication_patterns:
            m = pattern.match(word)
            if m:
                return True, m.group(1)
        return False, None

    def strip_affixes(self, word: str) -> list[tuple[str, str]]:
        """Try stripping affixes from a word.

        Returns list of (affix_type, root) pairs. A word may match
        multiple affix patterns (e.g., meN- + -an = circumfix).
        """
        results = []

        for affix_type, affix_list in self.affixes.items():
            for affix_name, pattern in affix_list:
                m = pattern.match(word)
                if m:
                    root = m.group(1)
                    if len(root) >= 2:  # root must be at least 2 chars
                        results.append((affix_type, root))

        return results

    def find_root(self, word: str) -> str | None:
        """Find the root form of a word by stripping affixes.

        Returns the root if found, None if the word appears to be a root.
        """
        # Check cache first
        if word in self._headword_to_root:
            return self._headword_to_root[word]

        # Try reduplication first
        is_redup, base = self.is_reduplication(word)
        if is_redup and base:
            self._headword_to_root[word] = base
            self._root_to_derived[base].append(word)
            return base

        # Try affix stripping
        affix_results = self.strip_affixes(word)
        if affix_results:
            # Prefer circumfix > prefix > suffix (most specific first)
            for affix_type, root in affix_results:
                self._headword_to_root[word] = root
                self._root_to_derived[root].append(word)
                return root

        return None

    def find_derived_forms(self, root: str) -> list[str]:
        """Find all derived forms of a root in the corpus."""
        return list(self._root_to_derived.get(root, []))

    def analyze_entries(
        self, entries: list[DictionaryEntry]
    ) -> list[dict]:
        """Analyze a set of entries for morphology patterns.

        Returns a list of morphology findings:
        [
            {
                "type": "reduplication" | "prefix" | "suffix" | "circumfix",
                "derived_form": "bo-bo",
                "root": "bo",
                "entry_id": "abc123",
                "action": "keep_as_entry" | "flag_as_variant" | "cross_reference",
            },
            ...
        ]
        """
        findings = []
        root_entries: dict[str, list[DictionaryEntry]] = defaultdict(list)

        # First pass: identify roots
        for entry in entries:
            root = self.find_root(entry.headword)
            if root:
                root_entries[root].append(entry)
            else:
                root_entries[entry.headword].append(entry)

        # Second pass: classify each derived form
        for root, derived_entries in root_entries.items():
            for entry in derived_entries:
                if entry.headword == root:
                    continue  # root itself, not a derived form

                # Determine if this should be kept as a separate entry
                is_redup, _ = self.is_reduplication(entry.headword)
                affix_results = self.strip_affixes(entry.headword)

                if is_redup:
                    # Reduplication often changes meaning (plural, emphasis)
                    # → keep as separate entry
                    action = "keep_as_entry"
                elif any(t == "prefix" for t, _ in affix_results):
                    # Prefix may change meaning or just conjugate
                    # → flag as variant for agent to decide
                    action = "flag_as_variant"
                elif any(t == "suffix" for t, _ in affix_results):
                    # Suffix often just conjugates
                    # → cross-reference to root
                    action = "cross_reference"
                else:
                    action = "keep_as_entry"

                findings.append({
                    "type": (
                        "reduplication" if is_redup
                        else affix_results[0][0] if affix_results
                        else "unknown"
                    ),
                    "derived_form": entry.headword,
                    "root": root,
                    "entry_id": entry.id,
                    "action": action,
                })

        logger.info(
            "🧬 Analyzed %d entries: %d derived forms found "
            "(%d reduplication, %d affixed).",
            len(entries),
            len(findings),
            sum(1 for f in findings if f["type"] == "reduplication"),
            sum(1 for f in findings if f["type"] != "reduplication"),
        )

        return findings

    def as_conventions_section(self) -> str:
        """Generate a morphology section for the conventions file."""
        lines = ["## Morphology", ""]

        # Reduplication
        lines.append("- Reduplication: full (word-word), partial (CVCVCV → CVCV)")

        # Prefixes
        prefix_names = [name for name, _ in self.affixes.get("prefix", [])]
        if prefix_names:
            lines.append(f"- Prefixes: {', '.join(prefix_names)}")

        # Suffixes
        suffix_names = [name for name, _ in self.affixes.get("suffix", [])]
        if suffix_names:
            lines.append(f"- Suffixes: {', '.join(suffix_names)}")

        # Circumfixes
        cf_names = [name for name, _ in self.affixes.get("circumfix", [])]
        if cf_names:
            lines.append(f"- Circumfixes: {', '.join(cf_names)}")

        # Learned patterns
        if self._root_to_derived:
            lines.append("")
            lines.append("### Learned patterns")
            for root, derived in sorted(self._root_to_derived.items()):
                lines.append(f"- {root}: {', '.join(derived[:5])}")

        return "\n".join(lines) + "\n"
