"""One-shot helper: parse Sentani dictionary and test extraction patterns.
Usage: python3 scripts/test_extract.py [--pattern NAME]
"""
import sys, re, argparse
sys.path.insert(0, "scripts")
from pdf_parser import PDFParser
from book_profiler import BookProfiler
from entry_extractor import EntryExtractor
from typo_corrector import PhonologyReference
from models import Language

LANG = Language(code="set", name="Sentani", family="Sentanic",
                pivot_code="ind", pivot_name="Bahasa Indonesia")
PDF  = "dictionaries/671742406-Set-Kamus-Sentani-Indonesia-Inggris-2.pdf"
PHON = "references/sentani_phonology.md"

def load_pages():
    parser = PDFParser(ocr_lang_hint="ind")
    probes = parser.probe(PDF)
    profile = BookProfiler().profile(probes, lambda n: parser.ocr_selected(probes, n))
    return parser.parse_source(PDF, only_pages=set(profile.body_pages))

def run(pattern_name, pages):
    phon = PhonologyReference.from_markdown(PHON)
    if pattern_name == "current":
        ext = EntryExtractor(LANG, entry_pattern=phon.entry_pattern,
                             split_pattern=phon.entry_split)
    elif pattern_name == "line":
        ext = EntryExtractor(LANG, entry_pattern=phon.entry_pattern,
                             split_pattern=None)
    elif pattern_name == "line_wide":
        # Allow headwords that are 1-3 tokens (current allows 1-2)
        pat = re.compile(
            r"^(?:a\s+)?[•·.]{0,3}\s*(?P<headword>[a-zà-ÿ''\-]+"
            r"(?:\s+[a-zà-ÿ''\-]+){0,2})\s*(?P<gloss>.+)$"
        )
        ext = EntryExtractor(LANG, entry_pattern=pat, split_pattern=None)
    else:
        raise ValueError(f"Unknown pattern: {pattern_name}")

    entries = ext.extract(pages.pages)
    hw = {}
    for e in entries:
        hw.setdefault(e.headword, []).append(e)
    print(f"\n=== {pattern_name}: {len(entries)} entries, {len(hw)} unique headwords ===")
    dupes = {h: els for h, els in hw.items() if len(els) > 1}
    print(f"  Duplicate headwords: {len(dupes)}")
    for h, els in sorted(dupes.items())[:15]:
        print(f"    {h}: {len(els)} — {els[0].gloss_pivot[:60]}")
    return entries

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="current",
                    choices=["current", "line", "line_wide"])
    args = ap.parse_args()
    pages = load_pages()
    print(f"Loaded {len(pages.pages)} body pages")
    run(args.pattern, pages)
