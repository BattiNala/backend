# pylint: disable=missing-module-docstring

from app.main import health
from app.api.v1.endpoints.issues import create_issue, list_issues
from app.api.v1.endpoints.routes import generate_route


def test_health_ok():
    """Test that the health endpoint returns the expected status."""
    assert health() == {"status": "ok"}


def test_list_issues():
    """Test that the list_issues endpoint returns an empty list."""
    assert list_issues() == {"items": []}


def test_create_issue():
    """Test that the create_issue endpoint returns a success message."""
    assert create_issue() == {"created": True}


def test_generate_route():
    """Test that the generate_route endpoint returns an empty route."""
    assert generate_route() == {"route": []}
