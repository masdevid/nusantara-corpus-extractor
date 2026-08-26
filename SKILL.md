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
agents/extraction-agent.md         ← the agent's operating loop/spec —
                                      read this to run the pipeline end-to-end
                                      (including the optional web-verify step)
scripts/
  models.py             domain model: Language (fully configurable, no
                        Bahasa Indonesia default pivot), DictionaryEntry, FlaggedTerm (with
                        web-check hooks), PatternInsight, BookProfile,
                        ExtractionSession, QualityReport
  pdf_parser.py         detects digital-text vs image-PDF, extracts raw pages
                        (OCR via pytesseract, lang hint from Language.pivot_code);
                        also catches furniture-only text layers (headers/page
                        numbers over a scan) and OCRs those pages instead
  book_profiler.py      learns what the book IS before extraction: classifies
                        kind (dictionary / kids_picture_book / teaching_book /
                        grammar_morphology / mixed), splits front-matter /
                        body / back-matter zones, detects entry conventions,
                        suggests phonology-ref settings → book_profile.md
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
  corpus_writer.py      writes/appends JSONL corpus + markdown reports
  cli.py                entry point wiring the above together
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

   The loop profiles the book first (`book_profiler.py` → 
   `book_profile.md`): it detects whether this is a standard dictionary,
   a kids' picture book, a teaching workbook, or a grammar/morphology
   booklet — none of which follow the standard format — splits
   front-matter guides from the entry body, and suggests layout settings.
   Check its findings against real pages before trusting them; merge any
   suggestions into the phonology ref. Books with no dictionary-like body
   (workbooks, picture books) are left un-extracted rather than forced
   through headword–gloss parsing.

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

6. **Output.** Structured JSONL parallel corpus, plus `flagged_terms.md`,
   `pattern_insights.md`, and a per-run `quality_report_<n>.md` for
   traceability.

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
