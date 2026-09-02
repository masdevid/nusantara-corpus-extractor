# Conventions Management Skill

## When to Load

- After BookProfiler produces `book_profile.md`
- Before EntryExtractor runs for the first time on a new language
- When the existing phonology reference seems incomplete or wrong
- After the extraction agent finds that the split pattern produces bad chunks

## Purpose

This skill guides the **conventions agent** through analyzing a dictionary's
structure and updating persistent configuration files. The conventions agent
is the pipeline's memory — it learns patterns from each book and writes them
down for future runs.

## Workflow

### 1. Read Current State

```bash
# What does the profiler think this book looks like?
cat out/<lang>/book_profile.md

# What's already configured?
cat references/<lang>_phonology.md

# Is there an existing conventions file?
cat out/<lang>/conventions_<lang>.md
```

### 2. Sample Pages for Pattern Detection

Use `scripts/conventions_extractor.py` to analyze pages:

```python
from conventions_extractor import ConventionsExtractor
from pdf_parser import PDFParser

parser = PDFParser()
extractor = ConventionsExtractor()

# Parse 5-10 body pages
pages = [parser.parse_page(pdf, pg) for pg in body_pages[:10]]

# Extract conventions
conventions = extractor.extract(pages, profile)

# Get suggestions
split_pattern = extractor.suggest_split_pattern(conventions)
entry_pattern = extractor.suggest_entry_pattern(conventions)
```

### 3. Analyze Entry Layout

Key questions to answer:
- **How are entries separated?** Line-based, marker-based, or hybrid?
- **Where do entries start?** Line beginning, after a marker, after a POS code?
- **What does a headword look like?** Simple (1 word), compound (2+ words), hyphenated?
- **Are there multiple entries per line?** If so, what marks the boundary?

### 4. Analyze Gloss Format

Key questions:
- **Which languages?** Indonesian, English, or both?
- **Abbreviations?** n., v., adj., KS (lihat juga), etc.
- **Multi-sense format?** Numbered senses (1, 2, 3), semicolons, newlines?
- **Example sentences?** Inline, parenthesized, after a dash?

### 5. Detect Morphology

Use `scripts/morphology_rules.py` to analyze:

```python
from morphology_rules import MorphologyRules

rules = MorphologyRules()
findings = rules.analyze_entries(entries)

# Check for reduplication
is_redup, base = rules.is_reduplication("bo-bo")

# Strip affixes
root = rules.find_root("membaca")  # → "baca"
```

### 6. Write Updates

#### Phonology Reference
Update `references/<lang>_phonology.md` with:
- Improved `split_before` pattern (if found)
- Updated entry pattern (if headwords differ from default)
- New cross-reference markers (if found)
- Morphology rules section

#### Conventions File
Write `out/<lang>/conventions_<lang>.md` with:
- All detected patterns (not just what changed)
- Book-specific observations
- Morphology rules
- Homonym/variant pairs discovered

### 7. Verify

After updating, run a quick extraction test:

```bash
python3 scripts/cli.py extract \
    --pdf <pdf> \
    --book-id <book_id> \
    --lang-code <lang> --lang-name <Lang> --lang-family <Family> \
    --phonology references/<lang>_phonology.md
```

Check that:
- Entry count is reasonable (not 9 for 180 pages)
- Headwords look correct (not continuation text)
- Glosses are properly aligned
- No large chunks being skipped

## Helper Functions

These are reusable across languages:

### `ConventionsExtractor.extract(pages, profile)`
Analyzes raw pages and returns a conventions dict.

### `ConventionsExtractor.suggest_split_pattern(conventions)`
Returns a regex `split_before` pattern based on detected markers.

### `ConventionsExtractor.suggest_entry_pattern(conventions)`
Returns a regex entry pattern based on headword shapes.

### `MorphologyRules.from_conventions_file(text)`
Parses morphology section from a conventions markdown file.

### `MorphologyRules.analyze_entries(entries)`
Detects reduplication and affix patterns in extracted entries.

### `MorphologyRules.find_root(word)`
Strips affixes and returns the root form.

## Multi-Book Workflow

When extracting multiple dictionaries for the same language:

### Per-Book Conventions
Write to `out/<lang>/books/<book_id>/conventions_<book_id>.md`:
- Snapshot of THIS book's layout
- Read-only after creation (preserves original format)

### Cumulative Conventions
Maintain `out/<lang>/conventions_<lang>.md`:
- Patterns observed across ALL books
- Updated after each book extraction
- Contains: common headword shapes, shared abbreviations, morphology rules

### Before Extracting a New Book
```bash
# 1. Read cumulative conventions
cat out/<lang>/conventions_<lang>.md

# 2. Check what patterns are already known
# 3. Run conventions extraction on new book
# 4. Compare with cumulative patterns
# 5. Write per-book conventions + update cumulative
```

### Conventions File Template (Multi-Book)
```markdown
# <Language> Conventions (Cumulative)

Last updated: <date>
Books analyzed: <list of book IDs>

## Common Patterns
- Entry split mode: <mode> (consistent across books)
- Headword shape: <pattern>
- Gloss languages: <list>

## Book-Specific Notes
### <book_id>
- Split mode: <mode> (differs from common: <note>)
- Extra markers: <list>
```

## Anti-Patterns

- **Don't update the phonology ref unless you're >80% confident.** Ambiguous
  patterns go in the conventions file as notes, not as active config.
- **Don't assume the profiler's suggestions are correct.** Always verify
  against actual pages.
- **Don't create a new conventions file from scratch every time.** Read the
  existing one and update it incrementally.
- **Don't skip verification.** After updating patterns, always test extraction.
