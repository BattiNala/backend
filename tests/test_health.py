from app.main import health
from app.api.v1.endpoints.issues import create_issue, list_issues
from app.api.v1.endpoints.routes import generate_route


def test_health_ok():
    assert health() == {"status": "ok"}


def test_list_issues():
    assert list_issues() == {"items": []}


def test_create_issue():
    assert create_issue() == {"created": True}


def test_generate_route():
    assert generate_route() == {"route": []}
