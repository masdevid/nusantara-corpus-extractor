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

# In split mode, a candidate longer than this isn't an entry — it's a page
# (or slab of pages) the split pattern couldn't cut. Emitting it as one
# entry would bake a bogus headword into the corpus; skip and count instead.
MAX_CHUNK_CHARS = 800


class EntryExtractor:
    def __init__(
        self,
        language: Language,
        entry_pattern: re.Pattern | None = None,
        split_pattern: re.Pattern | None = None,
    ) -> None:
        self.language = language
        self.entry_pattern = entry_pattern or ENTRY_PATTERN
        # Optional zero-width "split before this" regex (from the language's
        # phonology ref). When set, page text is joined into one block and
        # cut into entry chunks at every match — for dictionaries where
        # several entries share a line and line starts mean nothing.
        self.split_pattern = split_pattern

    def extract(self, pages: list[RawPage]) -> list[DictionaryEntry]:
        entries: list[DictionaryEntry] = []
        skipped = 0
        oversized = 0

        for page in pages:
            if self.split_pattern:
                candidates = self._split_chunks(page.text)
            else:
                candidates = self._candidate_lines(page.text)

            for candidate in candidates:
                if len(candidate) > MAX_CHUNK_CHARS:
                    oversized += 1
                    continue
                match = self.entry_pattern.match(candidate)
                if not match:
                    skipped += 1
                    continue

                headword = (match.group("headword") or "").strip()
                gloss = (match.group("gloss") or "").strip()
                pos = ((match.groupdict().get("pos") or "") or "").strip() or None

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

        mode = "split-pattern" if self.split_pattern else "line"
        logger.info(
            "🧩 Extracted %d entries from %d pages in %s mode (%d candidates "
            "didn't match the entry pattern, %d oversized slabs skipped — "
            "check the phonology ref's entry settings if those numbers look "
            "high).",
            len(entries), len(pages), mode, skipped, oversized,
        )
        return entries

    # -- internals -----------------------------------------------------

    def _split_chunks(self, text: str) -> list[str]:
        """Cuts a whole page into entry chunks at every split-pattern match.
        Inner line breaks are collapsed to single spaces — the text layer
        hard-wraps every few words mid-entry."""
        assert self.split_pattern is not None
        chunks = [
            " ".join(c.split()) for c in self.split_pattern.split(text) if c.strip()
        ]
        return [c for c in chunks if c]

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
