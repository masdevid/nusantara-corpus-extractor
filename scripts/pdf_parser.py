"""
PDFParser: turns a dictionary PDF (digital or scanned) into RawPage objects. 🖨️➡️📄

Digital-text pages get pulled straight out. Image-only pages get rasterized
and OCR'd. A page that OCRs badly gets flagged at the page level — we don't
extract garbage entries from a garbage scan.

Sources may be a single PDF or a folder of split PDFs (one chunk per page
range, e.g. "3. Halaman 39 - 62.pdf") — folders are expanded in natural
order by their numeric filename prefix and parsed as one book.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from models import RawPage

logger = logging.getLogger("indo_corpus_extractor.pdf_parser")

# Below this OCR confidence, the whole page is suspect — don't hand it to
# the entry extractor, hand it to a human instead.
BAD_PAGE_OCR_THRESHOLD = 0.55

# Minimum characters of extractable digital text before we treat a page as
# "needs OCR" rather than "digital text, just sparse".
MIN_DIGITAL_CHARS = 20

# Some scanned books carry a text layer holding only furniture — running
# headers, page numbers (~40 chars/page) — while the actual content is
# image-only. A content page below this many characters is treated as
# furniture-only and OCR'd instead of trusted.
MIN_CONTENT_CHARS = 200


@dataclass
class PageParseResult:
    pages: list[RawPage]
    bad_pages: list[int]          # page numbers that failed the OCR confidence bar
    total_pages: int = 0          # physical pages seen (incl. skipped/bad)


@dataclass
class PageProbe:
    """Cheap per-page metadata from a pass that renders/OCRs nothing —
    the input to sample-based profiling."""

    page_number: int              # global, continuous across split files
    source_file: str
    local_page: int
    digital_text: str | None      # usable layer, or furniture/None
    needs_ocr: bool


def resolve_source(source: str) -> list[str]:
    """Resolves a source path to an ordered list of PDF files.

    A folder of split PDFs is expanded in natural order by the numeric
    prefix of each filename ("2. Halaman 15 - 38.pdf" sorts before
    "10. ..."), which lexicographic sort would get wrong. Files without a
    numeric prefix sort after those with one, alphabetically.
    """
    if os.path.isfile(source):
        return [source]
    if not os.path.isdir(source):
        raise FileNotFoundError(f"Source not found: {source}")

    def natural_key(path: str) -> tuple:
        name = os.path.basename(path)
        m = re.match(r"^(\d+)", name)
        return (0, int(m.group(1)), name) if m else (1, 0, name)

    pdfs = [
        os.path.join(source, f)
        for f in os.listdir(source)
        if f.lower().endswith(".pdf") and not f.startswith(".")
    ]
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in folder: {source}")
    return sorted(pdfs, key=natural_key)


class PDFParser:
    def __init__(self, ocr_lang_hint: str) -> None:
        # pytesseract lang code for whichever gloss/pivot language this
        # dictionary uses — Language.pivot_code, not hardcoded to any one
        # language. Pivot text usually OCRs more reliably than the local
        # language's script, which is why this hint exists at all, but the
        # pipeline shouldn't assume which pivot it is.
        self.ocr_lang_hint = ocr_lang_hint

    def parse_source(self, source: str, only_pages: set[int] | None = None) -> PageParseResult:
        """Parses a single PDF or a folder of split PDFs as one book.
        Page numbers are assigned continuously across files so downstream
        zones/references are global. `only_pages` restricts actual
        parsing/OCR to those global page numbers (zone filtering) —
        numbering still covers the whole book."""
        files = resolve_source(source)
        if len(files) > 1:
            logger.info(
                "📚 Source is a folder of %d split PDFs — parsing in natural order.",
                len(files),
            )

        all_pages: list[RawPage] = []
        all_bad: list[int] = []
        offset = 0
        for path in files:
            result = self.parse(path, skip=only_pages, offset=offset)
            for page in result.pages:
                all_pages.append(page)
            all_bad.extend(p + offset for p in result.bad_pages)
            offset += result.total_pages

        logger.info(
            "✅ Parsed source '%s': %d usable pages, %d bad, across %d file(s).",
            source, len(all_pages), len(all_bad), len(files),
        )
        return PageParseResult(pages=all_pages, bad_pages=all_bad)

    def probe(self, source: str) -> list[PageProbe]:
        """Cheap pass over the whole source: reads text layers only —
        no rendering, no OCR. Tells the profiler which pages have usable
        digital text and which would need OCR."""
        files = resolve_source(source)
        probes: list[PageProbe] = []
        page_number = 0
        for path in files:
            import pypdfium2 as pdfium

            doc = pdfium.PdfDocument(path)
            try:
                for local_page, page in enumerate(doc, start=1):
                    page_number += 1
                    text = page.get_textpage().get_text_bounded()
                    usable = bool(text and len(text.strip()) >= MIN_CONTENT_CHARS)
                    probes.append(
                        PageProbe(
                            page_number=page_number,
                            source_file=path,
                            local_page=local_page,
                            digital_text=text if usable else None,
                            needs_ocr=not usable,
                        )
                    )
            finally:
                doc.close()
        return probes

    def ocr_selected(self, probes: list[PageProbe], page_numbers: list[int]) -> list[RawPage]:
        """OCRs only the requested pages (by global number). Used by the
        profiler to sample an image-heavy book without scanning it all."""
        wanted = set(page_numbers)
        by_global = {p.page_number: p for p in probes}
        results: list[RawPage] = []
        for pn in sorted(wanted):
            probe = by_global.get(pn)
            if probe is None:
                continue
            import pypdfium2 as pdfium

            doc = pdfium.PdfDocument(probe.source_file)
            try:
                bitmap = doc[probe.local_page - 1].render(scale=300 / 72)
                text, confidence = self._ocr_page(bitmap.to_pil())
            finally:
                doc.close()
            results.append(
                RawPage(
                    page_number=pn,
                    text=text,
                    was_ocr=True,
                    ocr_confidence=confidence,
                )
            )
        return results

    def parse(self, source_pdf: str, skip: set[int] | None = None, offset: int = 0) -> PageParseResult:
        """Parses one PDF. `skip` is a set of *global* page numbers to leave
        unparsed (zone filtering); `offset` shifts numbering so split-file
        chunks keep continuous global numbers."""
        logger.info("📖 Opening %s for parsing...", source_pdf)
        pages: list[RawPage] = []
        bad_pages: list[int] = []
        total = 0

        for local_number, digital_text, image in self._iter_pdf_pages(source_pdf):
            page_number = local_number + offset
            total = local_number
            if skip is not None and page_number not in skip:
                continue

            if digital_text and len(digital_text.strip()) >= MIN_CONTENT_CHARS:
                pages.append(
                    RawPage(page_number=page_number, text=digital_text, was_ocr=False)
                )
                continue

            if digital_text is not None:
                if digital_text.strip():
                    logger.info(
                        "🔎 Page %d has a text layer of only %d chars — likely "
                        "headers/page numbers over a scan; OCR-ing the image.",
                        page_number, len(digital_text.strip()),
                    )
                else:
                    logger.info(
                        "🔎 Page %d has no text layer — OCR-ing the image.",
                        page_number,
                    )

            text, confidence = self._ocr_page(image)
            if confidence < BAD_PAGE_OCR_THRESHOLD:
                logger.warning(
                    "⚠️ Page %d OCR confidence %.2f is below threshold %.2f — "
                    "flagging the whole page instead of guessing entries.",
                    page_number, confidence, BAD_PAGE_OCR_THRESHOLD,
                )
                bad_pages.append(page_number)
                continue

            pages.append(
                RawPage(
                    page_number=page_number,
                    text=text,
                    was_ocr=True,
                    ocr_confidence=confidence,
                )
            )

        logger.info(
            "✅ Parsed %d usable pages (%d flagged as bad scans).",
            len(pages), len(bad_pages),
        )
        return PageParseResult(pages=pages, bad_pages=bad_pages, total_pages=total)

    # -- internals -----------------------------------------------------

    def _iter_pdf_pages(self, source_pdf: str):
        """Yields (page_number, digital_text_or_None, page_image_or_None).

        Implementation swap point: use pypdfium2 for digital text extraction
        and page rasterization. Kept as a thin seam here so
        the rest of the pipeline never needs to know which library is
        backing it.
        """
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(source_pdf)
        try:
            for i, page in enumerate(doc, start=1):
                text_page = page.get_textpage()
                text = text_page.get_text_bounded()
                if text and len(text.strip()) >= MIN_CONTENT_CHARS:
                    yield i, text, None
                else:
                    # No usable text layer — either none at all or just
                    # furniture (headers/page numbers) over a scan.
                    bitmap = page.render(scale=300 / 72)
                    yield i, text, bitmap.to_pil()
        finally:
            doc.close()

    def _ocr_page(self, image) -> tuple[str, float]:
        """Runs OCR on a rasterized page, returns (text, mean_confidence)."""
        import pytesseract

        data = pytesseract.image_to_data(
            image, lang=self.ocr_lang_hint, output_type=pytesseract.Output.DICT
        )
        words = [w for w in data["text"] if w.strip()]
        confidences = [
            int(c) for c, w in zip(data["conf"], data["text"]) if w.strip() and int(c) >= 0
        ]
        text = " ".join(words)
        mean_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
        return text, mean_conf
