import json

from corpus_merger import CorpusMerger


def _write_book(tmp_path, lang, book_id, entries):
    import os
    book_dir = tmp_path / lang / "books" / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    with open(book_dir / "entries.jsonl", "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def test_merge_no_books(tmp_path):
    merger = CorpusMerger(str(tmp_path), "shj")
    summary = merger.merge()
    assert summary["books"] == 0


def test_merge_single_book_passthrough(tmp_path, make_entry):
    e = make_entry(headword="abara", gloss_pivot="burung").as_corpus_row()
    _write_book(tmp_path, "shj", "set", [e])
    merger = CorpusMerger(str(tmp_path), "shj")
    summary = merger.merge()
    assert summary["entries_in"] == 1
    assert summary["entries_out"] == 1
    assert summary["conflicts"] == 0
    assert summary["corpus_path"].endswith("corpus_shj.jsonl")


def test_merge_same_gloss_dedupes(tmp_path, make_entry):
    rows = [make_entry(headword="abara", gloss_pivot="burung", source_book="a").as_corpus_row(),
            make_entry(headword="abara", gloss_pivot="burung", source_book="b").as_corpus_row()]
    _write_book(tmp_path, "shj", "a", [rows[0]])
    _write_book(tmp_path, "shj", "b", [rows[1]])
    merger = CorpusMerger(str(tmp_path), "shj")
    summary = merger.merge()
    assert summary["entries_in"] == 2
    assert summary["entries_out"] == 1
    assert summary["conflicts"] == 0


def test_merge_different_glosses_multi_sense(tmp_path, make_entry):
    rows = [make_entry(headword="abara", gloss_pivot="burung", source_book="a").as_corpus_row(),
            make_entry(headword="abara", gloss_pivot="layar", source_book="b").as_corpus_row()]
    _write_book(tmp_path, "shj", "a", [rows[0]])
    _write_book(tmp_path, "shj", "b", [rows[1]])
    merger = CorpusMerger(str(tmp_path), "shj")
    summary = merger.merge()
    assert summary["entries_in"] == 2
    assert summary["entries_out"] == 1
    assert summary["conflicts"] == 0
    merged = [json.loads(l) for l in open(summary["corpus_path"], encoding="utf-8")]
    assert "(1)" in merged[0]["gloss_pivot"]
    assert "(2)" in merged[0]["gloss_pivot"]


def test_merge_group_single(tmp_path, make_entry):
    merger = CorpusMerger(str(tmp_path), "shj")
    e = make_entry(headword="abara", gloss_pivot="burung")
    result = merger._merge_group([e])
    assert result["type"] == "single"


def test_merge_group_multi_sense(tmp_path, make_entry):
    merger = CorpusMerger(str(tmp_path), "shj")
    e1 = make_entry(headword="bo", gloss_pivot="air", source_book="a")
    e2 = make_entry(headword="bo", gloss_pivot="kata", source_book="b")
    result = merger._merge_group([e1, e2])
    assert result["type"] == "multi_sense"
    assert "(1)" in result["entry"].gloss_pivot
    assert "(2)" in result["entry"].gloss_pivot


def test_merge_group_similar_gloss_merged(tmp_path, make_entry):
    merger = CorpusMerger(str(tmp_path), "shj")
    e1 = make_entry(headword="abara", gloss_pivot="burung gagak", source_book="a")
    e2 = make_entry(headword="abara", gloss_pivot="burung gagak.", source_book="b")
    result = merger._merge_group([e1, e2])
    assert result["type"] == "single"
    assert result["entry"].gloss_pivot == "burung gagak."
