"""
BookProfiler: learns what kind of book this actually is before extraction. 🔍

Not every source is a standard headword–gloss dictionary. Kids' picture
books have one phrase per page; morphology/grammar booklets are mostly
prose exposition with paradigm tables and example sentences; real
dictionaries have dense, repetitive entry shapes.

Profiling is SAMPLE-BASED so an image-only 500-page scan doesn't need
OCR-ing in full just to be classified: pages with a usable digital text
layer are scored for free, and image pages are OCR'd only at ~24 evenly
spaced sample points. Zone boundaries are therefore approximate (± one
sample step) — good enough to keep guides/prefaces out of extraction,
and the agent verifies findings against real pages anyway.
"""

from __future__ import annotations

import logging
import re
import statistics as st
from collections import Counter

from models import BookProfile, RawPage
from pdf_parser import PageProbe

logger = logging.getLogger("indo_corpus_extractor.book_profiler")

# Function words per candidate gloss language — used to detect which pivot
# language(s) the glosses are written in. Extend per project as needed.
FUNCTION_WORDS = {
    "indonesian": {
        "yang", "dan", "di", "dengan", "itu", "ini", "tidak", "untuk",
        "dari", "pada", "adalah", "karena", "juga", "oleh", "dalam",
    },
    "english": {
        "the", "of", "and", "in", "to", "is", "was", "that", "it",
        "he", "his", "as", "for", "on", "with", "are",
    },
}

# Signals that a page is prose exposition (grammar guide, preface) rather
# than dictionary body.
PROSE_TABLE_HINTS = re.compile(
    r"\b(?:subyek|obyek|subject|object|paradigm|morpheme|affix|suffix|prefix)\b",
    re.I,
)
NUMBERED_LIST = re.compile(r"\(\d\)")
CROSS_REF = re.compile(r"\b(?:KS|lht\s+jg|Lit|see\s+also)\s*:", re.I)
DOTTED_MARKER = re.compile(r"[•·.]{2,}")
PAREN_VARIANT = re.compile(r"\([a-zà-ÿ]{2,}\)")
# Part-of-speech codes many dictionaries print after the headword
# (`membubarkan v here ukate: ...`). Standalone in prose is rare, so a
# page full of them smells like dictionary body.
POS_CODES = re.compile(
    r"(?<![A-Za-z])(?:n|v|adj|adv|num|pron|prep|conj|part|interj)(?![A-Za-z])\.?",
)

# Grammar books announce their structure ("BAB V", "5.1 Pengertian");
# dictionaries don't (letter-section headers are single characters).
SECTION_HEADER = re.compile(
    r"^\s*(?:BAB\s+[IVXLC]+|\d+(?:\.\d+)+\s+\S)", re.M | re.I
)
# Numbered vocabulary lists ("12 13 14 ... Kiligirage Kii' me ...") —
# common in teaching materials and beginner word lists; entries have no
# headword–gloss shape at all.
NUMBERED_ITEM = re.compile(r"(?m)^\s*\d{1,4}\b")

MIN_WORDS_FOR_SCORING = 30   # thinner pages (titles, separators) can't be scored
MARKER_FLOOR = 3             # markers/page for a page to count as dictionary-like
ASL_CEILING = 15             # avg sentence length above this smells like prose
SAMPLE_BUDGET = 24           # max image pages OCR'd just for profiling
BAD_PAGE_OCR_THRESHOLD = 0.55


class BookProfiler:
    def profile(
        self,
        probes: list[PageProbe],
        ocr_selected,   # callable(list[int]) -> list[RawPage], from PDFParser
    ) -> BookProfile:
        """Classifies the book from digital-text pages plus an OCR'd sample
        of the image pages. Never OCRs more than SAMPLE_BUDGET pages."""
        needs_ocr = [p for p in probes if p.needs_ocr]
        sample = self._pick_sample(needs_ocr)
        ocred: dict[int, RawPage] = {}
        if sample:
            logger.info(
                "🔍 Sampling %d of %d image page(s) for profiling "
                "(no full-book OCR needed)...",
                len(sample), len(needs_ocr),
            )
            for pg in ocr_selected(sample):
                ocred[pg.page_number] = pg

        # Score everything we have text for: digital layers free, samples cheap.
        texts: dict[int, str] = {}
        for p in probes:
            if not p.needs_ocr and p.digital_text:
                texts[p.page_number] = p.digital_text
        for pn, pg in ocred.items():
            texts[pn] = pg.text
        stats = {pn: self._page_stats(t) for pn, t in texts.items()}

        like = {
            pn: s["words"] >= MIN_WORDS_FOR_SCORING
            and s["markers"] >= MARKER_FLOOR
            and s["avg_sentence_len"] <= ASL_CEILING
            for pn, s in stats.items()
        }

        profile = BookProfile()
        profile.unreadable_pages = sorted(
            pn for pn, pg in ocred.items()
            if (pg.ocr_confidence or 0) < BAD_PAGE_OCR_THRESHOLD
        )
        profile.front_matter_pages, profile.body_pages, profile.back_matter_pages = (
            self._split_zones(probes, like)
        )
        body_stats = {
            pn: s for pn, s in stats.items() if pn in set(profile.body_pages)
        }
        profile.conventions = self._conventions(body_stats)
        # With no dictionary-like zone, judge the book from everything we
        # scored — that's how workbooks/phrase books get named.
        profile.book_kind = self._book_kind(
            profile.body_pages, body_stats or stats, like
        )
        profile.suggested_settings = self._suggestions(profile, texts, body_stats)
        if len(needs_ocr) > len(sample):
            profile.notes.append(
                f"Profiled from a {len(sample)}-page sample of {len(needs_ocr)} "
                "image pages — zone boundaries are approximate (± one sample "
                "step); verify against real pages."
            )

        logger.info(
            "🔍 Profiled %d page(s) from %d scored (%d sampled) — kind=%s, "
            "front=%d, body=%d, back=%d.",
            len(probes), len(stats), len(ocred), profile.book_kind,
            len(profile.front_matter_pages), len(profile.body_pages),
            len(profile.back_matter_pages),
        )
        return profile

    # -- internals -----------------------------------------------------

    def _pick_sample(self, needs_ocr: list[PageProbe]) -> list[int]:
        """Evenly spaced page numbers across the image-page population."""
        if not needs_ocr:
            return []
        numbers = [p.page_number for p in needs_ocr]
        if len(numbers) <= SAMPLE_BUDGET:
            return numbers
        step = len(numbers) / SAMPLE_BUDGET
        return sorted({numbers[min(int(i * step), len(numbers) - 1)] for i in range(SAMPLE_BUDGET)})

    def _page_stats(self, text: str) -> dict:
        words = text.split()
        lines = [l for l in re.split(r"[\r\n]+", text) if l.strip()]
        sentences = [s for s in re.split(r"[.!?]", text) if s.strip()]
        return {
            "words": len(words),
            "markers": (
                len(DOTTED_MARKER.findall(text))
                + len(CROSS_REF.findall(text))
                + len(PAREN_VARIANT.findall(text))
                + len(POS_CODES.findall(text))
            ),
            "avg_sentence_len": (
                st.mean(len(s.split()) for s in sentences) if sentences else 0.0
            ),
            "prose_hints": len(PROSE_TABLE_HINTS.findall(text))
                + len(NUMBERED_LIST.findall(text)),
            "section_headers": len(SECTION_HEADER.findall(text)),
            "numbered_items": len(NUMBERED_ITEM.findall(text)),
            "gloss_langs": Counter(
                lang
                for lang, vocab in FUNCTION_WORDS.items()
                for w in words
                if w.lower().strip(".,;:()'’") in vocab
            ),
        }

    def _split_zones(
        self, probes: list[PageProbe], like: dict[int, bool]
    ) -> tuple[list[int], list[int], list[int]]:
        """Front matter = everything before the first sustained
        dictionary-like stretch; back matter mirrors it. With sampled
        scoring, boundaries are padded outward by one sample step so no
        body content lands outside the extraction range."""
        ordered = [p.page_number for p in probes]
        n = len(ordered)
        liked = [pn for pn in ordered if like.get(pn)]
        if not liked:
            return ordered, [], []

        # Sustained = 2 of the first/last 4 liked pages' neighbours also
        # liked — loose on purpose, sampling already thins the signal.
        def sustained_run(start_idx: int, direction: int) -> int:
            idxs = (
                range(start_idx, n)
                if direction == 1
                else range(start_idx, -1, -1)
            )
            hits = [
                like.get(ordered[j], False) for j in list(idxs)[:4]
            ]
            return sum(hits[:2]) >= 2

        first_idx = ordered.index(liked[0])
        last_idx = ordered.index(liked[-1])
        while first_idx > 0 and not sustained_run(first_idx, 1):
            first_idx -= 1
        while last_idx < n - 1 and not sustained_run(last_idx, -1):
            last_idx += 1

        step = max(1, n // max(len(liked), 1))
        start = max(0, first_idx - step)
        end = min(n - 1, last_idx + step)

        front = ordered[:start]
        back = ordered[end + 1:]
        body = ordered[start:end + 1]
        return front, body, back

    def _conventions(self, body_stats: dict[int, dict]) -> dict:
        if not body_stats:
            return {"marker density (body)": "no scoreable pages sampled"}
        markers_per_page = st.mean(s["markers"] for s in body_stats.values())
        gloss_mix: Counter = Counter()
        for s in body_stats.values():
            gloss_mix.update(s["gloss_langs"])
        total = len(body_stats)
        numbered_pages = sum(1 for s in body_stats.values() if s["numbered_items"] >= 5)
        return {
            "marker density (body)": f"{markers_per_page:.1f} per page"
            " (dotted aspect runs, cross-refs, parenthetical variants)",
            "dotted-marker runs": sum(s["markers"] for s in body_stats.values()),
            "numbered-list pages": (
                f"{numbered_pages}/{total} — numbered vocabulary-list style,"
                " not headword–gloss entries"
                if numbered_pages > total * 0.3
                else f"{numbered_pages}/{total}"
            ),
            "gloss language mix": dict(gloss_mix) or "no function-word signal",
        }

    def _book_kind(
        self, body: list[int], body_stats: dict[int, dict], like: dict[int, bool]
    ) -> str:
        if not body or not body_stats:
            # No dictionary-like zone anywhere. If the book still has real
            # text (workbooks, phrase books, kids' books), say so instead
            # of shrugging "unknown" — extraction strategy differs.
            if body_stats and st.median(
                s["words"] for s in body_stats.values()
            ) >= MIN_WORDS_FOR_SCORING:
                return "teaching_book"
            return "unknown"

        words = st.median(s["words"] for s in body_stats.values())
        markers = st.mean(s["markers"] for s in body_stats.values())
        prose_share = sum(
            1 for s in body_stats.values()
            if s["prose_hints"] >= 3 or s["avg_sentence_len"] > ASL_CEILING
        ) / len(body_stats)
        dict_like_share = sum(1 for pn in body_stats if like.get(pn)) / len(body_stats)
        sectional_share = sum(
            1 for s in body_stats.values() if s["section_headers"] >= 1
        ) / len(body_stats)

        if words < 60 and markers < 3:
            return "kids_picture_book"
        if sectional_share >= 0.15 and (prose_share >= 0.3 or sectional_share >= 0.5):
            return "grammar_morphology"
        if dict_like_share < 0.5 and prose_share >= 0.5:
            return "grammar_morphology"
        if dict_like_share >= 0.2 and prose_share >= 0.2:
            return "mixed"
        return "dictionary"

    def _suggestions(
        self,
        profile: BookProfile,
        texts: dict[int, str],
        body_stats: dict[int, dict],
    ) -> list[str]:
        suggestions: list[str] = []
        dotted = sum(s["markers"] for s in body_stats.values())
        if dotted:
            suggestions.append(
                "## Entry splitting — split_before: `\\s+(?=[a-zà-ÿ'’\\-]+\\s+[•·.]{1,3}\\s)`"
                f"  ({dotted} marker hits detected)"
            )
        mix = profile.conventions.get("gloss language mix")
        if isinstance(mix, dict) and mix:
            suggestions.append(
                f"## Notes on pivot gloss conventions — gloss languages detected: {', '.join(mix)}"
            )
        suggestions.append(
            "## Digital text layer — most pages were OCR'd; verify artifacts by eye"
        )
        if profile.book_kind in ("kids_picture_book", "grammar_morphology", "teaching_book"):
            suggestions.append(
                f"# Book kind is '{profile.book_kind}' — standard headword–gloss"
                " extraction will underperform; review book_profile.md before running."
            )
        return suggestions
