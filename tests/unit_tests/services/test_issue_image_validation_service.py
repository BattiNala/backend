"""Tests for issue image validation service."""

from app.services.issue_image_validation_service import IssueImageValidationService


def test_compute_embedding_cosine_similarity_returns_expected_score():
    """Embedding cosine similarity should be computed from normalized vectors."""
    result = IssueImageValidationService.compute_embedding_cosine_similarity(
        [1.0, 0.0, 0.0],
        [0.5, 0.5, 0.0],
    )

    assert result == {"similarity_score": 0.7071}


def test_compute_embedding_cosine_similarity_returns_zero_for_mismatched_dimensions():
    """Mismatched embedding dimensions should return the default result."""
    result = IssueImageValidationService.compute_embedding_cosine_similarity(
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
    )

    assert result == {"similarity_score": 0.0}


def test_compute_embedding_cosine_similarity_returns_zero_for_missing_vectors():
    """Missing vectors should return the default result."""
    result = IssueImageValidationService.compute_embedding_cosine_similarity(None, [1.0, 0.0])

    assert result == {"similarity_score": 0.0}
