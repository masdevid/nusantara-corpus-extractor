"""
EntryExtractor: raw page text → DictionaryEntry objects. 🧩

Dictionary layouts vary, so this is deliberately pattern-driven rather than
hardcoded to one format. Swap `ENTRY_PATTERN` per dictionary if the layout
differs (e.g. "headword (pos) — gloss" vs "headword: gloss (pos)").
"""

from __future__ import annotations

import logging
import re

from models import DictionaryEntry, Language, RawPage

logger = logging.getLogger("indo_corpus_extractor.entry_extractor")

# Default layout: "headword (pos) gloss. Example sentence — example gloss."
# Local-language dictionaries commonly follow: HEADWORD n. gloss text
ENTRY_PATTERN = re.compile(
    r"^(?P<headword>[A-Za-zÀ-ÿ'’\-]+)\s*"
    r"(?:\((?P<pos>[a-z.]+)\))?\s*"
    r"(?P<gloss>.+?)\.?\s*$"
)

# Digital-text pages OCR-free → confidence 1.0; OCR pages inherit the
# page-level OCR confidence as a starting point for each entry.
DEFAULT_DIGITAL_CONFIDENCE = 1.0


class EntryExtractor:
    def __init__(self, language: Language, entry_pattern: re.Pattern = ENTRY_PATTERN) -> None:
        self.language = language
        self.entry_pattern = entry_pattern

    def extract(self, pages: list[RawPage]) -> list[DictionaryEntry]:
        entries: list[DictionaryEntry] = []
        skipped = 0

        for page in pages:
            for line in self._candidate_lines(page.text):
                match = self.entry_pattern.match(line)
                if not match:
                    skipped += 1
                    continue

                headword = match.group("headword").strip()
                gloss = match.group("gloss").strip()
                pos = (match.group("pos") or "").strip() or None

                if not headword or not gloss:
                    skipped += 1
                    continue

                confidence = (
                    page.ocr_confidence if page.was_ocr else DEFAULT_DIGITAL_CONFIDENCE
                )
                entries.append(
                    DictionaryEntry(
                        headword=headword,
                        part_of_speech=pos,
                        gloss_pivot=gloss,
                        page_ref=page.page_number,
                        confidence=confidence or DEFAULT_DIGITAL_CONFIDENCE,
                        source_language=self.language.code,
                    )
                )

        logger.info(
            "🧩 Extracted %d entries from %d pages (%d lines didn't match the "
            "entry pattern — check ENTRY_PATTERN if that number looks high).",
            len(entries), len(pages), skipped,
        )
        return entries

    # -- internals -----------------------------------------------------

    def _candidate_lines(self, text: str) -> list[str]:
        """Splits page text into candidate entry lines. Dictionaries often
        wrap entries mid-line in OCR output, so this does a light rejoin on
        lines that don't look like they start a new headword (lowercase
        continuation lines get glued to the previous line)."""
        raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
        joined: list[str] = []

        for line in raw_lines:
            starts_new_entry = bool(re.match(r"^[A-ZÀ-Ý]", line))
            if not starts_new_entry and joined:
                joined[-1] = f"{joined[-1]} {line}"
            else:
                joined.append(line)

        return joined
