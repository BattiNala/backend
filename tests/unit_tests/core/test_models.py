"""Tests for ORM model wiring."""

from sqlalchemy.orm import configure_mappers

from app import models


def test_model_mappers_configure_successfully():
    """All model relationships should configure without mapper errors."""
    assert models is not None
    configure_mappers()
