"""Tests for issue utils."""

import re

from app.utils.issue_utils import generate_issue_label


def test_generate_issue_label_uses_expected_prefix_and_length():
    """Test generate issue label uses expected prefix and length."""
    label = generate_issue_label()

    assert re.fullmatch(r"I-[A-Z0-9]{7}", label)
