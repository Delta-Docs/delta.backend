import pytest
import sys
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from uuid import uuid4

# Windows local testing workaround: Mock 'rq' and 'redis' before app is imported
# This prevents the "cannot find context for 'fork'" error on Windows without modifying source code.
sys.modules['rq'] = MagicMock()
sys.modules['redis'] = MagicMock()

from app.main import app  # noqa: E402
from app.deps import get_db_connection, get_current_user  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.repository import Repository  # noqa: E402
from app.models.drift import DriftEvent  # noqa: E402

# Setup test client
client = TestClient(app)

# Create a mock authenticated user
mock_user_id = uuid4()
mock_user = User(
    id=mock_user_id,
    email="tester@delta.com",
    full_name="Jahnavi Tester",
    github_user_id=123456789,
    github_username="jahnavitest"
)

# Global override for authentication dependency
def override_get_current_user():
    return mock_user

app.dependency_overrides[get_current_user] = override_get_current_user

# Fixture to provide a completely fresh mockup of the PostgreSQL database per test
@pytest.fixture
def mock_db_session():
    mock_db = MagicMock()
    # Inject our mock db whenever fastapi asks for a database connection
    app.dependency_overrides[get_db_connection] = lambda: mock_db
    yield mock_db
    pass


# =========== GET /repos/ Tests ===========

def test_get_linked_repos_success(mock_db_session):
    # Setup test data (2 repositories linked to the user)
    repo1_id = uuid4()
    repo2_id = uuid4()
    
    mock_repo_1 = Repository(
        id=repo1_id,
        installation_id=1,
        repo_name="delta/backend",
        is_active=True,
        is_suspended=False,
        style_preference="professional",
        docs_root_path="/docs",
        file_ignore_patterns=["/node_modules"]
    )
    
    mock_repo_2 = Repository(
        id=repo2_id,
        installation_id=1,
        repo_name="delta/frontend",
        is_active=False,
        is_suspended=False,
        style_preference="casual",
        docs_root_path="/readme.md",
        file_ignore_patterns=[]
    )

    # Tell the mock database to return our test data when query().join().filter().all() is called
    mock_db_session.query.return_value.join.return_value.filter.return_value.all.return_value = [
        mock_repo_1, 
        mock_repo_2
    ]

    # Perform the API request using FastAPI TestClient
    response = client.get("/api/repos/")

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["repo_name"] == "delta/backend"
    assert data[1]["repo_name"] == "delta/frontend"
    assert data[0]["style_preference"] == "professional"


# =========== PUT /repos/{id}/settings Tests ===========

def test_update_repo_settings_success(mock_db_session):
    repo_id = uuid4()
    
    # Initial repository state
    mock_repo = Repository(
        id=repo_id,
        installation_id=2,
        repo_name="delta/docs",
        is_active=True,
        is_suspended=False,
        style_preference="professional",
        docs_root_path="/docs",
        file_ignore_patterns=[]
    )

    # Have the mock database return this repository when queried by ID
    mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = mock_repo

    # The payload simulating what the React frontend would send
    update_payload = {
        "style_preference": "casual",
        "docs_root_path": "/new-docs-dir",
        "file_ignore_patterns": ["/dist", "/build"]
    }

    # Perform the API request
    response = client.put(f"/api/repos/{repo_id}/settings", json=update_payload)

    # Assertions
    assert response.status_code == 200
    data = response.json()
    
    # Verify the API response matches what we requested
    assert data["style_preference"] == "casual"
    assert data["docs_root_path"] == "/new-docs-dir"
    assert data["file_ignore_patterns"] == ["/dist", "/build"]

    # Verify the database commit was called
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


def test_update_repo_settings_not_found(mock_db_session):
    repo_id = uuid4()
    
    # Simulate DB finding nothing
    mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = None

    update_payload = {
        "style_preference": "casual"
    }

    # Perform the API request
    response = client.put(f"/api/repos/{repo_id}/settings", json=update_payload)

    # Ensure we get the correct 404 error
    assert response.status_code == 404
    assert response.json()["detail"] == "Repository not found"
    
    # Ensure no commit was performed on failure
    mock_db_session.commit.assert_not_called()


# =========== PATCH /repos/{id}/activate Tests ===========

def test_toggle_repo_activation_success(mock_db_session):
    repo_id = uuid4()
    
    mock_repo = Repository(
        id=repo_id,
        installation_id=3,
        repo_name="delta/api",
        is_active=False,
        is_suspended=False
    )

    mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = mock_repo

    activation_payload = {"is_active": True}

    response = client.patch(f"/api/repos/{repo_id}/activate", json=activation_payload)

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    mock_db_session.commit.assert_called_once()


def test_toggle_repo_activation_not_found(mock_db_session):
    repo_id = uuid4()
    mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = None

    response = client.patch(f"/api/repos/{repo_id}/activate", json={"is_active": True})

    assert response.status_code == 404
    mock_db_session.commit.assert_not_called()


# =========== GET /repos/{id}/drift-events Tests ===========

def test_get_drift_events_success(mock_db_session):
    repo_id = uuid4()
    
    # Mock finding the repository
    mock_repo = Repository(
        id=repo_id,
        installation_id=1,
        repo_name="delta/events",
        is_active=True,
        is_suspended=False
    )

    # Mock finding the drift events
    event1_id = uuid4()
    from datetime import datetime, UTC
    mock_event = DriftEvent(
        id=event1_id,
        repo_id=repo_id,
        pr_number=42,
        base_branch="main",
        head_branch="feature-branch",
        base_sha="abc1234",
        head_sha="def5678",
        processing_phase="queued",
        drift_result="pending",
        created_at=datetime.now(UTC)
    )

    # Setup database mocks
    # We first join+filter for the repo, then filter+order_by for events
    mock_db_session.query.side_effect = [
        # First query: repo
        MagicMock(join=MagicMock(return_value=MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_repo)))))),
        # Second query: events
        MagicMock(filter=MagicMock(return_value=MagicMock(order_by=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_event]))))))
    ]

    response = client.get(f"/api/repos/{repo_id}/drift-events")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["processing_phase"] == "queued"
    assert data[0]["pr_number"] == 42


def test_get_drift_events_repo_not_found(mock_db_session):
    repo_id = uuid4()
    
    # First query returns None (repo not found)
    mock_db_session.query.side_effect = [
        MagicMock(join=MagicMock(return_value=MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None))))))
    ]

    response = client.get(f"/api/repos/{repo_id}/drift-events")

    assert response.status_code == 404
