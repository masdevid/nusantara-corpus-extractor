# Multi-Book Workflow

Extracting multiple dictionaries for one language, then merging into a single corpus.

```mermaid
flowchart TD
    subgraph "Book A Extraction"
        A1["PDF: Set Kamus Sentani"] --> A2["Profile + Conventions"]
        A2 --> A3["Extract entries"]
        A3 --> A4["Quality loop"]
        A4 --> A5["entries_A.jsonl"]
        A4 --> A6["conventions_A.md"]
    end

    subgraph "Book B Extraction"
        B1["PDF: Kamus Bahasa Sentani"] --> B2["Profile + Conventions"]
        B2 --> B3["Extract entries"]
        B3 --> B4["Quality loop"]
        B4 --> B5["entries_B.jsonl"]
        B4 --> B6["conventions_B.md"]
    end

    subgraph "Language Level (shj)"
        P["Phonology Ref"] --> M["corpus_merger.py"]
        A5 --> M
        B5 --> M
        A6 --> C["Cumulative Conventions"]
        B6 --> C
        M --> CORP["corpus_shj.jsonl"]
        M --> CONFLICT["cross_book_conflicts.md"]
    end

    style P fill:#fff3e0,stroke:#f57c00
    style C fill:#e8f5e9,stroke:#388e3c
    style CORP fill:#e8f5e9,stroke:#388e3c
    style CONFLICT fill:#ffebee,stroke:#d32f2f
```

## Merge Rules

| Scenario | Action |
|----------|--------|
| Same headword, same gloss | Keep one (higher confidence wins) |
| Same headword, different gloss | Merge into multi-sense entry with numbered senses |
| Same headword, conflicting glosses | Flag in `cross_book_conflicts.md` for human review |

## Merged Entry Format

```json
{
  "headword": "bo",
  "gloss_pivot": "(1) pohon; (2) kayu; (3) hutan",
  "source_book": ["set", "sentani_kamus"],
  "examples": ["bo fau ...", "bo siro ..."],
  "confidence": 0.92
}
```

## Conventions Flow

```mermaid
flowchart LR
    subgraph "Per-Book"
        BA["Book A conventions"] --> |snapshot| CA["conventions_A.md"]
        BB["Book B conventions"] --> |snapshot| CB["conventions_B.md"]
    end

    subgraph "Cumulative"
        CA --> |accumulate| CC["conventions_shj.md"]
        CB --> |accumulate| CC
        CC --> |update| PHON["Phonology Ref"]
    end

    style CA fill:#e1f5fe
    style CB fill:#e1f5fe
    style CC fill:#e8f5e9
    style PHON fill:#fff3e0
```
