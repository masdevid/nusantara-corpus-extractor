# Nusantara Corpus PDF Extractor

Extracts structured parallel-corpus entries from local/low-resource-language
dictionary PDFs (scanned or digital) into a quality-checked JSONL corpus.
Language-agnostic by design; Bahasa Indonesia is the default pivot language.

## Quick Start

### Prerequisites

```bash
# Python 3.10+
pip install pytesseract Pillow

# Tesseract OCR (for scanned PDFs)
brew install tesseract
```

### First Extraction

```bash
# 1. Set up language (copy + fill in phonology reference)
cp references/phonology_template.md references/sentani_phonology.md
# Edit sentani_phonology.md with orthography rules and OCR confusion pairs

# 2. Extract a single book
python scripts/cli.py extract \
    --pdf "dictionaries/Set-Kamus-Sentani-Indonesia-Inggris-2.pdf" \
    --book-id set \
    --lang-code shj --lang-name Sentani --lang-family "Trans-New Guinea" \
    --phonology references/sentani_phonology.md

# 3. Check output
cat out/shj/books/set/entries.jsonl
cat out/shj/books/set/book_profile.md
cat out/shj/books/set/flagged_terms.md
```

### Merge Multiple Books

```bash
# After extracting multiple books for the same language:
python scripts/cli.py extract --pdf "Kamus Bahasa Sentani.pdf" --book-id kamus ...
python scripts/cli.py merge --lang-code shj

# Check merged corpus
cat out/shj/corpus_shj.jsonl
cat out/shj/cross_book_conflicts.md
```

## Architecture

The pipeline runs a **loop**, not a single pass — it iterates until
convergence (zero new flags) or a maximum iteration count is hit.

![Pipeline Overview](docs/diagrams/pipeline.md)

See detailed diagrams:
- [Multi-Book Workflow](docs/diagrams/multi-book.md) — extracting multiple
  dictionaries for one language
- [Agent System](docs/diagrams/agents.md) — how the three agents interact
- [Data Flow](docs/diagrams/data-flow.md) — inputs, scripts, outputs

### The Loop

```
0.  PROFILE       classify book kind, detect zones, suggest settings
0.5 CONVENTIONS   analyze entry layout, update phonology ref (sub-agent)
1.  PARSE         extract text from digital/OCR pages
2.  EXTRACT       parse raw text into DictionaryEntry objects
3.  CORRECT       fix OCR confusions, validate orthography
4.  CROSSCHECK    cross-check glosses against corpus + pivot
5.  SPOT          spot systematic issues across flags
5.5 CORRECTION    validate translations, resolve homonyms (sub-agent)
6.  REPORT        track convergence, write quality report
7.  WEB VERIFY    (optional) search for genuinely ambiguous flags
8.  WRITE         output JSONL corpus + markdown reports
```

### Three Agents

| Agent | Role | Runs |
|-------|------|------|
| **Extraction Agent** | Orchestrator — runs the full loop | Every pass |
| **Conventions Agent** | Memory — learns book structure, updates config | After profiling (step 0.5) |
| **Correction Agent** | Linguist — validates meaning, resolves ambiguity | After crosscheck (step 5.5) |

## Configuration

### Language Setup

Each language needs:
1. A `Language` config (code, name, family, pivot_code, pivot_name)
2. A phonology reference file (`references/<lang>_phonology.md`)

```python
from models import Language

sentani = Language(
    code="shj",
    name="Sentani",
    family="Trans-New Guinea",
    pivot_code="ind",           # tesseract lang code for gloss language
    pivot_name="Bahasa Indonesia",
)
```

### Phonology Reference

Copy the template and fill in orthography rules:

```bash
cp references/phonology_template.md references/sentani_phonology.md
```

Key sections:
- **Entry splitting** — regex pattern to cut entries in the text layer
- **Entry pattern** — regex to match a valid headword + gloss
- **Valid characters** — character set for headwords
- **OCR confusion pairs** — known OCR errors for this language
- **Morphology rules** — reduplication, affixes, verb forms

### Pivot Language

Bahasa Indonesia is the default pivot. Override with:

```bash
--pivot-code eng --pivot-name "English"
```

## Multi-Book Workflow

When extracting multiple dictionaries for the same language:

### Directory Structure

```
out/
  shj/                                    # Language level
    sentani_phonology.md                   # Shared orthography reference
    conventions_shj.md                     # Cumulative conventions
    corpus_shj.jsonl                       # Merged corpus from all books
    cross_book_conflicts.md                # Conflicting headwords
    books/
      set/                                # Book: "Set Kamus Sentani"
        entries.jsonl
        book_profile.md
        flagged_terms.md
        conventions_set.md
      sentani_kamus/                       # Book: "Kamus Bahasa Sentani"
        entries.jsonl
        book_profile.md
        conventions_sentani_kamus.md
```

### Step-by-Step

```bash
# 1. Extract each book with --book-id
python scripts/cli.py extract \
    --pdf "dictionaries/Set-Kamus-Sentani.pdf" \
    --book-id set \
    --lang-code shj --lang-name Sentani \
    --phonology references/sentani_phonology.md

python scripts/cli.py extract \
    --pdf "dictionaries/Kamus Bahasa Sentani.pdf" \
    --book-id kamus \
    --lang-code shj --lang-name Sentani \
    --phonology references/sentani_phonology.md

# 2. Merge into single language corpus
python scripts/cli.py merge --lang-code shj

# 3. Resolve cross-book conflicts (if any)
# Edit out/shj/cross_book_conflicts.md, then re-run merge
```

### Merge Rules

| Scenario | Action |
|----------|--------|
| Same headword, same gloss | Keep one (higher confidence wins) |
| Same headword, similar gloss (>80% overlap) | Merge, keep longer gloss |
| Same headword, different gloss | Merge into multi-sense entry |
| Same headword, conflicting glosses | Flag in `cross_book_conflicts.md` |

### Conventions System

**Per-book** (`books/<book_id>/conventions_<book_id>.md`):
- Snapshot of what THIS book looks like
- Read-only after creation (preserves original format)

**Cumulative** (`out/<lang>/conventions_<lang>.md`):
- Patterns observed across ALL books for this language
- Updated after each book extraction
- Informs the conventions agent when extracting a new book

## Multi-Language Projects

### Directory Structure

```
out/
  shj/                  # Sentani
    corpus_shj.jsonl
    books/
      set/
      kamus/
  bhw/                  # Biak
    corpus_bhw.jsonl
    books/
      kamus_biak/
  lni/                  # Lani
    corpus_lni.jsonl
    books/
      kamus_lani_wone/
      kamus_lengkap_lani/
```

### Cross-Language Considerations

- Each language has its own phonology reference, conventions, and corpus
- The phonology reference is per-language (different orthography rules)
- The pivot language is configurable per language (Indonesian, English, etc.)
- There is no cross-language merging — each language produces an independent corpus

## Output Format

### JSONL Corpus

Each line is a dictionary entry:

```json
{
  "id": "a1b2c3d4",
  "headword": "bo",
  "pos": "n",
  "gloss_pivot": "(1) pohon; (2) kayu",
  "examples": ["bo fau ...", "bo siro ..."],
  "page_ref": 42,
  "confidence": 0.95,
  "source_language": "shj",
  "source_book": "set",
  "source_page": 42
}
```

### Report Files

| File | Content |
|------|---------|
| `book_profile.md` | Book kind, page zones, conventions detected |
| `flagged_terms.md` | Open/resolved flags with web evidence |
| `pattern_insights.md` | Systematic issues across flags |
| `quality_report_N.md` | Per-pass stats (entries in/out, flags, convergence) |
| `cross_book_conflicts.md` | Conflicting headwords across books |

## Reference

### Scripts

| Script | Purpose |
|--------|---------|
| `scripts/models.py` | Domain model (Language, DictionaryEntry, FlaggedTerm, etc.) |
| `scripts/pdf_parser.py` | PDF parsing, digital/OCR page detection |
| `scripts/book_profiler.py` | Book classification, zone splitting |
| `scripts/conventions_extractor.py` | Entry layout analysis, pattern detection |
| `scripts/morphology_rules.py` | Reduplication, affix detection, root finding |
| `scripts/translation_checker.py` | Gloss validation, example checking |
| `scripts/homonym_resolver.py` | Homonym/variant classification |
| `scripts/entry_extractor.py` | Raw text → DictionaryEntry objects |
| `scripts/typo_corrector.py` | OCR confusion fixing |
| `scripts/meaning_crosscheck.py` | Gloss cross-checking |
| `scripts/pattern_spotter.py` | Systematic issue detection |
| `scripts/web_verification.py` | Web search queue management |
| `scripts/quality_loop.py` | Loop orchestrator, convergence logic |
| `scripts/corpus_writer.py` | JSONL + markdown output |
| `scripts/corpus_merger.py` | Multi-book corpus merging |
| `scripts/cli.py` | CLI entry point (extract/merge) |

### Agent Specifications

| Agent | File | Purpose |
|-------|------|---------|
| Extraction Agent | `agents/extraction-agent.md` | Full loop orchestration |
| Conventions Agent | `agents/conventions-agent.md` | Book structure analysis |
| Correction Agent | `agents/correction-agent.md` | Linguistic validation |

### Skills

| Skill | File | Purpose |
|-------|------|---------|
| Conventions Management | `.opencode/skills/conventions-management/SKILL.md` | Pattern detection, conventions workflow |
| Linguistic Correction | `.opencode/skills/linguistic-correction/SKILL.md` | Translation validation, homonym resolution |

## Extending

### Adding a New Language

1. Create a `Language` instance:
   ```python
   Language(code="xyz", name="XYZ", family="Austronesian",
            pivot_code="ind", pivot_name="Bahasa Indonesia")
   ```
2. Copy and fill in `references/phonology_template.md` → `references/<lang>_phonology.md`
3. Run extraction with `--lang-code xyz`

### Adding a New Dictionary

1. Place the PDF in `dictionaries/`
2. Run extraction with `--book-id <descriptive_id>`
3. Merge into the language corpus

### Customizing Morphology Rules

Edit the conventions file or phonology reference to add language-specific
affix patterns, reduplication rules, or verb conjugation patterns.

### Contributing

See `docs/` for architecture diagrams, `AGENTS.md` for agent guidelines.
