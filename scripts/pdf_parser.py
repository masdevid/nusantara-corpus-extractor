"""
PDFParser: turns a dictionary PDF (digital or scanned) into RawPage objects. 🖨️➡️📄

Digital-text pages get pulled straight out. Image-only pages get rasterized
and OCR'd. A page that OCRs badly gets flagged at the page level — we don't
extract garbage entries from a garbage scan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from models import RawPage

logger = logging.getLogger("indo_corpus_extractor.pdf_parser")

# Below this OCR confidence, the whole page is suspect — don't hand it to
# the entry extractor, hand it to a human instead.
BAD_PAGE_OCR_THRESHOLD = 0.55

# Minimum characters of extractable digital text before we treat a page as
# "needs OCR" rather than "digital text, just sparse".
MIN_DIGITAL_CHARS = 20


@dataclass
class PageParseResult:
    pages: list[RawPage]
    bad_pages: list[int]   # page numbers that failed the OCR confidence bar


class PDFParser:
    def __init__(self, ocr_lang_hint: str) -> None:
        # pytesseract lang code for whichever gloss/pivot language this
        # dictionary uses — Language.pivot_code, not hardcoded to any one
        # language. Pivot text usually OCRs more reliably than the local
        # language's script, which is why this hint exists at all, but the
        # pipeline shouldn't assume which pivot it is.
        self.ocr_lang_hint = ocr_lang_hint

    def parse(self, source_pdf: str) -> PageParseResult:
        logger.info("📖 Opening %s for parsing...", source_pdf)
        pages: list[RawPage] = []
        bad_pages: list[int] = []

        for page_number, digital_text, image in self._iter_pdf_pages(source_pdf):
            if digital_text and len(digital_text.strip()) >= MIN_DIGITAL_CHARS:
                pages.append(
                    RawPage(page_number=page_number, text=digital_text, was_ocr=False)
                )
                continue

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
        return PageParseResult(pages=pages, bad_pages=bad_pages)

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
                if text and len(text.strip()) >= MIN_DIGITAL_CHARS:
                    yield i, text, None
                else:
                    bitmap = page.render(scale=300 / 72)
                    yield i, None, bitmap.to_pil()
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
