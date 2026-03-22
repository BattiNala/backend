"""Tests for osm pbf loader."""

import pytest

from app.routing.osm_pbf_loader import _is_oneway, load_osm_pbf


def test_is_oneway_handles_standard_reverse_and_roundabout_tags():
    """Test is oneway handles standard reverse and roundabout tags."""
    assert _is_oneway({}) == (False, False)
    assert _is_oneway({"junction": "roundabout"}) == (True, False)
    assert _is_oneway({"oneway": "yes"}) == (True, False)
    assert _is_oneway({"oneway": "-1"}) == (True, True)
    assert _is_oneway({"oneway": "no"}) == (False, False)


def test_load_osm_pbf_raises_for_missing_file(tmp_path):
    """Test load osm pbf raises for missing file."""
    with pytest.raises(FileNotFoundError):
        load_osm_pbf(tmp_path / "missing.pbf")
