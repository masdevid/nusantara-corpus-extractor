# Contributing

Contributions are welcome. By submitting a contribution, you agree that it
may be distributed under the MIT License in `LICENSE`.

## What belongs in this repo

This repo ships as an **agent skills + sub-agents package**, not a plain
Python module. Keep changes focused on:

- The extraction pipeline (`scripts/*.py`) and its documentation
- The package skills (`.opencode/skills/conventions-management/`,
  `.opencode/skills/linguistic-correction/`)
- The agent specs (`agents/*.md`)
- The references, diagrams, and guides under `references/` and `docs/`

## What does NOT belong

- **Generic engineering skills** (code review, design philosophy, etc.) are
  harness-local and gitignored (`.opencode/skills/code-*/`). Do not commit
  them — they are not part of this package.
- **Harness scaffolding** (`.opencode/agents/`, `.opencode/commands/`,
  `opencode.json`, `ralph.sh`) is gitignored. Keep it local.
- Dictionary PDFs, private source material, generated corpora, OCR language
  data, credentials, or other files you do not have the right to redistribute.

## Before opening a change

- Keep changes focused on the extraction pipeline or its documentation.
- Preserve attribution and license notices for third-party dependencies.
- Run the available validation commands locally before submitting a change
  (e.g. `python -m py_compile scripts/*.py`).

## Licensing

The MIT License applies to original project materials. It does not change the
license of an input dictionary, OCR model, generated corpus, or dependency.
Contributors remain responsible for ensuring they have the right to submit
any content they add.
