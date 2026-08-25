"""
WebVerificationQueue: bridges flagged terms to the agent's web_search tool. 🌐

Important: this module does NOT perform any web requests itself. Scripts
in this pipeline run in a sandboxed environment without general internet
access — and even if they didn't, deciding what a search result actually
means is a judgment call the agent (Claude, running this skill) should
make, not something to fake with a scraper.

What this module does:
  1. `build_queue()` — collect flags worth a quick search, each already
     carrying a `suggested_query` from typo_corrector/meaning_crosscheck.
  2. `record_evidence()` — once the agent has actually run the search and
     read the results, write its finding back onto the flag (and mark it
     resolved if the evidence is conclusive).

See agents/extraction-agent.md, step "OPTIONAL WEB VERIFY", for how the
agent is expected to drive this loop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from models import ExtractionSession, FlaggedTerm

logger = logging.getLogger("indo_corpus_extractor.web_verification")


@dataclass
class VerificationTask:
    entry_id: str
    headword: str
    issue_type: str
    query: str


class WebVerificationQueue:
    def __init__(self, session: ExtractionSession) -> None:
        self.session = session

    def build_queue(self) -> list[VerificationTask]:
        """Returns the flags worth a web check, each with its pre-built
        query. The agent runs `web_search(task.query)` for each one — this
        function's job is only to decide WHICH flags are worth the round
        trip, not to search."""
        tasks = [
            VerificationTask(
                entry_id=f.entry_id,
                headword=f.headword,
                issue_type=f.issue_type.value,
                query=f.suggested_query,
            )
            for f in self.session.flags_needing_web_check()
            if f.suggested_query
        ]
        logger.info("🌐 %d flag(s) queued for optional web verification.", len(tasks))
        return tasks

    def record_evidence(
        self,
        entry_id: str,
        evidence: str,
        sources: list[str],
        resolves_flag: bool,
    ) -> FlaggedTerm | None:
        """Call this after the agent has run the search and formed a
        conclusion. `evidence` should be the agent's own paraphrase of what
        it found (never a verbatim quote — normal copyright discipline
        applies here same as anywhere else), `sources` the URLs it used.
        """
        matches = [f for f in self.session.flagged_terms if f.entry_id == entry_id]
        if not matches:
            logger.warning("⚠️ No flag found for entry_id=%s — nothing to update.", entry_id)
            return None

        flag = matches[-1]  # most recent flag for this entry
        flag.web_evidence = evidence
        flag.web_sources = sources
        if resolves_flag:
            flag.resolved = True
            flag.resolution_note = "Resolved via web verification."
            logger.info("🌐✅ Flag for '%s' resolved via web evidence.", flag.headword)
        else:
            logger.info(
                "🌐 Web evidence recorded for '%s' but didn't conclusively resolve "
                "it — still needs a human read.", flag.headword,
            )
        return flag
