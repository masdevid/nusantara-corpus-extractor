---
name: nusantara-corpus-pdf-extractor
description: Extracts structured parallel-corpus entries from ANY local/low-resource-language dictionary supplied as a PDF or scanned image-PDF — fully language-agnostic, with Bahasa Indonesia as the default pivot language (works for Biak, Sentani, Lani, or a dictionary for a language never seen before). Goes beyond one-shot OCR-to-JSONL parsing — runs a closed quality loop that OCR-typo-corrects headwords/definitions, cross-checks meanings against the pivot-language gloss and existing corpus entries, spots systematic patterns across flags instead of reviewing them one by one, and can optionally use web search to help resolve conflicting or ambiguous records. Trigger this whenever the user uploads a dictionary PDF/scan, mentions "corpus extraction", "parallel corpus from dictionary", building an MT training corpus from a scanned dictionary, or wants to reuse/extend the pipeline for a new language.
---

# Nusantara Corpus PDF Extractor

Turns a scanned or digital dictionary (local language ⇄ some pivot/gloss
language) into a quality-checked JSONL parallel corpus, through a **loop**,
not a single pass.

Fully language-agnostic by design: which local language, which pivot
language (Bahasa Indonesia by default, or whatever the dictionary glosses
into), and which orthography rules apply are all supplied as config — nothing
in the pipeline logic assumes a specific language pair. Originally generalized
from Lani dictionary extraction work, but "Lani-specific" behavior has been
deliberately designed out.

## When to use this

- User uploads a dictionary PDF (digital-text or scanned/image-based) and
  wants entries turned into structured data — for any language pair.
  A folder of split PDFs (one file per page range) works too and is
  parsed as a single book.
- User references "the Indo Corpus Extraction pipeline/agent", or wants to
  start a *new* language's dictionary corpus the same way.
- Any request that includes typo-correction, meaning cross-checking,
  pattern-spotting across errors, or "improving dictionary quality"
  alongside PDF/OCR parsing.
- Flags are piling up with genuinely ambiguous or conflicting readings —
  this skill's loop can queue those for a quick web search instead of
  requiring a human to resolve every single one.

## Architecture (domain model first)

```
references/quality_loop_guide.md   ← read this before running the loop —
                                      explains the OCR-confusion tables,
                                      cross-check tricks, and convergence rule
references/phonology_template.md   ← per-language orthography reference;
                                      copy + fill in for each new language
agents/
  extraction-agent.md     the agent's operating loop/spec —
                          read this to run the pipeline end-to-end
                          (including the optional web-verify step)
  conventions-agent.md    sub-agent: analyzes book structure, updates
                          phonology ref, writes conventions file,
                          detects morphology rules (runs after profiling)
  correction-agent.md     sub-agent: validates translations, checks examples,
                          resolves homonyms, handles multi-sense entries
                          (runs after crosscheck/pattern-spot)
scripts/
  models.py             domain model: Language (fully configurable, no
                        Bahasa Indonesia default pivot), DictionaryEntry, FlaggedTerm (with
                        web-check hooks), PatternInsight, BookProfile,
                        ExtractionSession, QualityReport
  pdf_parser.py         detects digital-text vs image-PDF, extracts raw pages
                        (OCR via pytesseract, lang hint from Language.pivot_code);
                        also catches furniture-only text layers (headers/page
                        numbers over a scan) and OCRs those pages instead;
                        accepts a single PDF OR a folder of split PDFs
                        (parsed in natural order as one book)
  book_profiler.py      learns what the book IS before extraction: classifies
                        kind (dictionary / kids_picture_book / teaching_book /
                        grammar_morphology / mixed), splits front-matter /
                        body / back-matter zones, detects entry conventions,
                        suggests phonology-ref settings → book_profile.md
  conventions_extractor.py  analyzes dictionary pages for entry layout,
                        headword shapes, gloss format, cross-references;
                        suggests split/entry patterns for the phonology ref
  morphology_rules.py   detects and manages reduplication, affixation,
                        verb conjugation; finds root forms, cross-references
                        derived entries to their roots
  translation_checker.py  validates headword–gloss alignment, checks example
                        sentences, detects gloss language mismatches, builds
                        web search queries for verification
  homonym_resolver.py   detects homonyms vs. variant spellings, classifies
                        polysemy/homonym/ocr_variant/dialect_variant,
                        suggests merge/split actions
  entry_extractor.py    raw page text → DictionaryEntry objects
  typo_corrector.py     OCR-confusion + orthography-aware typo pass; flags
                        entries stuck across passes for optional web-check
  meaning_crosscheck.py cross-checks glosses against corpus + pivot language;
                        marks genuine conflicts/duplicates for web-check
  pattern_spotter.py    looks ACROSS flags for systematic issues (recurring
                        OCR substitutions, bad-scan page clusters, issue-type
                        hotspots) instead of treating every flag as isolated
  web_verification.py   builds the queue of flags worth a web search + records
                        the agent's findings back onto the flag (the script
                        itself never searches — see agent spec)
  quality_loop.py        orchestrates parse→extract→correct→crosscheck→
                        pattern-spot→write until convergence, updates
                        flagged_terms.md + pattern_insights.md
  corpus_writer.py      writes/appends JSONL corpus + markdown reports;
                        supports per-book subdirectories via book_id
  corpus_merger.py      merges per-book entries.jsonl into a single
                        language corpus; handles multi-sense merging,
                        cross-book conflicts, source_book tracking
  cli.py                entry point: extract (single book) or merge (all books)
  test_extract.py       helper for testing extraction patterns
docs/diagrams/
  pipeline.md           full extraction loop diagram (Mermaid)
  multi-book.md         multi-book workflow diagram
  agents.md             agent system diagram
  data-flow.md          input/output data flow diagram
.opencode/skills/
  conventions-management/  skill for the conventions agent: guides pattern
                          detection, phonology ref updates, conventions file
                          creation, morphology analysis
  linguistic-correction/  skill for the correction agent: guides translation
                          validation, homonym resolution, multi-sense handling,
                          web verification
assets/
  flagged_terms_template.md
  orthography_reference_template.md
```

## Workflow

1. **Set up the language.** Copy `references/phonology_template.md` to
   `outputs_<lang>/<lang>_phonology.md` (e.g. `outputs_sentani/sentani_phonology.md`) and fill in the orthography
   rules and known OCR pitfalls (see `references/quality_loop_guide.md` for
   what to include). Skip this step if the language already has one.

2. **Run the extraction loop.** Read `agents/extraction-agent.md` for the
   full operating loop, then either:
   - drive it yourself step-by-step using the `scripts/*.py` modules, or
   - invoke `scripts/cli.py` as a single command for a first full pass.

   The loop profiles the book first — cheaply: digital-text pages are
   scored for free and image pages are OCR'd only at ~24 evenly spaced
   sample points, so a 500-page scan is classified in minutes, not an
   hour (`book_profile.md`). It detects whether this is a standard
   dictionary, a kids' picture book, a teaching workbook/vocabulary list,
   or a grammar/morphology booklet — none of which follow the standard
   format — splits front-matter guides from the entry body, and suggests
   layout settings. Check its findings against real pages before trusting
   them; merge any suggestions into the phonology ref. Books with no
   dictionary-like body (workbooks, picture books) are left un-extracted
   rather than forced through headword–gloss parsing; full OCR runs only
   on the detected body zone.

   After profiling, the **conventions agent** (`agents/conventions-agent.md`)
   analyzes the book's actual entry layout, headword shapes, gloss format,
   and morphology rules. It updates the phonology reference with improved
   patterns and writes a conventions file for future runs. Load the
   `conventions-management` skill for guidance.

   After extraction and cross-checking, the **correction agent**
   (`agents/correction-agent.md`) validates translation accuracy, checks
   example sentences, resolves homonyms, and handles multi-sense entries.
   Load the `linguistic-correction` skill for guidance.

3. **Check pattern_insights.md before flagged_terms.md.** Each pass writes
   `pattern_insights.md` alongside the flags — if 8 flags all trace back to
   the same bad OCR substitution or the same faint scan page, that's one
   fix, not 8 reviews. Handle patterns first; they usually clear a chunk
   of `flagged_terms.md` on the next pass for free.

4. **Review remaining flags — web search where it helps.** Anything the
   loop can't resolve automatically (ambiguous OCR reads, conflicting
   glosses, low-confidence entries stuck across passes) stays in
   `flagged_terms.md` for review, never silently guessed into the corpus.
   Flags marked `needs_web_check` come with a ready-made `suggested_query`
   — as the agent, use `web_search` on genuinely ambiguous or conflicting
   records (e.g. two different glosses for the same headword) and record
   what you find via `WebVerificationQueue.record_evidence()`. Don't
   web-search everything reflexively — it's for cases where the pipeline
   itself can't adjudicate (meaning conflicts, duplicate headwords, or
   entries still low-confidence after 2+ correction passes), not routine
   OCR typos the confusion-pair pass already handles.

5. **Converge, don't just run once.** Re-run the loop after flags are
   resolved; `quality_loop.py` tracks a per-pass `QualityReport` and stops
   when a pass produces zero new flags (or `max_iterations` is hit —
   default 5). Read `references/quality_loop_guide.md` for the exact
   convergence + scoring rules before changing them.

6. **Output.** Structured JSONL parallel corpus, plus `book_profile.md`,
   `flagged_terms.md`, `pattern_insights.md`, and a per-run
   `quality_report_<n>.md` for traceability — all under
   `out/<language_code>/` so each language gets its own directory.

7. **Multi-book merging.** When extracting multiple dictionaries for the
   same language, each book gets its own subdirectory under
   `out/<lang>/books/<book_id>/`. After all books are extracted, merge
   them into a single language corpus:

   ```bash
   python scripts/cli.py merge --lang-code <lang>
   ```

   This produces `out/<lang>/corpus_<lang>.jsonl` with:
   - Same headword, same gloss → kept once (higher confidence wins)
   - Same headword, different gloss → merged into multi-sense entry
   - Same headword, conflicting glosses → flagged in `cross_book_conflicts.md`

   Every entry retains `source_book` and `source_page` for traceability.

   See detailed diagrams:
   - [Pipeline Workflow](docs/diagrams/pipeline.md)
   - [Multi-Book Workflow](docs/diagrams/multi-book.md)
   - [Agent System](docs/diagrams/agents.md)
   - [Data Flow](docs/diagrams/data-flow.md)

## Notes for extending to a new language

- Only a filled-in `phonology_template.md` and a `Language(...)` instance
  (code, name, family, pivot_code, pivot_name) are needed per language —
  every script reads these, none hardcodes a language pair. The CLI defaults
  to `pivot_code="ind"` and `pivot_name="Bahasa Indonesia"`; pass explicit
  pivot arguments when working with another gloss language.
- If the language is tonal or has diacritics the OCR engine mangles
  often, add those confusion pairs to the language's phonology file under
  `## OCR confusion pairs` — `typo_corrector.py` reads that section.

## Smart flagging vs. flooding a human with flags

- `pattern_spotter.py` runs after every pass and groups flags by shared
  root cause (same bad substitution, same troublesome page, one issue
  type dominating). Fixing the pattern's `suggested_action` often clears
  several flags in the next pass instead of resolving them one by one.
- `web_verification.py` only queues flags where a search plausibly
  resolves the ambiguity — genuine meaning conflicts, duplicate headwords
  with diverging glosses, or entries still low-confidence after multiple
  correction passes. It never fires for straightforward OCR-confusion
  fixes; those are handled deterministically by `typo_corrector.py`.
