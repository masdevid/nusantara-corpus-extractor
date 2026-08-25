"""
PatternSpotter: looks across ALL flags from a pass (not one at a time) for
systematic issues. 🧠🔍

Reviewing 40 individual flags is slow. Reviewing "this exact OCR
substitution shows up in 12 of them" is fast, and it's the kind of thing a
human reviewer would eventually notice anyway — this just surfaces it
sooner, and suggests the fix that would clear all 12 flags at once.

Nothing here is language-specific: it operates purely on the structure of
FlaggedTerm/DictionaryEntry data that the rest of the pipeline already
produces.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict

from models import DictionaryEntry, FlaggedTerm, IssueType, PatternInsight

logger = logging.getLogger("indo_corpus_extractor.pattern_spotter")

# A substitution or a bad page needs to show up at least this many times in
# one pass before it's worth surfacing as a "pattern" rather than noise.
MIN_OCCURRENCES_FOR_PATTERN = 3


class PatternSpotter:
    def spot_patterns(
        self, flags: list[FlaggedTerm], entries: list[DictionaryEntry]
    ) -> list[PatternInsight]:
        insights: list[PatternInsight] = []
        insights += self._recurring_substitutions(flags)
        insights += self._clustered_pages(flags, entries)
        insights += self._issue_type_hotspots(flags)

        logger.info("🧠 Spotted %d pattern(s) this pass.", len(insights))
        return insights

    # -- pattern detectors -----------------------------------------------

    def _recurring_substitutions(self, flags: list[FlaggedTerm]) -> list[PatternInsight]:
        """A (before, after) character substitution that failed validation
        on several DIFFERENT headwords is probably a real confusion pair
        that just needs a slightly different replacement rule, not 5+
        individual human reviews."""
        by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
        for flag in flags:
            if flag.attempted_fix:
                by_pair[flag.attempted_fix].append(flag.entry_id)

        insights = []
        for (before, after), entry_ids in by_pair.items():
            if len(entry_ids) >= MIN_OCCURRENCES_FOR_PATTERN:
                insights.append(
                    PatternInsight(
                        pattern_type="recurring_ocr_substitution",
                        description=(
                            f"The substitution '{before}' → '{after}' was attempted "
                            f"and failed orthography validation on {len(entry_ids)} "
                            f"different entries. This is probably a real OCR "
                            f"confusion pair, but the target character/rule in the "
                            f"phonology reference may need adjusting rather than "
                            f"the substitution being wrong outright."
                        ),
                        affected_entry_ids=entry_ids,
                        suggested_action=(
                            f"Review whether '{before}' should map to something "
                            f"other than '{after}' in this language's phonology "
                            f"reference, then re-run the pass — this could clear "
                            f"all {len(entry_ids)} flags at once."
                        ),
                        confidence=min(0.5 + 0.05 * len(entry_ids), 0.95),
                    )
                )
        return insights

    def _clustered_pages(
        self, flags: list[FlaggedTerm], entries: list[DictionaryEntry]
    ) -> list[PatternInsight]:
        """If a disproportionate share of flags trace back to a handful of
        pages, the scan quality (not the extraction logic) is the problem —
        worth flagging as a page-level issue, not N separate word-level
        ones."""
        entry_page = {e.id: e.page_ref for e in entries}
        page_counts: Counter[int] = Counter(
            entry_page[f.entry_id]
            for f in flags
            if f.entry_id in entry_page and entry_page[f.entry_id] is not None
        )

        insights = []
        for page, count in page_counts.items():
            if count >= MIN_OCCURRENCES_FOR_PATTERN:
                affected = [
                    f.entry_id for f in flags if entry_page.get(f.entry_id) == page
                ]
                insights.append(
                    PatternInsight(
                        pattern_type="bad_page_cluster",
                        description=(
                            f"Page {page} accounts for {count} flags this pass — "
                            f"likely a scan-quality issue (faint print, skew, bleed-"
                            f"through) rather than {count} unrelated problems."
                        ),
                        affected_entry_ids=affected,
                        suggested_action=(
                            f"Re-scan or re-photograph page {page} at higher "
                            f"resolution/contrast before re-running extraction on it."
                        ),
                        confidence=min(0.4 + 0.1 * count, 0.9),
                    )
                )
        return insights

    def _issue_type_hotspots(self, flags: list[FlaggedTerm]) -> list[PatternInsight]:
        """If one issue type dominates the pass, that's a signal about
        where to spend review time first."""
        if not flags:
            return []

        counts = Counter(f.issue_type for f in flags)
        dominant, dominant_count = counts.most_common(1)[0]
        if dominant_count < MIN_OCCURRENCES_FOR_PATTERN or dominant_count < len(flags) * 0.5:
            return []

        affected = [f.entry_id for f in flags if f.issue_type == dominant]
        return [
            PatternInsight(
                pattern_type="issue_type_hotspot",
                description=(
                    f"{dominant.value} accounts for {dominant_count}/{len(flags)} "
                    f"flags this pass — that's the bottleneck, not a spread of "
                    f"unrelated issues."
                ),
                affected_entry_ids=affected,
                suggested_action=self._hotspot_suggestion(dominant),
                confidence=round(dominant_count / len(flags), 2),
            )
        ]

    def _hotspot_suggestion(self, issue_type: IssueType) -> str:
        return {
            IssueType.OCR_TYPO: (
                "Review the phonology reference's confusion pairs — a "
                "systematic gap there is cheaper to fix than reviewing each typo."
            ),
            IssueType.LOW_CONFIDENCE: (
                "Check overall scan quality/DPI for this source — low "
                "confidence at scale usually traces back to the scan, not the words."
            ),
            IssueType.MEANING_CONFLICT: (
                "Worth a batch web-verification pass (see flags with "
                "needs_web_check=True) rather than resolving these one by one."
            ),
            IssueType.DUPLICATE_HEADWORD: (
                "Check whether this dictionary marks distinct senses of the "
                "same headword in a way the entry pattern isn't capturing."
            ),
            IssueType.BAD_PAGE: (
                "Re-scan the affected pages before continuing — extraction "
                "quality is capped by input quality here."
            ),
        }.get(issue_type, "Review these flags as a batch — they share a root cause.")
