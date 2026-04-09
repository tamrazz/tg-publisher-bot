"""
Tests for hashtag tag format validation (regex used in FSM handler).
"""

import re

import pytest

_HASHTAG_RE = re.compile(r"^#?[a-zA-Zа-яА-ЯёЁ0-9_]{2,}$")


@pytest.mark.parametrize(
    "tag,valid",
    [
        ("#python", True),  # with #
        ("python", True),  # without # — now valid
        ("#тег_1", True),
        ("тег_1", True),  # without # — now valid
        ("#АБВ", True),
        ("#ab", True),
        ("ab", True),  # without # — now valid
        ("#a1_b2", True),
        ("#Ёлка", True),
        ("#", False),
        ("#a", False),  # only 1 char after #
        ("a", False),  # only 1 char, no #
        ("#tag name", False),  # space not allowed
        ("##double", False),  # double ## (becomes empty after strip)
        ("#tag!", False),  # special char
        ("", False),
    ],
)
def test_hashtag_format_validation(tag: str, valid: bool) -> None:
    assert bool(_HASHTAG_RE.match(tag)) is valid
