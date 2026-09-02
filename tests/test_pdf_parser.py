import os

import pytest

from pdf_parser import (
    BAD_PAGE_OCR_THRESHOLD,
    MIN_CONTENT_CHARS,
    PDFParser,
    PageProbe,
    resolve_source,
)


def test_resolve_source_single_file(tmp_path):
    f = tmp_path / "book.pdf"
    f.write_bytes(b"%PDF")
    assert resolve_source(str(f)) == [str(f)]


def test_resolve_source_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_source(str(tmp_path / "nope.pdf"))


def test_resolve_source_folder_natural_sort(tmp_path):
    for name in ["10. Halaman 39 - 62.pdf", "2. Halaman 15 - 38.pdf",
                 "1. Halaman 1 - 14.pdf", "notes.pdf"]:
        (tmp_path / name).write_bytes(b"%PDF")
    files = resolve_source(str(tmp_path))
    basenames = [os.path.basename(f) for f in files]
    assert basenames == ["1. Halaman 1 - 14.pdf", "2. Halaman 15 - 38.pdf",
                         "10. Halaman 39 - 62.pdf", "notes.pdf"]


def test_resolve_source_folder_no_pdfs(tmp_path):
    (tmp_path / "readme.txt").write_text("hi")
    with pytest.raises(FileNotFoundError):
        resolve_source(str(tmp_path))


def test_parse_digital_pages(monkeypatch):
    parser = PDFParser(ocr_lang_hint="ind")

    def fake_iter(path):
        yield 1, "word " * 100, None
        yield 2, "word " * 100, None

    monkeypatch.setattr(parser, "_iter_pdf_pages", fake_iter)
    result = parser.parse("book.pdf")
    assert len(result.pages) == 2
    assert result.pages[0].was_ocr is False
    assert result.pages[0].page_number == 1
    assert result.bad_pages == []


def test_parse_ocr_page(monkeypatch):
    parser = PDFParser(ocr_lang_hint="ind")

    def fake_iter(path):
        yield 1, "", object()  # no digital text -> OCR

    def fake_ocr(image):
        return "abara burung gagak", 0.9

    monkeypatch.setattr(parser, "_iter_pdf_pages", fake_iter)
    monkeypatch.setattr(parser, "_ocr_page", fake_ocr)
    result = parser.parse("book.pdf")
    assert len(result.pages) == 1
    assert result.pages[0].was_ocr is True
    assert result.pages[0].ocr_confidence == 0.9


def test_parse_bad_ocr_page(monkeypatch):
    parser = PDFParser(ocr_lang_hint="ind")

    def fake_iter(path):
        yield 1, "", object()

    def fake_ocr(image):
        return "garbage", 0.2

    monkeypatch.setattr(parser, "_iter_pdf_pages", fake_iter)
    monkeypatch.setattr(parser, "_ocr_page", fake_ocr)
    result = parser.parse("book.pdf")
    assert result.pages == []
    assert result.bad_pages == [1]


def test_parse_skip_pages(monkeypatch):
    parser = PDFParser(ocr_lang_hint="ind")

    def fake_iter(path):
        yield 1, "word " * 100, None
        yield 2, "word " * 100, None
        yield 3, "word " * 100, None

    monkeypatch.setattr(parser, "_iter_pdf_pages", fake_iter)
    # `skip` is the set of pages to parse (zone filtering / include set)
    result = parser.parse("book.pdf", skip={2})
    assert [p.page_number for p in result.pages] == [2]


def test_parse_offset(monkeypatch):
    parser = PDFParser(ocr_lang_hint="ind")

    def fake_iter(path):
        yield 1, "word " * 100, None
        yield 2, "word " * 100, None

    monkeypatch.setattr(parser, "_iter_pdf_pages", fake_iter)
    result = parser.parse("book.pdf", offset=10)
    assert [p.page_number for p in result.pages] == [11, 12]


def test_parse_source_folder(monkeypatch, tmp_path):
    parser = PDFParser(ocr_lang_hint="ind")
    (tmp_path / "1. a.pdf").write_bytes(b"%PDF")
    (tmp_path / "2. b.pdf").write_bytes(b"%PDF")

    calls = []

    def fake_parse(path, skip=None, offset=0):
        calls.append((path, offset))
        from pdf_parser import PageParseResult
        from models import RawPage
        return PageParseResult(
            pages=[RawPage(page_number=offset + 1, text="word " * 100, was_ocr=False)],
            bad_pages=[], total_pages=1,
        )

    monkeypatch.setattr(parser, "parse", fake_parse)
    result = parser.parse_source(str(tmp_path))
    assert len(result.pages) == 2
    assert [p.page_number for p in result.pages] == [1, 2]
    assert calls[0][1] == 0
    assert calls[1][1] == 1


def test_probe(monkeypatch):
    parser = PDFParser(ocr_lang_hint="ind")
    monkeypatch.setattr("pdf_parser.resolve_source", lambda s: ["book.pdf"])

    class FakeTextPage:
        def get_text_bounded(self):
            return "word " * 100

    class FakePage:
        def get_textpage(self):
            return FakeTextPage()

    class FakeDoc:
        def __init__(self, path):
            self.pages = [FakePage(), FakePage()]

        def __iter__(self):
            return iter(self.pages)

        def close(self):
            pass

    monkeypatch.setattr("pypdfium2.PdfDocument", FakeDoc)
    probes = parser.probe("book.pdf")
    assert len(probes) == 2
    assert probes[0].page_number == 1
    assert probes[0].needs_ocr is False
    assert probes[0].digital_text is not None


def test_probe_needs_ocr(monkeypatch):
    parser = PDFParser(ocr_lang_hint="ind")
    monkeypatch.setattr("pdf_parser.resolve_source", lambda s: ["book.pdf"])

    class FakeTextPage:
        def get_text_bounded(self):
            return "short"

    class FakePage:
        def get_textpage(self):
            return FakeTextPage()

    class FakeDoc:
        def __init__(self, path):
            self.pages = [FakePage()]

        def __iter__(self):
            return iter(self.pages)

        def close(self):
            pass

    monkeypatch.setattr("pypdfium2.PdfDocument", FakeDoc)
    probes = parser.probe("book.pdf")
    assert probes[0].needs_ocr is True
    assert probes[0].digital_text is None


def test_ocr_page(monkeypatch):
    parser = PDFParser(ocr_lang_hint="ind")
    data = {"text": ["abara", "burung", "gagak", ""],
            "conf": ["90", "80", "70", "-1"]}

    class FakeTesseract:
        Output = type("Output", (), {"DICT": "dict"})()

        @staticmethod
        def image_to_data(image, lang=None, output_type=None):
            return data

    monkeypatch.setattr("pytesseract.image_to_data", FakeTesseract.image_to_data)
    monkeypatch.setattr("pytesseract.Output", FakeTesseract.Output)
    text, conf = parser._ocr_page(object())
    assert text == "abara burung gagak"
    assert abs(conf - 0.8) < 1e-6


def test_ocr_selected(monkeypatch):
    parser = PDFParser(ocr_lang_hint="ind")
    probes = [PageProbe(page_number=1, source_file="book.pdf", local_page=1,
                        digital_text=None, needs_ocr=True),
              PageProbe(page_number=2, source_file="book.pdf", local_page=2,
                        digital_text=None, needs_ocr=True)]

    class FakeBitmap:
        def to_pil(self):
            return object()

    class FakePage:
        def render(self, scale):
            return FakeBitmap()

    class FakeDoc:
        def __init__(self, path):
            self.pages = [FakePage(), FakePage()]

        def __getitem__(self, i):
            return self.pages[i]

        def close(self):
            pass

    monkeypatch.setattr("pypdfium2.PdfDocument", FakeDoc)
    monkeypatch.setattr(parser, "_ocr_page", lambda img: ("abara burung", 0.85))
    results = parser.ocr_selected(probes, [2])
    assert len(results) == 1
    assert results[0].page_number == 2
    assert results[0].was_ocr is True
    assert results[0].ocr_confidence == 0.85
