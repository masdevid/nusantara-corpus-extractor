import json

import cli


def test_infer_book_id_basic():
    assert cli.infer_book_id("Set-Kamus-Sentani-Indonesia-Inggris-2.pdf") == \
        "set_kamus_sentani_indonesia_inggris_2"


def test_infer_book_id_collapses_underscores():
    assert cli.infer_book_id("a  b--c.pdf") == "a_b_c"


def test_infer_book_id_strips_edges():
    assert cli.infer_book_id("--book--.pdf") == "book"


def test_load_existing_corpus_none():
    assert cli.load_existing_corpus(None) is None


def test_load_existing_corpus_reads_jsonl(tmp_path):
    path = tmp_path / "corpus.jsonl"
    path.write_text(
        json.dumps({"headword": "abara", "gloss_pivot": "burung"}) + "\n",
        encoding="utf-8",
    )
    entries = cli.load_existing_corpus(str(path))
    assert len(entries) == 1
    assert entries[0].headword == "abara"
    assert entries[0].gloss_pivot == "burung"
