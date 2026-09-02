# indo-corpus-extractor

Extracts structured parallel-corpus entries from local/low-resource-language
dictionary PDFs (scanned or digital) into a quality-checked JSONL corpus.
Language-agnostic by design; Bahasa Indonesia is the default pivot language.

Start with `SKILL.md` for the pipeline overview and
`agents/extraction-agent.md` for the operating loop.

## Agent skills

### Issue tracker

GitHub Issues on masdevid/nusantara-corpus-extractor via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
