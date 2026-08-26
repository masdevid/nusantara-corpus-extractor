"""
CLI entry point. 🎬

Example (Lani → Bahasa Indonesia):
    python cli.py \\
        --pdf lani_dictionary_scan.pdf \\
        --lang-code lni --lang-name Lani --lang-family "Trans-New Guinea" \\
        --pivot-code ind --pivot-name "Bahasa Indonesia" \\
        --phonology lani_phonology.md \\
        --output-dir outputs/ \\
        --existing-corpus lani_dictionary.jsonl

--pdf accepts a single PDF or a folder of split PDFs (one file per page
range) — folders are expanded in natural filename order and parsed as one
book. Bahasa Indonesia is the default pivot; pass --pivot-* to use another
gloss language. Swap --lang-* for a different source language as needed.
"""

from __future__ import annotations

import argparse
import json
import logging

from models import ExtractionSession, Language
from quality_loop import DEFAULT_MAX_ITERATIONS, QualityLoop
from web_verification import WebVerificationQueue

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S"
)


def load_existing_corpus(path: str | None):
    if not path:
        return None
    from models import DictionaryEntry

    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            entries.append(
                DictionaryEntry(
                    id=row.get("id", ""),
                    headword=row["headword"],
                    part_of_speech=row.get("pos"),
                    gloss_pivot=row["gloss_pivot"],
                    examples=row.get("examples", []),
                    page_ref=row.get("page_ref"),
                    confidence=row.get("confidence", 1.0),
                    source_language=row.get("source_language", ""),
                )
            )
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Nusantara Corpus PDF Extraction loop 📖")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--lang-code", required=True)
    parser.add_argument("--lang-name", required=True)
    parser.add_argument("--lang-family", required=True)
    parser.add_argument(
        "--pivot-code", default="ind", help="tesseract lang code (default: ind)"
    )
    parser.add_argument(
        "--pivot-name", default="Bahasa Indonesia", help="display name (default: Bahasa Indonesia)"
    )
    parser.add_argument("--phonology", required=True)
    parser.add_argument("--output-dir", default="out")
    parser.add_argument("--existing-corpus", default=None)
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    args = parser.parse_args()

    language = Language(
        code=args.lang_code,
        name=args.lang_name,
        family=args.lang_family,
        pivot_code=args.pivot_code,
        pivot_name=args.pivot_name,
    )
    session = ExtractionSession(language=language, source_pdf=args.pdf)

    loop = QualityLoop(
        session=session,
        phonology_path=args.phonology,
        output_dir=args.output_dir,
        max_iterations=args.max_iterations,
    )
    existing_corpus = load_existing_corpus(args.existing_corpus)
    loop.run(existing_corpus=existing_corpus)

    open_flags = session.open_flags()
    web_pending = WebVerificationQueue(session).build_queue()

    if web_pending:
        print(
            f"\n🌐 {len(web_pending)} flag(s) are queued for optional web "
            f"verification — hand these to an agent with web_search access, "
            f"or resolve manually in flagged_terms.md."
        )
    if open_flags:
        print(f"🚩 {len(open_flags)} flagged term(s) total need review — see flagged_terms.md")
    else:
        print("\n🎉 Clean pass — no open flags.")

    if session.patterns:
        print(f"🧠 {len(session.patterns)} pattern(s) spotted — see pattern_insights.md")


if __name__ == "__main__":
    main()
