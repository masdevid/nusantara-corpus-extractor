import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


@pytest.fixture
def sample_language():
    from models import Language

    return Language(
        code="shj",
        name="Sentani",
        family="Sentanic",
        pivot_code="ind",
        pivot_name="Bahasa Indonesia",
    )


@pytest.fixture
def make_entry():
    from models import DictionaryEntry

    def _make(**kwargs):
        defaults = dict(
            headword="abara",
            gloss_pivot="burung gagak butcher bird",
            confidence=1.0,
            source_language="shj",
        )
        defaults.update(kwargs)
        return DictionaryEntry(**defaults)

    return _make
