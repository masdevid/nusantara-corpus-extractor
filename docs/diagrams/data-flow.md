# Data Flow

Inputs → Scripts → Outputs, and model relationships.

## Script Dependencies

```mermaid
flowchart LR
    subgraph Inputs["Inputs"]
        PDF["PDF / Scan"]
        PHON["phonology.md"]
        EXIST["existing corpus"]
    end

    subgraph Core["Core Scripts"]
        BP["book_profiler.py"]
        CE["conventions_extractor.py"]
        PDFP["pdf_parser.py"]
        EE["entry_extractor.py"]
        TC["typo_corrector.py"]
        MC["meaning_crosscheck.py"]
        PS["pattern_spotter.py"]
        CW["corpus_writer.py"]
        CM["corpus_merger.py"]
    end

    subgraph Correction["Correction Scripts"]
        MR["morphology_rules.py"]
        TC2["translation_checker.py"]
        HR["homonym_resolver.py"]
    end

    subgraph Outputs["Outputs"]
        PROF["book_profile.md"]
        CONV["conventions.md"]
        ENT["entries.jsonl"]
        CORP["corpus.jsonl"]
        FLAG["flagged_terms.md"]
        PAT["pattern_insights.md"]
        REP["quality_report_N.md"]
        CBC["cross_book_conflicts.md"]
    end

    PDF --> PDFP
    PDFP --> BP
    BP --> PROF
    PROF --> CE
    PHON --> CE
    CE --> CONV
    CONV --> EE
    PDFP --> EE
    EE --> TC
    TC --> MC
    MC --> PS
    PS --> MR
    MR --> TC2
    TC2 --> HR
    HR --> CW
    CW --> ENT
    ENT --> CM
    CM --> CORP
    PS --> FLAG
    PS --> PAT
    CW --> REP
    CM --> CBC

    style PDF fill:#fff3e0,stroke:#f57c00
    style PHON fill:#fff3e0,stroke:#f57c00
    style EXIST fill:#fff3e0,stroke:#f57c00
    style CORP fill:#e8f5e9,stroke:#388e3c
    style CONV fill:#e8f5e9,stroke:#388e3c
    style CBC fill:#ffebee,stroke:#d32f2f
```

## Model Relationships

```mermaid
classDiagram
    class Language {
        +code : str
        +name : str
        +family : str
        +pivot_code : str
        +pivot_name : str
    }

    class DictionaryEntry {
        +id : str
        +headword : str
        +part_of_speech : str
        +gloss_pivot : str
        +examples : list
        +page_ref : int
        +confidence : float
        +source_language : str
        +source_book : str
        +source_page : int
    }

    class FlaggedTerm {
        +entry_id : str
        +headword : str
        +issue_type : IssueType
        +note : str
        +raised_at_pass : int
        +resolved : bool
        +needs_web_check : bool
    }

    class BookProfile {
        +book_kind : str
        +front_matter_pages : list
        +body_pages : list
        +back_matter_pages : list
        +conventions : dict
    }

    class ExtractionSession {
        +language : Language
        +source_pdf : str
        +entries : list
        +flagged_terms : list
        +patterns : list
        +reports : list
        +profile : BookProfile
        +current_pass : int
    }

    class QualityReport {
        +pass_number : int
        +entries_in : int
        +entries_out : int
        +flags_raised : int
        +flags_resolved : int
        +converged : bool
    }

    Language "1" --> "*" ExtractionSession
    ExtractionSession "1" --> "*" DictionaryEntry
    ExtractionSession "1" --> "*" FlaggedTerm
    ExtractionSession "1" --> "*" QualityReport
    ExtractionSession "1" --> "0..1" BookProfile
```

## Output Directory Structure

```mermaid
flowchart TD
    OUT["out/"] --> LANG["shj/ — Sentani"]
    OUT --> LANG2["bhw/ — Biak"]
    OUT --> LANG3["lni/ — Lani"]

    LANG --> PHON["sentani_phonology.md"]
    LANG --> CONV_CUM["conventions_shj.md"]
    LANG --> CORP["corpus_shj.jsonl"]
    LANG --> CBC["cross_book_conflicts.md"]
    LANG --> BOOKS["books/"]

    BOOKS --> BK1["set/"]
    BOOKS --> BK2["sentani_kamus/"]

    BK1 --> BK1A["entries.jsonl"]
    BK1 --> BK1B["book_profile.md"]
    BK1 --> BK1C["conventions_set.md"]

    BK2 --> BK2A["entries.jsonl"]
    BK2 --> BK2B["book_profile.md"]
    BK2 --> BK2C["conventions_sentani_kamus.md"]

    style OUT fill:#f5f5f5
    style LANG fill:#e1f5fe
    style CORP fill:#e8f5e9
    style CONV_CUM fill:#e8f5e9
    style CBC fill:#ffebee
    style BOOKS fill:#fff3e0
```
