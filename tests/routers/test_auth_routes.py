import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
from uuid import uuid4

from sqlalchemy.orm import Session
from app.main import app
from app.deps import get_db_connection, get_current_user
from app.models.user import User

@pytest.fixture
def client():
    """Provides a fresh TestClient for each test."""
    with TestClient(app) as c:
        yield c


# =========== Diagnostic Test ===========

def test_api_root(client):
    """Diagnostic test to ensure GET /api works."""
    response = client.get("/api")
    assert response.status_code == 200
    assert "Delta" in response.json()["message"]


@pytest.fixture
def mock_db_session():
    """Provides a fresh mock database session and sets it in overrides."""
    mock_db = MagicMock(spec=Session)
    # Default behavior for query chain
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch.dict(app.dependency_overrides, {get_db_connection: lambda: mock_db}):
        yield mock_db


@pytest.fixture
def mock_current_user():
    """Fixture to provide a mock user and set it in overrides."""
    user = make_mock_user()
    with patch.dict(app.dependency_overrides, {get_current_user: lambda: user}):
        yield user


def make_mock_user(email="test@example.com", full_name="Test User"):
    """Helper to create a mock User model instance with valid string attributes."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = str(email)
    user.full_name = str(full_name)
    user.password_hash = "hashed_pw"
    user.current_refresh_token_hash = None
    user.github_user_id = None
    user.github_username = None
    return user


# Create a default mock user for general use
mock_user = make_mock_user()


# =========== POST /auth/signup Tests ===========


def test_signup_success(client, mock_db_session):
    """Test that a new user can register with valid credentials."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    mock_user = make_mock_user()

    with patch("app.routers.auth.security.get_hash", return_value="hashed_pw"), \
         patch("app.routers.auth.security.create_access_token", return_value="mock_access_token"), \
         patch("app.routers.auth.security.create_refresh_token", return_value="mock_refresh_token"), \
         patch("app.routers.auth.User") as MockUser:

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


def test_signup_duplicate_email(client, mock_db_session):
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


def test_signup_invalid_email(client, mock_db_session):
    """Test that signup fails with 422 when email format is invalid."""
    response = client.post("/api/auth/signup", json={
        "email": "not-a-valid-email",
        "full_name": "Test User",
        "password": "securepassword123"
    })

    assert response.status_code == 422


# =========== POST /auth/login Tests ===========


def test_login_success(client, mock_db_session):
    """Test that a user with correct credentials receives a successful response."""
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


def test_login_wrong_password(client, mock_db_session):
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


def test_login_user_not_found(client, mock_db_session):
    """Test that login fails with 401 when user does not exist."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "anypassword"
    })

    assert response.status_code == 401


def test_login_missing_fields(client, mock_db_session):
    """Test that login fails with 422 when required fields are missing."""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com"
        # missing password
    })

    assert response.status_code == 422


# =========== POST /auth/logout Tests ===========


def test_logout_with_valid_token(client, mock_db_session):
    """Test that logout clears cookies and nullifies the refresh token hash."""
    mock_user = make_mock_user()
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user

    with patch("app.routers.auth.security.verify_token", return_value={"sub": str(mock_user.id)}):
        client.cookies.set("access_token", "valid_access_token")
        response = client.post("/api/auth/logout")
        client.cookies.delete("access_token")

    assert response.status_code == 200
    assert response.json()["message"] == "Logout successful"
    mock_db_session.commit.assert_called()


def test_logout_without_token(client, mock_db_session):
    """Test that logout succeeds gracefully even with no cookies."""
    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json()["message"] == "Logout successful"


# =========== GET /auth/github/callback Tests ===========

@pytest.mark.asyncio
async def test_github_callback_success(mock_db_session, mock_current_user):
    """Test successful GitHub OAuth callback linking user and installation."""
    mock_token_resp = MagicMock()
    mock_token_resp.json.return_value = {"access_token": "gh_access_token"}
    
    mock_user_resp = MagicMock()
    mock_user_resp.json.return_value = {"id": 12345, "login": "github_user"}

    # Mock matching the way it's used in the router
    with patch("app.routers.auth.httpx.AsyncClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.post.return_value = mock_token_resp
        mock_instance.get.return_value = mock_user_resp
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/auth/github/callback?code=mock_code&installation_id=67890")

    assert response.status_code == 303
    assert "dashboard" in response.headers["location"]
    
    assert mock_current_user.github_user_id == 12345
    assert mock_current_user.github_username == "github_user"
    mock_db_session.commit.assert_called()


@pytest.mark.asyncio
async def test_github_callback_missing_code(mock_db_session, mock_current_user):
    """Test that missing authorization code returns 400."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/auth/github/callback?installation_id=67890")
    assert response.status_code == 400
    assert "code missing" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_github_callback_github_error(mock_db_session, mock_current_user):
    """Test handling of error returned by GitHub during token exchange."""
    mock_token_resp = MagicMock()
    mock_token_resp.json.return_value = {
        "error": "bad_verification_code",
        "error_description": "The code passed is incorrect or expired."
    }

    with patch("app.routers.auth.httpx.AsyncClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.post.return_value = mock_token_resp
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/auth/github/callback?code=wrong_code")

    assert response.status_code == 400
    assert "GitHub Error" in response.json()["detail"]
