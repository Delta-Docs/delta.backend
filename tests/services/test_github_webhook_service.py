import pytest
from unittest.mock import MagicMock, ANY, call, patch, AsyncMock
from app.services import github_webhook_service
from app.models.user import User
from app.models.installation import Installation
from app.models.repository import Repository
from app.models.drift import DriftEvent

# Test fixture for mocking DB session
@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    return session

# Test that GH app installation creates installation and repo records
@pytest.mark.asyncio
async def test_handle_installation_created(mock_db_session):
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
    
    await github_webhook_service.handle_github_event(mock_db_session, "installation", payload)
    assert mock_db_session.execute.call_count >= 2

# Test that GH app deletion removes installation and cascades
@pytest.mark.asyncio
async def test_handle_installation_deleted(mock_db_session):
    payload = {
        "action": "deleted",
        "installation": {"id": 123}
    }
    
    await github_webhook_service.handle_github_event(mock_db_session, "installation", payload)
    
    mock_db_session.query.assert_called_with(Installation)
    mock_db_session.query.return_value.filter.assert_called()
    mock_db_session.query.return_value.filter.return_value.delete.assert_called_once()

# Test that GH app suspension marks all linked repos as suspended
@pytest.mark.asyncio
async def test_handle_installation_suspend(mock_db_session):
    payload = {
        "action": "suspend",
        "installation": {"id": 123}
    }
    
    await github_webhook_service.handle_github_event(mock_db_session, "installation", payload)
    
    # Should update all linked repos for that installation to is_suspended=True
    mock_db_session.query.assert_called_with(Repository)
    mock_db_session.query.return_value.filter.return_value.update.assert_called_once_with({"is_suspended": True})

# Test that GH app unsuspension marks all linked repos as active again
@pytest.mark.asyncio
async def test_handle_installation_unsuspend(mock_db_session):
    payload = {
        "action": "unsuspend",
        "installation": {"id": 123}
    }
    
    await github_webhook_service.handle_github_event(mock_db_session, "installation", payload)
    
    # Should update all linked repos for that installation to is_suspended=False
    mock_db_session.query.assert_called_with(Repository)
    mock_db_session.query.return_value.filter.return_value.update.assert_called_once_with({"is_suspended": False})

# Test adding repos to an installation
@pytest.mark.asyncio
async def test_handle_repos_added(mock_db_session):
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
    
    await github_webhook_service.handle_github_event(mock_db_session, "installation_repositories", payload)
    
    mock_db_session.execute.assert_called_once()

# Test removing repos from an installation
@pytest.mark.asyncio
async def test_handle_repos_removed(mock_db_session):
    payload = {
        "action": "removed",
        "installation": {"id": 123},
        "repositories_removed": [
            {"full_name": "test-org/old-repo"}
        ]
    }
    
    await github_webhook_service.handle_github_event(mock_db_session, "installation_repositories", payload)
    
    mock_db_session.query.assert_called_with(Repository)
    mock_db_session.query.return_value.filter.return_value.delete.assert_called_once()

# Test that PR opened creates a drift event
@pytest.mark.asyncio
async def test_handle_pr_opened_success():
    mock_db = MagicMock()
    payload = {
        "action": "opened",
        "number": 123,
        "installation": {"id": 100},
        "repository": {"full_name": "owner/repo"},
        "pull_request": {
            "base": {"sha": "base123", "ref": "main"},
            "head": {"sha": "head456", "ref": "feature-branch"}
        },
    }
    
    # Mock the repo lookup
    mock_repo = MagicMock()
    mock_repo.id = "uuid-123"
    mock_repo.target_branch = "main"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    
    with patch("app.services.github_webhook_service.create_github_check_run", new_callable=AsyncMock) as mock_create_check, \
         patch("app.services.github_webhook_service.get_installation_access_token", new_callable=AsyncMock) as mock_get_token, \
         patch("app.services.github_webhook_service.pull_branches", new_callable=AsyncMock) as mock_pull:
        mock_get_token.return_value = "test_token"
        await github_webhook_service.handle_github_event(mock_db, "pull_request", payload)
    
    # Verify drift event was created with correct data
    mock_db.query.assert_called()
    mock_db.add.assert_called_once()
    args, _ = mock_db.add.call_args
    event = args[0]
    assert isinstance(event, DriftEvent)
    assert event.repo_id == "uuid-123"
    assert event.pr_number == 123
    assert event.base_sha == "base123"
    assert event.head_sha == "head456"
    assert event.processing_phase == "queued"

# Test that non relevant PR actions (like closing, assigning, etc.) are ignored
@pytest.mark.asyncio
async def test_handle_pr_ignored_action():
    mock_db = MagicMock()
    payload = {"action": "closed"}
    
    await github_webhook_service.handle_github_event(mock_db, "pull_request", payload)
    
    # Shouldn't add any records
    mock_db.add.assert_not_called()

# Test that PRs for unknown repos are handled gracefully
@pytest.mark.asyncio
async def test_repo_not_found_for_pr():
    mock_db = MagicMock()
    payload = {
        "action": "opened",
        "installation": {"id": 999},
        "repository": {"full_name": "unknown/repo"}
    }
    
    # Mock no repo found
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    await github_webhook_service.handle_github_event(mock_db, "pull_request", payload)
    
    # Should not create a drift event if the repo doesn't exist
    mock_db.add.assert_not_called()
