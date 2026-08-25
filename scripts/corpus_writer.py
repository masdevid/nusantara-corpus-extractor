"""
CorpusWriter: turns in-memory session state into the files a human/MT
pipeline actually consumes. 💾
"""

from __future__ import annotations

import json
import logging
import os

from models import DictionaryEntry, FlaggedTerm, PatternInsight, QualityReport

logger = logging.getLogger("indo_corpus_extractor.corpus_writer")


class CorpusWriter:
    def __init__(self, output_dir: str, language_code: str) -> None:
        self.output_dir = output_dir
        self.language_code = language_code
        os.makedirs(output_dir, exist_ok=True)

    def write_corpus(self, entries: list[DictionaryEntry]) -> str:
        path = os.path.join(self.output_dir, f"{self.language_code}_dictionary.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry.as_corpus_row(), ensure_ascii=False) + "\n")
        logger.info("💾 Wrote %d entries → %s", len(entries), path)
        return path

    def write_flagged_terms(self, flags: list[FlaggedTerm]) -> str:
        path = os.path.join(self.output_dir, "flagged_terms.md")
        header = (
            "# Flagged Terms 🚩\n\n"
            "Anything here needs a human read before it's trusted in the corpus.\n\n"
            "| Entry ID | Headword | Issue | Note | Raised | Status |\n"
            "|---|---|---|---|---|---|\n"
        )
        rows = "\n".join(f.as_markdown_row() for f in flags)
        with open(path, "w", encoding="utf-8") as f:
            f.write(header + rows + "\n")
        open_count = sum(1 for f in flags if not f.resolved)
        logger.info(
            "📝 flagged_terms.md updated — %d open, %d resolved.",
            open_count, len(flags) - open_count,
        )
        return path

    def write_quality_report(self, report: QualityReport) -> str:
        path = os.path.join(self.output_dir, f"quality_report_{report.pass_number}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(report.as_markdown())
        return path

    def write_pattern_insights(self, patterns: list[PatternInsight]) -> str:
        path = os.path.join(self.output_dir, "pattern_insights.md")
        header = (
            "# Pattern Insights 🧠\n\n"
            "Systematic issues spotted across multiple flags — fix these first,\n"
            "they tend to clear out a batch of individual flags at once.\n\n"
        )
        if not patterns:
            body = "_No systematic patterns spotted in the latest pass._\n"
        else:
            body = "\n".join(p.as_markdown() for p in patterns)
        with open(path, "w", encoding="utf-8") as f:
            f.write(header + body)
        logger.info("🧠 pattern_insights.md updated — %d pattern(s).", len(patterns))
        return path
