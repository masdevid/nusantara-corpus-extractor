# Agent System

Three agents working together in the extraction pipeline.

```mermaid
flowchart TD
    subgraph EA["Extraction Agent (orchestrator)"]
        direction TB
        S0["0. PROFILE"] --> S05["0.5 CONVENTIONS"]
        S05 --> S1["1. PARSE"]
        S1 --> S2["2. EXTRACT"]
        S2 --> S3["3. CORRECT"]
        S3 --> S4["4. CROSSCHECK"]
        S4 --> S5["5. SPOT"]
        S5 --> S55["5.5 CORRECTION"]
        S55 --> S6["6. REPORT"]
    end

    subgraph CA["Conventions Agent"]
        direction TB
        CA1["Read book_profile.md"] --> CA2["Sample 3-5 body pages"]
        CA2 --> CA3["Detect patterns"]
        CA3 --> CA4["Verify against 2-3 more pages"]
        CA4 --> CA5["Update phonology ref"]
        CA5 --> CA6["Write conventions file"]
    end

    subgraph CO["Correction Agent"]
        direction TB
        CO1["Load flags + patterns + conventions"] --> CO2["Translation check"]
        CO2 --> CO3["Homonym resolution"]
        CO3 --> CO4["Morphology check"]
        CO4 --> CO5["Web verify"]
        CO5 --> CO6["Apply corrections"]
    end

    S05 -.->|"sub-agent call"| CA1
    S55 -.->|"sub-agent call"| CO1

    CA6 -.->|"updated phonology ref"| S1
    CO6 -.->|"corrected entries"| S6

    style S05 fill:#e1f5fe,stroke:#0288d1
    style S55 fill:#e1f5fe,stroke:#0288d1
    style CA1 fill:#e1f5fe,stroke:#0288d1
    style CO1 fill:#e1f5fe,stroke:#0288d1
    style S6 fill:#e8f5e9,stroke:#388e3c
```

## Agent Responsibilities

### Extraction Agent
- **Role:** Orchestrator — runs the full loop, tracks convergence
- **Runs:** Every pass (steps 0-8)
- **Owns:** Quality loop, pass counting, convergence logic

### Conventions Agent
- **Role:** Memory — learns book structure, updates config
- **Runs:** After profiling (step 0.5), on first extraction of a new book
- **Owns:** Phonology ref updates, conventions file, morphology rules
- **Persists:** Per-book conventions snapshot + cumulative language conventions

### Correction Agent
- **Role:** Linguist — validates meaning, resolves ambiguity
- **Runs:** After crosscheck/pattern-spot (step 5.5), when flags remain
- **Owns:** Translation accuracy, homonym resolution, morphology fixes
- **Persists:** Corrected entries, resolved flags, cross-book conflicts

## Data Sharing

```mermaid
flowchart LR
    subgraph Writes["Conventions Agent writes"]
        P["Phonology Ref"]
        CV["Conventions File"]
    end

    subgraph Reads["Correction Agent reads"]
        F["Flagged Terms"]
        PI["Pattern Insights"]
        CV2["Conventions File"]
    end

    subgraph Out["Correction Agent writes"]
        CE["Corrected Entries"]
        RF["Resolved Flags"]
        CB["Cross-Book Conflicts"]
    end

    CV --> CV2
    P -.->|"improved patterns"| EXTRACT["EntryExtractor"]
    CE -.->|"fixed entries"| WRITE["CorpusWriter"]

    style P fill:#fff3e0
    style CV fill:#e8f5e9
    style CV2 fill:#e8f5e9
    style CE fill:#e8f5e9
```
