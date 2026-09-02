"""
CLI entry point. 🎬

Single book extraction:
    python cli.py \\
        --pdf "Set-Kamus-Sentani-Indonesia-Inggris-2.pdf" \\
        --book-id set \\
        --lang-code shj --lang-name Sentani --lang-family "Trans-New Guinea" \\
        --phonology references/sentani_phonology.md

Merge all books for a language:
    python cli.py --merge --lang-code shj

--pdf accepts a single PDF or a folder of split PDFs (one file per page
range) — folders are expanded in natural filename order and parsed as one
book. Bahasa Indonesia is the default pivot; pass --pivot-* to use another
gloss language. Swap --lang-* for a different source language as needed.
"""

from __future__ import annotations

import argparse
import json
import logging
import os

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
                    source_book=row.get("source_book", ""),
                    source_page=row.get("source_page"),
                )
            )
    return entries


def infer_book_id(pdf_path: str) -> str:
    """Derive a book ID from the PDF filename."""
    name = os.path.splitext(os.path.basename(pdf_path))[0]
    # Clean up: lowercase, replace spaces/special chars with underscores
    book_id = name.lower().replace(" ", "_").replace("-", "_")
    # Remove consecutive underscores
    while "__" in book_id:
        book_id = book_id.replace("__", "_")
    return book_id.strip("_")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Nusantara Corpus PDF Extraction 📖"
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- extract (default) ---
    extract = subparsers.add_parser("extract", help="Extract entries from a dictionary PDF")
    extract.add_argument("--pdf", required=True, help="Path to dictionary PDF or folder of split PDFs")
    extract.add_argument("--book-id", default=None, help="Book identifier (derived from PDF name if omitted)")
    extract.add_argument("--lang-code", required=True, help="Language code (e.g. shj)")
    extract.add_argument("--lang-name", required=True, help="Language name (e.g. Sentani)")
    extract.add_argument("--lang-family", required=True, help="Language family (e.g. Trans-New Guinea)")
    extract.add_argument("--pivot-code", default="ind", help="tesseract lang code for gloss language (default: ind)")
    extract.add_argument("--pivot-name", default="Bahasa Indonesia", help="Gloss language name (default: Bahasa Indonesia)")
    extract.add_argument("--phonology", required=True, help="Path to phonology reference")
    extract.add_argument("--output-dir", default="out", help="Output directory (default: out/)")
    extract.add_argument("--existing-corpus", default=None, help="Prior corpus for cross-checking")
    extract.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)

    # --- merge ---
    merge = subparsers.add_parser("merge", help="Merge all books for a language into one corpus")
    merge.add_argument("--lang-code", required=True, help="Language code to merge")
    merge.add_argument("--output-dir", default="out", help="Output directory (default: out/)")

    args = parser.parse_args()

    if args.command == "merge":
        from corpus_merger import CorpusMerger

        merger = CorpusMerger(output_dir=args.output_dir, language_code=args.lang_code)
        result = merger.merge()
        print(f"\n🔗 Merged {result['entries_in']} entries from {result['books']} books → {result['entries_out']} entries.")
        if result["conflicts"]:
            print(f"🔀 {result['conflicts']} conflict(s) flagged — see cross_book_conflicts.md")
        return

    # Default: extract
    if not args.pdf:
        parser.error("--pdf is required for extraction")

    book_id = args.book_id or infer_book_id(args.pdf)

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
        book_id=book_id,
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

    print(f"\n📁 Book artifacts: out/{args.lang_code}/books/{book_id}/")
    print(f"🔗 To merge all books: python cli.py merge --lang-code {args.lang_code}")


if __name__ == "__main__":
    main()
