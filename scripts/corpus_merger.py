"""
CorpusMerger: merges per-book entries into a single language corpus. 🔗

When multiple dictionaries are extracted for the same language, this module
combines their entries into one unified corpus:

- Same headword, same gloss → keep one (higher confidence wins)
- Same headword, different gloss → merge into multi-sense entry
- Same headword, conflicting glosses → flag in cross_book_conflicts.md

Each merged entry retains source_book annotations so every entry traces
back to its originating dictionary.
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from difflib import SequenceMatcher

from models import DictionaryEntry

logger = logging.getLogger("indo_corpus_extractor.corpus_merger")

SIMILARITY_THRESHOLD = 0.90  # glosses above this are considered "same"


class CorpusMerger:
    """Merges per-book entries into a single language corpus."""

    def __init__(self, output_dir: str, language_code: str):
        self.lang_dir = os.path.join(output_dir, language_code)
        self.books_dir = os.path.join(self.lang_dir, "books")
        self.language_code = language_code

    def merge(self) -> dict:
        """Merge all book entries for this language.

        Returns a summary dict with counts and paths.
        """
        book_entries = self._load_all_books()
        if not book_entries:
            logger.warning("No book entries found in %s", self.books_dir)
            return {"books": 0, "entries_in": 0, "entries_out": 0}

        # Flatten all entries
        all_entries = []
        for book_id, entries in book_entries.items():
            all_entries.extend(entries)

        entries_in = len(all_entries)

        # Group by normalized headword
        by_headword: dict[str, list[DictionaryEntry]] = defaultdict(list)
        for entry in all_entries:
            key = entry.headword.lower().strip()
            by_headword[key].append(entry)

        # Merge
        merged: list[DictionaryEntry] = []
        conflicts: list[dict] = []

        for hw, group in by_headword.items():
            if len(group) == 1:
                merged.append(group[0])
                continue

            # Multiple entries for the same headword
            result = self._merge_group(group)
            if result["type"] == "single":
                merged.append(result["entry"])
            elif result["type"] == "multi_sense":
                merged.append(result["entry"])
            elif result["type"] == "conflict":
                # Keep the highest-confidence entry but flag the conflict
                best = max(group, key=lambda e: e.confidence)
                merged.append(best)
                conflicts.append(result)

        # Write merged corpus
        corpus_path = self._write_corpus(merged)

        # Write conflicts file
        conflicts_path = self._write_conflicts(conflicts)

        summary = {
            "books": len(book_entries),
            "entries_in": entries_in,
            "entries_out": len(merged),
            "conflicts": len(conflicts),
            "corpus_path": corpus_path,
            "conflicts_path": conflicts_path,
        }

        logger.info(
            "🔗 Merged %d entries from %d books → %d entries "
            "(%d conflicts flagged).",
            entries_in, len(book_entries), len(merged), len(conflicts),
        )

        return summary

    # -- internals -----------------------------------------------------

    def _load_all_books(self) -> dict[str, list[DictionaryEntry]]:
        """Load entries.jsonl from each book subdirectory."""
        book_entries: dict[str, list[DictionaryEntry]] = {}

        if not os.path.isdir(self.books_dir):
            return book_entries

        for book_id in sorted(os.listdir(self.books_dir)):
            book_dir = os.path.join(self.books_dir, book_id)
            entries_path = os.path.join(book_dir, "entries.jsonl")
            if not os.path.isfile(entries_path):
                continue

            entries = []
            with open(entries_path, encoding="utf-8") as f:
                for line in f:
                    row = json.loads(line)
                    entries.append(DictionaryEntry(
                        id=row.get("id", ""),
                        headword=row.get("headword", ""),
                        part_of_speech=row.get("pos"),
                        gloss_pivot=row.get("gloss_pivot", ""),
                        examples=row.get("examples", []),
                        page_ref=row.get("page_ref"),
                        confidence=row.get("confidence", 1.0),
                        source_language=row.get("source_language", ""),
                        source_book=row.get("source_book", book_id),
                        source_page=row.get("source_page"),
                    ))
            if entries:
                book_entries[book_id] = entries
                logger.info("📖 Loaded %d entries from book '%s'", len(entries), book_id)

        return book_entries

    def _merge_group(self, group: list[DictionaryEntry]) -> dict:
        """Merge a group of entries with the same headword.

        Returns:
            {"type": "single", "entry": ...} — one entry, keep as-is
            {"type": "multi_sense", "entry": ...} — merged multi-sense entry
            {"type": "conflict", "entries": [...], "glosses": [...]}
        """
        if len(group) == 1:
            return {"type": "single", "entry": group[0]}

        # Collect unique glosses
        gloss_map: dict[str, list[DictionaryEntry]] = defaultdict(list)
        for entry in group:
            key = entry.gloss_pivot.lower().strip()
            gloss_map[key].append(entry)

        unique_glosses = list(gloss_map.keys())

        if len(unique_glosses) == 1:
            # Same gloss across all books — keep highest confidence
            best = max(group, key=lambda e: e.confidence)
            # Merge source_book lists
            source_books = list({e.source_book for e in group if e.source_book})
            best.source_book = ",".join(source_books)
            return {"type": "single", "entry": best}

        # Check if glosses are similar enough to merge
        if len(unique_glosses) == 2:
            sim = SequenceMatcher(None, unique_glosses[0], unique_glosses[1]).ratio()
            if sim >= SIMILARITY_THRESHOLD:
                # Similar enough — merge, keep the longer/more complete gloss
                best_gloss = max(unique_glosses, key=len)
                best = max(group, key=lambda e: e.confidence)
                best.gloss_pivot = best_gloss
                source_books = list({e.source_book for e in group if e.source_book})
                best.source_book = ",".join(source_books)
                return {"type": "single", "entry": best}

        # Different glosses — create multi-sense entry
        senses = []
        all_examples = []
        source_books = []
        total_confidence = 0.0

        for i, (gloss_key, entries) in enumerate(gloss_map.items(), 1):
            best_entry = max(entries, key=lambda e: e.confidence)
            senses.append(f"({i}) {best_entry.gloss_pivot}")
            all_examples.extend(best_entry.examples)
            source_books.extend(e.source_book for e in entries if e.source_book)
            total_confidence += best_entry.confidence

        # Build merged entry from the highest-confidence source
        best = max(group, key=lambda e: e.confidence)
        merged_entry = DictionaryEntry(
            headword=best.headword,
            part_of_speech=best.part_of_speech,
            gloss_pivot="; ".join(senses),
            examples=all_examples[:10],  # cap examples
            page_ref=best.page_ref,
            confidence=total_confidence / len(group),
            source_language=best.source_language,
            source_book=",".join(sorted(set(source_books))),
            source_page=best.source_page,
        )

        return {"type": "multi_sense", "entry": merged_entry}

    def _write_corpus(self, entries: list[DictionaryEntry]) -> str:
        """Write merged corpus to corpus_<lang>.jsonl."""
        path = os.path.join(self.lang_dir, f"corpus_{self.language_code}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry.as_corpus_row(), ensure_ascii=False) + "\n")
        logger.info("💾 Wrote merged corpus (%d entries) → %s", len(entries), path)
        return path

    def _write_conflicts(self, conflicts: list[dict]) -> str:
        """Write cross-book conflicts to cross_book_conflicts.md."""
        path = os.path.join(self.lang_dir, "cross_book_conflicts.md")

        if not conflicts:
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Cross-Book Conflicts\n\n_No conflicts found._\n")
            return path

        with open(path, "w", encoding="utf-8") as f:
            f.write("# Cross-Book Conflicts 🔀\n\n")
            f.write(
                "Same headword appears in multiple books with conflicting glosses.\n"
                "Review and resolve before using the merged corpus.\n\n"
            )
            f.write("| Headword | Glosses | Books | Action |\n")
            f.write("|---|---|---|---|\n")

            for conflict in conflicts:
                entries = conflict["entries"]
                glosses = conflict["glosses"]
                books = list({e.source_book for e in entries if e.source_book})
                f.write(
                    f"| {entries[0].headword} "
                    f"| {' vs. '.join(glosses)} "
                    f"| {', '.join(books)} "
                    f"| _resolve_ |\n"
                )

            f.write(
                f"\n\n---\n\n"
                f"**{len(conflicts)} conflict(s) need manual resolution.**\n"
                f"Edit this file to add resolutions, then re-run the merger.\n"
            )

        logger.info("🔀 Wrote %d conflicts → %s", len(conflicts), path)
        return path
