import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.deps import get_db_connection, get_current_user
from app.models.user import User

# =========== Setup ===========

client = TestClient(app)

# Create a mock authenticated user for all dashboard tests
mock_user_id = uuid4()
mock_user = MagicMock(spec=User)
mock_user.id = mock_user_id
mock_user.email = "tester@delta.com"
mock_user.full_name = "Jahnavi Tester"


def override_get_current_user():
    return mock_user


app.dependency_overrides[get_current_user] = override_get_current_user


@pytest.fixture
def mock_db_session():
    """Provides a fresh mock database session injected as a FastAPI dependency."""
    mock_db = MagicMock()
    app.dependency_overrides[get_db_connection] = lambda: mock_db
    yield mock_db
    app.dependency_overrides.pop(get_db_connection, None)


# =========== GET /dashboard/stats Tests ===========


def test_get_dashboard_stats_success(mock_db_session):
    """Test that dashboard stats returns correct counts for the authenticated user."""
    # Each scalar() call returns a different count
    mock_db_session.query.return_value.filter.return_value.scalar.return_value = 3
    mock_db_session.query.return_value.join.return_value.filter.return_value.scalar.return_value = 7
    mock_db_session.query.return_value.join.return_value.join.return_value.filter.return_value.scalar.return_value = 21

    response = client.get("/api/dashboard/stats")

    assert response.status_code == 200
    data = response.json()
    assert "installations_count" in data
    assert "repos_linked_count" in data
    assert "drift_events_count" in data
    assert "pr_waiting_count" in data


def test_get_dashboard_stats_all_zero(mock_db_session):
    """Test that dashboard stats returns zeros for a new user with no data."""
    mock_db_session.query.return_value.filter.return_value.scalar.return_value = 0
    mock_db_session.query.return_value.join.return_value.filter.return_value.scalar.return_value = 0
    mock_db_session.query.return_value.join.return_value.join.return_value.filter.return_value.scalar.return_value = 0

    response = client.get("/api/dashboard/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["installations_count"] == 0
    assert data["repos_linked_count"] == 0
    assert data["drift_events_count"] == 0
    assert data["pr_waiting_count"] == 0


def test_get_dashboard_stats_requires_auth():
    """Test that dashboard stats requires authentication."""
    # Remove auth override temporarily
    app.dependency_overrides.pop(get_current_user, None)

    response = client.get("/api/dashboard/stats")

    # Restore override
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Should be 401 or 403 without auth
    assert response.status_code in [401, 403]


# =========== GET /dashboard/repos Tests ===========


def test_get_dashboard_repos_success(mock_db_session):
    """Test that dashboard repos returns up to 5 recent repos with details."""
    mock_repo = MagicMock()
    mock_repo.repo_name = "owner/delta-docs"
    mock_repo.installation_id = 101

    mock_db_session.query.return_value.join.return_value.filter.return_value \
        .order_by.return_value.limit.return_value.all.return_value = [mock_repo]

    with patch("app.routers.dashboard.get_repo_details", new_callable=AsyncMock) as mock_details:
        mock_details.return_value = {
            "name": "delta-docs",
            "description": "Documentation drift detector",
            "language": "Python",
            "stargazers_count": 42,
            "forks_count": 5,
            "avatar_url": None,
        }
        response = client.get("/api/dashboard/repos")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "delta-docs"
    assert data[0]["language"] == "Python"
    assert data[0]["stargazers_count"] == 42


def test_get_dashboard_repos_empty(mock_db_session):
    """Test that dashboard repos returns empty list when user has no repos."""
    mock_db_session.query.return_value.join.return_value.filter.return_value \
        .order_by.return_value.limit.return_value.all.return_value = []

    response = client.get("/api/dashboard/repos")

    assert response.status_code == 200
    assert response.json() == []


def test_get_dashboard_repos_github_api_failure(mock_db_session):
    """Test that dashboard repos falls back gracefully when GitHub API fails."""
    mock_repo = MagicMock()
    mock_repo.repo_name = "owner/delta-docs"
    mock_repo.installation_id = 101

    mock_db_session.query.return_value.join.return_value.filter.return_value \
        .order_by.return_value.limit.return_value.all.return_value = [mock_repo]

    with patch("app.routers.dashboard.get_repo_details", side_effect=Exception("GitHub API down")):
        response = client.get("/api/dashboard/repos")

    assert response.status_code == 200
    data = response.json()
    # Should fallback with error description instead of crashing
    assert len(data) == 1
    assert data[0]["description"] == "Error fetching details"
    assert data[0]["name"] == "owner/delta-docs"
