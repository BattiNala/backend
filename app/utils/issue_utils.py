"""
Issue utility functions.
"""

import secrets
import string


def generate_issue_label() -> str:
    """Generate a unique issue label in the format 'I-XXXXXXX' (7 alphanumeric chars)."""

    chars = string.ascii_uppercase + string.digits
    random_id = "".join(secrets.choice(chars) for _ in range(7))
    return f"I-{random_id}"
