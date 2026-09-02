# Pipeline Workflow

Full extraction loop — from PDF to quality-checked corpus.

```mermaid
flowchart TD
    A["PDF / Scan"] --> B["0. PROFILE\nBookProfiler"]
    B --> B5["0.5 CONVENTIONS\nConventions Agent"]
    B5 --> C["1. PARSE\nPDFParser"]
    C --> D["2. EXTRACT\nEntryExtractor"]
    D --> E["3. CORRECT\nTypoCorrector"]
    E --> F["4. CROSSCHECK\nMeaningCrossChecker"]
    F --> G["5. SPOT\nPatternSpotter"]
    G --> G5["5.5 CORRECTION\nCorrection Agent"]
    G5 --> H{"6. CONVERGED?"}
    H -->|"new_flags == 0\nor max_iterations"| I["8. WRITE\nCorpusWriter"]
    H -->|"flags remain"| J["7. WEB VERIFY\n(optional)"]
    J --> C

    I --> K["corpus.jsonl"]
    I --> L["flagged_terms.md"]
    I --> M["pattern_insights.md"]
    I --> N["quality_report_N.md"]

    style B5 fill:#e1f5fe,stroke:#0288d1
    style G5 fill:#e1f5fe,stroke:#0288d1
    style H fill:#fff3e0,stroke:#f57c00
    style I fill:#e8f5e9,stroke:#388e3c
```

## Steps

| Step | Script | Purpose |
|------|--------|---------|
| 0 | `book_profiler.py` | Classify book kind, split zones, detect conventions |
| 0.5 | `conventions_extractor.py` | Analyze entry layout, update phonology ref, write conventions |
| 1 | `pdf_parser.py` | Extract text from digital pages, OCR image pages |
| 2 | `entry_extractor.py` | Parse raw text into DictionaryEntry objects |
| 3 | `typo_corrector.py` | Fix OCR confusions, validate orthography |
| 4 | `meaning_crosscheck.py` | Cross-check glosses against corpus + pivot |
| 5 | `pattern_spotter.py` | Spot systematic issues across flags |
| 5.5 | `translation_checker.py`, `homonym_resolver.py`, `morphology_rules.py` | Validate translations, resolve homonyms, check morphology |
| 6 | `quality_loop.py` | Track convergence, write reports |
| 7 | (agent-driven) | Web search for genuinely ambiguous flags |
| 8 | `corpus_writer.py` | Write JSONL corpus + markdown reports |
