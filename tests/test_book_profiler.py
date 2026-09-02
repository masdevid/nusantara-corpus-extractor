from book_profiler import BookProfiler, SAMPLE_BUDGET
from pdf_parser import PageProbe


def _probe(number, digital_text=None, needs_ocr=False):
    return PageProbe(page_number=number, source_file="x.pdf", local_page=number,
                     digital_text=digital_text, needs_ocr=needs_ocr)


def test_page_stats_markers():
    profiler = BookProfiler()
    text = "a kata •• word KS: olaiwa (aye) burung n. v. adj."
    stats = profiler._page_stats(text)
    assert stats["words"] > 0
    assert stats["markers"] >= 4  # dotted + cross-ref + paren + pos codes


def test_page_stats_gloss_langs():
    profiler = BookProfiler()
    stats = profiler._page_stats("yang dan di the of and in")
    assert stats["gloss_langs"]["indonesian"] >= 3
    assert stats["gloss_langs"]["english"] >= 3


def test_pick_sample_all_when_small():
    profiler = BookProfiler()
    probes = [_probe(i) for i in range(1, 6)]
    sample = profiler._pick_sample(probes)
    assert sample == [1, 2, 3, 4, 5]


def test_pick_sample_budget_cap():
    profiler = BookProfiler()
    probes = [_probe(i) for i in range(1, 100)]
    sample = profiler._pick_sample(probes)
    assert len(sample) <= SAMPLE_BUDGET


def test_split_zones():
    profiler = BookProfiler()
    probes = [_probe(i) for i in range(1, 11)]
    like = {i: (3 <= i <= 8) for i in range(1, 11)}
    front, body, back = profiler._split_zones(probes, like)
    assert 1 in front
    assert 10 in back
    # zone boundaries are padded outward by one sample step
    assert body and body[0] <= 3 and body[-1] >= 8


def test_split_zones_no_liked():
    profiler = BookProfiler()
    probes = [_probe(i) for i in range(1, 6)]
    front, body, back = profiler._split_zones(probes, {})
    assert body == []
    assert front == [1, 2, 3, 4, 5]


def test_book_kind_dictionary():
    profiler = BookProfiler()
    body = [1, 2, 3]
    stats = {i: {"words": 200, "markers": 10, "prose_hints": 0,
                 "avg_sentence_len": 8, "section_headers": 0} for i in body}
    like = {i: True for i in body}
    assert profiler._book_kind(body, stats, like) == "dictionary"


def test_book_kind_kids_picture_book():
    profiler = BookProfiler()
    body = [1, 2]
    stats = {i: {"words": 20, "markers": 0, "prose_hints": 0,
                 "avg_sentence_len": 5, "section_headers": 0} for i in body}
    like = {i: False for i in body}
    assert profiler._book_kind(body, stats, like) == "kids_picture_book"


def test_book_kind_unknown_no_body():
    profiler = BookProfiler()
    assert profiler._book_kind([], {}, {}) == "unknown"


def test_conventions():
    profiler = BookProfiler()
    body_stats = {
        1: {"markers": 5, "gloss_langs": {"indonesian": 3}, "numbered_items": 0},
        2: {"markers": 7, "gloss_langs": {"indonesian": 2}, "numbered_items": 0},
    }
    conv = profiler._conventions(body_stats)
    assert "marker density (body)" in conv
    assert "gloss language mix" in conv


def test_conventions_no_body():
    profiler = BookProfiler()
    conv = profiler._conventions({})
    assert "no scoreable pages" in conv["marker density (body)"]


def test_profile_uses_ocr_sample(monkeypatch):
    profiler = BookProfiler()

    def dict_text(prefix):
        return (
            f"{prefix} kata •• word. NEBEl A ELEWATERE FAMAt MOISE EKEISEI. "
            "Apa yang dikatakan orang tidak mempengaruhi Famai untuk mundur. "
            "That word that was spoken, Famai ignored it. bawah •• low. EBI "
            "ANE RUKE. Ebi jatuh di bawah. Ebi fell down. tempat •• place. NDA "
            "WANEN NEKEYANDEBE HEKE BAN A BAN NA BEKO HELE HUBAYANNELE. Hidup "
            "tanpa tempat berkebun rasanya sangat tidak baik. The way we are "
            "living with no place for a garden is very bad. KS: anuwau"
        )

    probes = [
        _probe(1, digital_text=dict_text("a")),
        _probe(2, needs_ocr=True),
        _probe(3, digital_text=dict_text("a")),
    ]

    def fake_ocr(page_numbers):
        from models import RawPage
        return [RawPage(page_number=2, text=dict_text("a"), was_ocr=True,
                        ocr_confidence=0.9)]

    profile = profiler.profile(probes, fake_ocr)
    assert profile.book_kind in ("dictionary", "mixed")
    assert profile.body_pages  # non-empty


def test_profile_bad_ocr_page_flagged(monkeypatch):
    profiler = BookProfiler()
    probes = [_probe(1, needs_ocr=True)]

    def fake_ocr(page_numbers):
        from models import RawPage
        return [RawPage(page_number=1, text="garbage", was_ocr=True,
                        ocr_confidence=0.2)]

    profile = profiler.profile(probes, fake_ocr)
    assert profile.unreadable_pages == [1]
