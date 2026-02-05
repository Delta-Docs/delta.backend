import pytest
from unittest.mock import MagicMock, ANY, call
from app.services import github_webhook_service
from app.models.user import User
from app.models.installation import Installation
from app.models.repository import Repository

@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    return session

def test_handle_installation_created(mock_db_session):
    payload = {
        "action": "created",
        "installation": {
            "id": 123,
            "account": {
                "login": "test-org",
                "type": "Organization",
                "avatar_url": "http://avatar.url"
            }
        },
        "sender": {
            "id": 456
        },
        "repositories": [
            {"full_name": "test-org/repo1"},
            {"full_name": "test-org/repo2"}
        ]
    }
    
    github_webhook_service.handle_github_event(mock_db_session, "installation", payload)
    
    assert mock_db_session.execute.call_count >= 2

def test_handle_installation_deleted(mock_db_session):
    payload = {
        "action": "deleted",
        "installation": {"id": 123}
    }
    
    github_webhook_service.handle_github_event(mock_db_session, "installation", payload)
    
    mock_db_session.query.assert_called_with(Installation)
    mock_db_session.query.return_value.filter.assert_called()
    mock_db_session.query.return_value.filter.return_value.delete.assert_called_once()

def test_handle_installation_suspend(mock_db_session):
    payload = {
        "action": "suspend",
        "installation": {"id": 123}
    }
    
    github_webhook_service.handle_github_event(mock_db_session, "installation", payload)
    
    mock_db_session.query.assert_called_with(Repository)
    mock_db_session.query.return_value.filter.return_value.update.assert_called_once_with({"is_suspended": True})

def test_handle_installation_unsuspend(mock_db_session):
    payload = {
        "action": "unsuspend",
        "installation": {"id": 123}
    }
    
    github_webhook_service.handle_github_event(mock_db_session, "installation", payload)
    
    mock_db_session.query.assert_called_with(Repository)
    mock_db_session.query.return_value.filter.return_value.update.assert_called_once_with({"is_suspended": False})

def test_handle_repos_added(mock_db_session):
    payload = {
        "action": "added",
        "installation": {
            "id": 123,
            "account": {"avatar_url": "http://avatar.url"}
        },
        "repositories_added": [
            {"full_name": "test-org/new-repo"}
        ]
    }
    
    github_webhook_service.handle_github_event(mock_db_session, "installation_repositories", payload)
    
    mock_db_session.execute.assert_called_once()

def test_handle_repos_removed(mock_db_session):
    payload = {
        "action": "removed",
        "installation": {"id": 123},
        "repositories_removed": [
            {"full_name": "test-org/old-repo"}
        ]
    }
    
    github_webhook_service.handle_github_event(mock_db_session, "installation_repositories", payload)
    
    mock_db_session.query.assert_called_with(Repository)
    mock_db_session.query.return_value.filter.return_value.delete.assert_called_once()
