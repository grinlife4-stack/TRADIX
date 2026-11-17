from pathlib import Path
import sys

SOURCE_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_DIR))

import pytest

from text_tools import slugify


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Hello World", "hello-world"),
        ("  Hello,   World! ", "hello-world"),
        ("Crème brûlée", "creme-brulee"),
        ("A/B & C", "a-b-c"),
        ("Already---slug", "already-slug"),
        ("中文", ""),
        ("--- !!! ---", ""),
        ("", ""),
    ],
)
def test_slugify_normalizes_text(value, expected):
    assert slugify(value) == expected


def test_slugify_rejects_non_string_input():
    with pytest.raises(TypeError, match="value must be a string"):
        slugify(None)
