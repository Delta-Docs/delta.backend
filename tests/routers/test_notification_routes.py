import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.deps import get_db_connection, get_current_user
from app.models.user import User
from app.models.notification import Notification

# =========== Setup ===========

client = TestClient(app)

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


def make_mock_notification(is_read=False):
    """Helper to create a mock Notification instance."""
    notif = MagicMock(spec=Notification)
    notif.id = uuid4()
    notif.user_id = mock_user_id
    notif.message = "New drift event detected in delta/backend"
    notif.is_read = is_read
    notif.created_at = "2026-03-11T06:00:00Z"
    return notif


# =========== GET /notifications/ Tests ===========


def test_get_notifications_success(mock_db_session):
    """Test that a user can retrieve their notifications in descending order."""
    notif1 = make_mock_notification()
    notif2 = make_mock_notification(is_read=True)

    mock_db_session.query.return_value.filter.return_value \
        .order_by.return_value.all.return_value = [notif1, notif2]

    response = client.get("/api/notifications/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_notifications_empty(mock_db_session):
    """Test that an empty list is returned when user has no notifications."""
    mock_db_session.query.return_value.filter.return_value \
        .order_by.return_value.all.return_value = []

    response = client.get("/api/notifications/")

    assert response.status_code == 200
    assert response.json() == []


# =========== PATCH /notifications/{id}/read Tests ===========


def test_mark_notification_as_read_success(mock_db_session):
    """Test that a notification can be marked as read."""
    notif = make_mock_notification(is_read=False)
    notification_id = notif.id

    mock_db_session.query.return_value.filter.return_value.first.return_value = notif

    response = client.patch(f"/api/notifications/{notification_id}/read")

    assert response.status_code == 200
    assert notif.is_read is True
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(notif)


def test_mark_notification_as_read_not_found(mock_db_session):
    """Test that marking a non-existent notification raises 404."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client.patch(f"/api/notifications/{uuid4()}/read")

    assert response.status_code == 404
    assert "Notification not found" in response.json()["detail"]
    mock_db_session.commit.assert_not_called()


# =========== PATCH /notifications/read-all Tests ===========


def test_mark_all_notifications_as_read(mock_db_session):
    """Test that all unread notifications can be marked as read at once."""
    mock_db_session.query.return_value.filter.return_value.update.return_value = 3

    response = client.patch("/api/notifications/read-all")

    assert response.status_code == 200
    assert response.json()["message"] == "All notifications marked as read"
    mock_db_session.commit.assert_called_once()


# =========== DELETE /notifications/{id} Tests ===========


def test_delete_notification_success(mock_db_session):
    """Test that a notification can be deleted."""
    notif = make_mock_notification()
    notification_id = notif.id

    mock_db_session.query.return_value.filter.return_value.first.return_value = notif

    response = client.delete(f"/api/notifications/{notification_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Notification deleted"
    mock_db_session.delete.assert_called_once_with(notif)
    mock_db_session.commit.assert_called_once()


def test_delete_notification_not_found(mock_db_session):
    """Test that deleting a non-existent notification raises 404."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client.delete(f"/api/notifications/{uuid4()}")

    assert response.status_code == 404
    assert "Notification not found" in response.json()["detail"]
    mock_db_session.delete.assert_not_called()


# =========== DELETE /notifications/ Tests ===========


def test_delete_all_notifications(mock_db_session):
    """Test that all notifications for the user can be deleted at once."""
    mock_db_session.query.return_value.filter.return_value.delete.return_value = 5

    response = client.delete("/api/notifications/")

    assert response.status_code == 200
    assert response.json()["message"] == "All notifications deleted"
    mock_db_session.commit.assert_called_once()
