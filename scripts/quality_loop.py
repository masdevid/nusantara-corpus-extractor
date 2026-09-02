"""
QualityLoop: the orchestrator. Runs the full pass, spots patterns across
flags, and decides whether to loop again. This is the only module that
owns "are we done yet?" 🔁✅
"""

from __future__ import annotations

import logging

from book_profiler import BookProfiler
from corpus_writer import CorpusWriter
from entry_extractor import EntryExtractor
from meaning_crosscheck import MeaningCrossChecker
from models import DictionaryEntry, ExtractionSession, QualityReport
from pattern_spotter import PatternSpotter
from pdf_parser import PDFParser
from typo_corrector import PhonologyReference, TypoCorrector
from web_verification import WebVerificationQueue

logger = logging.getLogger("indo_corpus_extractor.quality_loop")

DEFAULT_MAX_ITERATIONS = 5


class QualityLoop:
    def __init__(
        self,
        session: ExtractionSession,
        phonology_path: str,
        output_dir: str,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        book_id: str | None = None,
    ) -> None:
        self.session = session
        self.phonology = PhonologyReference.from_markdown(phonology_path)
        self.writer = CorpusWriter(
            output_dir=output_dir,
            language_code=session.language.code,
            book_id=book_id,
        )
        self.max_iterations = max_iterations
        # OCR lang hint comes from the language's own pivot config — nothing
        # here is hardcoded to any specific language pair.
        self.parser = PDFParser(ocr_lang_hint=session.language.pivot_code)
        self.profiler = BookProfiler()
        self.pattern_spotter = PatternSpotter()

    def run(self, existing_corpus: list[DictionaryEntry] | None = None) -> ExtractionSession:
        logger.info(
            "🚀 Starting extraction loop for %s → %s (max %d passes)...",
            self.session.language.name, self.session.language.pivot_name,
            self.max_iterations,
        )

        # Stage 1 — probe: cheap pass, no rendering/OCR. Profiling must not
        # cost a full-book OCR on image-only scans.
        probes = self.parser.probe(self.session.source_pdf)

        # Stage 2 — profile: classify the book from digital text + a small
        # OCR'd sample; detect zones so guides/prefaces stay out of
        # extraction and non-dictionary books don't get force-parsed.
        profile = self.profiler.profile(
            probes,
            lambda numbers: self.parser.ocr_selected(probes, numbers),
        )
        self.session.profile = profile
        self.writer.write_book_profile(profile)

        if not profile.body_pages:
            logger.warning(
                "⚠️ Profiler classified this book as '%s' with no "
                "dictionary-like body — headword–gloss extraction does not "
                "apply. See book_profile.md; corpus left empty.",
                profile.book_kind,
            )
            self.writer.write_corpus([])
            return self.session

        # Stage 3 — full parse of the body zone only (OCR included).
        parse_result = self.parser.parse_source(
            self.session.source_pdf, only_pages=set(profile.body_pages)
        )
        for bad_page in parse_result.bad_pages:
            logger.warning("🚩 Page %d flagged as unreadable — skipped entirely.", bad_page)

        extractor = EntryExtractor(
            self.session.language,
            entry_pattern=self.phonology.entry_pattern,
            split_pattern=self.phonology.entry_split,
        )
        self.session.entries = extractor.extract(parse_result.pages)
        for bad_page in parse_result.bad_pages:
            logger.warning("🚩 Page %d flagged as unreadable — skipped entirely.", bad_page)

        for pass_number in range(1, self.max_iterations + 1):
            self.session.current_pass = pass_number
            entries_in = len(self.session.entries)

            corrector = TypoCorrector(self.phonology, pass_number)
            self.session.entries, typo_flags = corrector.correct(self.session.entries)
            crosschecker = MeaningCrossChecker(pass_number, self.session.language)
            meaning_flags = crosschecker.crosscheck(self.session.entries, existing_corpus)

            new_flags = typo_flags + meaning_flags
            resolved_this_pass = self._reconcile_flags(new_flags)

            patterns = self.pattern_spotter.spot_patterns(new_flags, self.session.entries)
            self.session.patterns.extend(patterns)

            # Last pass before giving up: anything still open is worth a
            # web check even if the individual modules didn't flag it —
            # a human is about to look at this either way.
            is_final_pass = pass_number == self.max_iterations
            if is_final_pass:
                for flag in self.session.open_flags():
                    if not flag.needs_web_check:
                        flag.needs_web_check = True
                        flag.suggested_query = flag.suggested_query or (
                            f'"{flag.headword}" {self.session.language.name} meaning'
                        )

            report = QualityReport(
                pass_number=pass_number,
                entries_in=entries_in,
                entries_out=len(self.session.entries),
                typo_fixes_applied=getattr(corrector, "last_fixes_applied", 0),
                flags_raised=len(new_flags),
                flags_resolved=resolved_this_pass,
                patterns_spotted=len(patterns),
                converged=len(new_flags) == 0,
            )
            self.session.reports.append(report)
            self.writer.write_quality_report(report)
            self.writer.write_flagged_terms(self.session.flagged_terms)
            self.writer.write_pattern_insights(self.session.patterns)

            logger.info(
                "🔁 Pass %d done — %d flags raised, %d patterns spotted, %d open "
                "flags total.",
                pass_number, len(new_flags), len(patterns), len(self.session.open_flags()),
            )

            if report.converged:
                logger.info("🎉 Converged after %d pass(es) — no new flags.", pass_number)
                break
        else:
            logger.warning(
                "⏸️ Hit max_iterations (%d) with %d open flags still unresolved — "
                "handing off to a human (%d of them queued for web verification).",
                self.max_iterations, len(self.session.open_flags()),
                len(self.session.flags_needing_web_check()),
            )

        self.writer.write_corpus(self.session.entries)

        web_queue = WebVerificationQueue(self.session)
        pending = web_queue.build_queue()
        if pending:
            logger.info(
                "🌐 %d flag(s) ready for optional web verification — the agent "
                "can run these with web_search and record findings via "
                "WebVerificationQueue.record_evidence().", len(pending),
            )

        return self.session

    # -- internals -----------------------------------------------------

    def _reconcile_flags(self, new_flags: list) -> int:
        """Adds new flags to the session and returns how many *previously
        open* flags this pass resolved (i.e. no longer being re-raised)."""
        previously_open_ids = {f.entry_id for f in self.session.open_flags()}
        newly_raised_ids = {f.entry_id for f in new_flags}

        resolved_count = 0
        for flag in self.session.flagged_terms:
            if (
                not flag.resolved
                and flag.entry_id in previously_open_ids
                and flag.entry_id not in newly_raised_ids
            ):
                flag.resolved = True
                flag.resolution_note = "Not re-raised in subsequent pass."
                resolved_count += 1

        # One flag per entry: re-raised entries keep their existing record
        # (and original pass number) instead of piling up a duplicate every
        # pass — otherwise open-flag counts inflate without converging.
        fresh_flags: list = []
        seen_this_pass: set[str] = set()
        for flag in new_flags:
            if flag.entry_id in previously_open_ids or flag.entry_id in seen_this_pass:
                continue
            seen_this_pass.add(flag.entry_id)
            fresh_flags.append(flag)
        self.session.flagged_terms.extend(fresh_flags)
        return resolved_count
