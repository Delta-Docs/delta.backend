import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.deps import get_db_connection, get_current_user
from app.models.user import User

# =========== Setup ===========

client = TestClient(app)


@pytest.fixture
def mock_db_session():
    """Provides a fresh mock database session and injects it as the FastAPI dependency."""
    mock_db = MagicMock()
    app.dependency_overrides[get_db_connection] = lambda: mock_db
    yield mock_db
    app.dependency_overrides.pop(get_db_connection, None)


def make_mock_user(email="test@example.com", full_name="Test User"):
    """Helper to create a mock User model instance."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = email
    user.full_name = full_name
    user.password_hash = "hashed_password"
    user.current_refresh_token_hash = None
    return user


# =========== POST /auth/signup Tests ===========


def test_signup_success(mock_db_session):
    """Test that a new user can register with valid credentials."""
    # No existing user found in DB
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    # After add+commit, refresh sets the user attributes
    mock_user = make_mock_user()
    mock_db_session.refresh.side_effect = lambda u: None

    with patch("app.routers.auth.security.get_hash", return_value="hashed_pw"), \
         patch("app.routers.auth.security.create_access_token", return_value="mock_access_token"), \
         patch("app.routers.auth.security.create_refresh_token", return_value="mock_refresh_token"), \
         patch("app.routers.auth.User") as MockUser:

        # Make the User() constructor return our mock_user
        MockUser.return_value = mock_user

        response = client.post("/api/auth/signup", json={
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "securepassword123"
        })

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called()


def test_signup_duplicate_email(mock_db_session):
    """Test that signup fails with 400 when email already exists."""
    existing_user = make_mock_user()
    mock_db_session.query.return_value.filter.return_value.first.return_value = existing_user

    response = client.post("/api/auth/signup", json={
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "securepassword123"
    })

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]
    mock_db_session.add.assert_not_called()


def test_signup_invalid_email(mock_db_session):
    """Test that signup fails with 422 when email format is invalid."""
    response = client.post("/api/auth/signup", json={
        "email": "not-a-valid-email",
        "full_name": "Test User",
        "password": "securepassword123"
    })

    assert response.status_code == 422


# =========== POST /auth/login Tests ===========


def test_login_success(mock_db_session):
    """Test that a user with correct credentials receives tokens in cookies."""
    mock_user = make_mock_user()
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user

    with patch("app.routers.auth.security.verify_hash", return_value=True), \
         patch("app.routers.auth.security.create_access_token", return_value="access_tok"), \
         patch("app.routers.auth.security.create_refresh_token", return_value="refresh_tok"), \
         patch("app.routers.auth.security.get_hash", return_value="hashed_refresh"):

        response = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "correctpassword"
        })

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    mock_db_session.commit.assert_called()


def test_login_wrong_password(mock_db_session):
    """Test that login fails with 401 when password is incorrect."""
    mock_user = make_mock_user()
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user

    with patch("app.routers.auth.security.verify_hash", return_value=False):
        response = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword"
        })

    assert response.status_code == 401
    assert "Incorrect credentials" in response.json()["detail"]


def test_login_user_not_found(mock_db_session):
    """Test that login fails with 401 when user does not exist."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "anypassword"
    })

    assert response.status_code == 401


def test_login_missing_fields(mock_db_session):
    """Test that login fails with 422 when required fields are missing."""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com"
        # missing password
    })

    assert response.status_code == 422


# =========== POST /auth/logout Tests ===========


def test_logout_with_valid_token(mock_db_session):
    """Test that logout clears cookies and nullifies the refresh token hash."""
    mock_user = make_mock_user()
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user

    with patch("app.routers.auth.security.verify_token", return_value={"sub": str(mock_user.id)}):
        response = client.post(
            "/api/auth/logout",
            cookies={"access_token": "valid_access_token"}
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Logout successful"
    assert mock_user.current_refresh_token_hash is None
    mock_db_session.commit.assert_called()


def test_logout_without_token(mock_db_session):
    """Test that logout succeeds gracefully even with no cookies."""
    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json()["message"] == "Logout successful"
