# Nusantara Corpus PDF Extractor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

A language-agnostic pipeline for turning dictionaries from 700+ Nusantara and
other local languages into quality-checked Bahasa Indonesia parallel corpora.
It parses digital text or OCR, extracts entries, applies conservative
orthography-aware corrections, cross-checks meanings, spots recurring
problems, and produces review reports.

## Install

Install the Python CLI from PyPI after a release:

```sh
python3 -m pip install nusantara-corpus-extractor
```

Or install it as a uv-managed command:

```sh
uv tool install nusantara-corpus-extractor
```

## What is licensed

The original source code, agent skill definition, templates, references, and
documentation in this repository are released under the MIT License. See
[LICENSE](LICENSE) and [NOTICE](NOTICE).

The MIT License does not cover:

- Dictionary PDFs, scans, text, glosses, or other source material supplied by
  a user or included in a downstream project.
- Generated corpora or OCR language data whose terms come from another owner.
- Third-party software and libraries, which retain their own licenses.

You are responsible for confirming that you may process and redistribute the
source dictionary and resulting corpus.

## Dependency licensing

The parser uses `pypdfium2` for digital PDF text extraction and page rendering.
`pypdfium2` is distributed under Apache-2.0/BSD-3-Clause terms and includes
PDFium binaries and related dependency notices. The project MIT license does
not relicense those dependencies; preserve the notices for any redistributed
binary wheels. See the [pypdfium2 licensing documentation](https://pypdfium2.readthedocs.io/en/stable/license.html).

The other declared Python libraries are separate dependencies and retain their
own licenses. Keep their notices when redistributing installed or vendored
copies.

## Requirements

- Python 3.10 or newer is recommended.
- Tesseract OCR must be installed and available as `tesseract` for scanned PDFs.
  On macOS: `brew install tesseract`.
- Python dependencies:

  ```sh
  python3 -m pip install -e .
  ```

  Install the Tesseract language data needed by the dictionary's pivot
  language separately.

## Quick start

Create a language-specific phonology file from the reference template and
fill in its valid characters and OCR confusion pairs:

```sh
cp references/phonology_template.md lani_phonology.md
```

Run the installed command:

```sh
nusantara-corpus-extractor \
  --pdf path/to/dictionary.pdf \
  --lang-code lni \
  --lang-name Lani \
  --lang-family "Trans-New Guinea" \
  --pivot-code ind \
  --pivot-name "Bahasa Indonesia" \
  --phonology lani_phonology.md \
  --output-dir outputs
```

Optional existing-corpus checking:

```sh
  --existing-corpus ../path/to/existing.jsonl
```

The output directory contains the JSONL corpus, flagged terms, pattern
insights, and per-pass quality reports. Review unresolved flags before using
the corpus for training or redistribution.

## Repository layout

- `SKILL.md`: agent entry point and operating guidance.
- `agents/`: detailed agent workflow.
- `references/`: quality and orthography guidance.
- `assets/`: output templates.
- `scripts/`: parser, extractor, correction, validation, and writer modules.
- `pyproject.toml`: package metadata and CLI entry point.
- `outputs/`: local generated output; ignored by Git.

## Development checks

Compile the Python modules after changes:

```sh
python3 -m compileall -q scripts
```

There is currently no automated test suite. Add focused tests around parser,
extraction, correction, and reconciliation behavior as those interfaces
stabilize.

## Git publishing checklist

Before the first public push:

1. Replace the copyright holder text in `LICENSE` and `NOTICE` with the legal
   copyright holder's name.
2. Review every input dictionary, model, and generated corpus for permission
   to redistribute.
3. Confirm the `pypdfium2` wheel and PDFium dependency notices are included.
4. Run the compilation check and inspect `git diff --check`.
5. Make a small initial commit containing only intended project files.
6. Tag a release after the licensing and dependency review is complete.

MIT grants broad copyright permissions but does not provide a patent license.
If patent protection matters, obtain professional advice and file before a
public disclosure where applicable.
