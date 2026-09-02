from morphology_rules import MorphologyRules


def test_is_reduplication_hyphenated():
    mr = MorphologyRules()
    is_redup, base = mr.is_reduplication("bo-bo")
    assert is_redup and base == "bo"


def test_is_reduplication_spaced():
    mr = MorphologyRules()
    is_redup, base = mr.is_reduplication("bo bo")
    assert is_redup and base == "bo"


def test_is_reduplication_false():
    mr = MorphologyRules()
    assert mr.is_reduplication("abara") == (False, None)


def test_strip_affix_prefix():
    mr = MorphologyRules()
    results = mr.strip_affixes("menabara")
    assert ("prefix", "abara") in results


def test_strip_affix_suffix():
    mr = MorphologyRules()
    results = mr.strip_affixes("abaraan")
    assert ("suffix", "abara") in results


def test_find_root_affixed():
    mr = MorphologyRules()
    assert mr.find_root("menabara") == "abara"


def test_find_root_reduplication():
    mr = MorphologyRules()
    assert mr.find_root("bo-bo") == "bo"


def test_find_root_plain_returns_none():
    mr = MorphologyRules()
    assert mr.find_root("abara") is None


def test_find_derived_forms():
    mr = MorphologyRules()
    mr.find_root("menabara")
    mr.find_root("abaraan")
    assert "menabara" in mr.find_derived_forms("abara")
    assert "abaraan" in mr.find_derived_forms("abara")


def test_analyze_entries_reduplication(make_entry):
    mr = MorphologyRules()
    entries = [make_entry(headword="bo"), make_entry(headword="bo-bo")]
    findings = mr.analyze_entries(entries)
    redup = [f for f in findings if f["type"] == "reduplication"]
    assert len(redup) == 1
    assert redup[0]["action"] == "keep_as_entry"


def test_analyze_entries_suffix_cross_reference(make_entry):
    mr = MorphologyRules()
    entries = [make_entry(headword="abara"), make_entry(headword="abaraan")]
    findings = mr.analyze_entries(entries)
    suffix = [f for f in findings if f["type"] == "suffix"]
    assert len(suffix) == 1
    assert suffix[0]["action"] == "cross_reference"


def test_as_conventions_section():
    mr = MorphologyRules()
    section = mr.as_conventions_section()
    assert "## Morphology" in section
    assert "Prefixes:" in section
    assert "Suffixes:" in section


def test_from_conventions_file():
    text = (
        "## Morphology\n"
        "- Reduplication: full (bo-bo)\n"
        "- Prefixes: meN-, peN-\n"
        "- Suffixes: -an, -i\n"
        "- Circumfixes: ke-...-an\n"
    )
    mr = MorphologyRules().from_conventions_file(text)
    assert any(name == "men" for name, _ in mr.affixes["prefix"])
    assert any(name == "-an" for name, _ in mr.affixes["suffix"])
