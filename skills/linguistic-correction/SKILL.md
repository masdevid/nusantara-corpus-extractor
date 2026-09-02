# Linguistic Correction Skill

## When to Load

- After MeaningCrossChecker and PatternSpotter (steps 4-5 in the quality loop)
- When `duplicate_headword` or `meaning_conflict` flags dominate
- When the extraction agent finds entries with wrong glosses
- When homonyms or variant spellings need resolution

## Purpose

This skill guides the **correction agent** through validating translation
accuracy, checking example sentences, resolving homonyms, and handling
multi-sense entries. The correction agent is the pipeline's linguist — it
understands the language's structure and ensures the extracted data is correct.

## Workflow

### 1. Read Current State

```bash
# What flags need attention?
cat out/<lang>/flagged_terms.md

# What patterns were spotted?
cat out/<lang>/pattern_insights.md

# What conventions apply?
cat out/<lang>/conventions_<lang>.md

# What does the phonology reference say?
cat references/<lang>_phonology.md
```

### 2. Classify Flags

Group flags by correction type:

| Type | Description | Tool |
|------|-------------|------|
| `translation_accuracy` | Gloss doesn't match headword meaning | `TranslationChecker` |
| `example_review` | Example sentence is garbled or wrong | `TranslationChecker` |
| `homonym_variant` | Same spelling, different words | `HomonymResolver` |
| `multi_sense` | One entry should be two | `HomonymResolver` |
| `morphology_fix` | Affixed form treated as separate entry | `MorphologyRules` |
| `cross_ref` | Cross-reference points to non-existent entry | Manual review |

### 3. Translation Accuracy

Use `scripts/translation_checker.py`:

```python
from translation_checker import TranslationChecker

checker = TranslationChecker(gloss_language="indonesian")

# Check all entries
flags = checker.check_entries(entries)

# Build web query for a specific entry
query = checker.build_web_query(entry)
# → '"bo" arti bahasa Indonesia OR "bo" meaning'
```

**Web search protocol:**
1. Build query with `build_web_query()`
2. Run `web_search(query)`
3. Record evidence on the flag
4. If evidence is conclusive → mark `resolved`
5. If ambiguous → keep flag open with evidence attached

### 4. Homonym Resolution

Use `scripts/homonym_resolver.py`:

```python
from homonym_resolver import HomonymResolver

resolver = HomonymResolver()

# Analyze all entries
analysis = resolver.analyze(entries)

# Check against known homonyms
flags = resolver.check_conventions(entries, known_homonyms=[("bo", "bo")])
```

**Decision framework:**
- **Polysemy** (same word, related meanings) → merge with sense markers
- **Homonym** (different words, same spelling) → keep separate
- **OCR variant** (same word, different spelling) → merge, keep better form
- **Dialect variant** (same word, regional spelling) → keep separate, cross-ref

### 5. Multi-Sense Entries

When one extracted "entry" contains multiple glosses:

1. **Identify sense boundaries:** numbered markers (1, 2, 3), semicolons, newlines
2. **Split into separate senses:** each sense gets its own entry
3. **Add sense numbers:** `(1)` before each sense
4. **Verify each sense:** does it have its own example?

### 6. Morphology Fixes

Use `scripts/morphology_rules.py`:

```python
from morphology_rules import MorphologyRules

rules = MorphologyRules()

# Find root of an entry
root = rules.find_root("membaca")  # → "baca"

# Check if entry is a derived form
findings = rules.analyze_entries(entries)
# → [{"type": "prefix", "derived_form": "membaca", "root": "baca", "action": "flag_as_variant"}]
```

**Decision framework:**
- **Reduplication** → keep as separate entry (changes meaning)
- **Prefix** → flag as variant, check if meaning changes
- **Suffix** → cross-reference to root (usually just conjugation)
- **Circumfix** → flag as variant, check if meaning changes

### 7. Apply Corrections

After analysis, write corrections back:

```python
# Mark flags resolved
flag.resolved = True
flag.resolution_note = "Corrected via web verification: ..."

# Update entries
entry.headword = corrected_headword
entry.gloss_pivot = corrected_gloss

# Create new flags for newly discovered issues
new_flag = FlaggedTerm(
    entry_id=entry.id,
    headword=entry.headword,
    issue_type=IssueType.MEANING_CONFLICT,
    note="Newly discovered issue: ...",
    raised_at_pass=current_pass,
)
```

### 8. Update Conventions

Write discoveries to conventions file:

```python
# From homonym analysis
section = resolver.as_conventions_section(analysis)
# → "## Homonyms and Variants\n### Polysemy\n- bo: ..."

# From morphology analysis
section = rules.as_conventions_section()
# → "## Morphology\n- Prefixes: meN-, peN-..."
```

## Helper Functions

### `TranslationChecker`
- `check_entries(entries)` → flags for translation issues
- `build_web_query(entry)` → search query for web verification

### `HomonymResolver`
- `analyze(entries)` → classification of homonyms/variants
- `check_conventions(entries, known_homonyms)` → flags for convention violations
- `as_conventions_section(results)` → markdown for conventions file

### `MorphologyRules`
- `from_conventions_file(text)` → parse morphology from conventions
- `analyze_entries(entries)` → morphology findings
- `find_root(word)` → strip affixes, return root
- `find_derived_forms(root)` → all derived forms of a root

## Multi-Book Conflict Handling

When extracting multiple dictionaries for the same language:

### Cross-Book Duplicate Detection
Before correcting a headword, check the merged corpus:
```bash
# Check if headword exists from another book
grep '"headword": "bo"' out/shj/corpus_shj.jsonl
```

### Cross-Book Conflict Resolution
When same headword has different glosses across books:

| Scenario | Action |
|----------|--------|
| Same gloss | Keep one (higher confidence wins) |
| Similar gloss (>80% overlap) | Merge, keep longer gloss |
| Different gloss | Create multi-sense entry (1) gloss_A (2) gloss_B |
| Conflicting gloss | Flag in `cross_book_conflicts.md` |

### Merge into Multi-Sense Entry
```python
# When merging entries from different books
glosses = [
    "(1) pohon [from set]",
    "(2) kayu [from kamus]"
]
merged.gloss_pivot = "; ".join(glosses)
merged.source_book = "set,kamus"
```

### Cross-Book Conflict File
Edit `out/<lang>/cross_book_conflicts.md` to resolve:
```markdown
| Headword | Glosses | Books | Action |
|---|---|---|---|
| bo | pohon vs. kayu | set, kamus | merged as multi-sense |
| si | air vs. tahu | set, kamus | _resolve_ |
```

## Anti-Patterns

- **Don't silently merge.** When in doubt, flag it — don't guess.
- **Don't impose sense-marking schemes.** Follow the dictionary's own convention.
- **Don't merge homonyms.** Same spelling ≠ same word. Check glosses first.
- **Don't skip web verification.** Partial evidence still helps the next reviewer.
- **Don't forget to update conventions.** Every discovery goes in the file.
