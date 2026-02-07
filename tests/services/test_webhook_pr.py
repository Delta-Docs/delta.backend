import unittest
from unittest.mock import MagicMock, ANY
from app.services.github_webhook_service import handle_github_event
from app.models.repository import Repository
from app.models.drift import DriftEvent

class TestWebhookPR(unittest.TestCase):
    def test_handle_pr_opened_success(self):
        mock_db = MagicMock()
        payload = {
            "action": "opened",
            "number": 123,
            "installation": {"id": 100},
            "repository": {"full_name": "owner/repo"},
            "pull_request": {
                "base": {"sha": "base123"},
                "head": {"sha": "head456"}
            },
        }
        
        mock_repo = MagicMock()
        mock_repo.id = "uuid-123"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
        
        handle_github_event(mock_db, "pull_request", payload)
        
        mock_db.query.assert_called()
        mock_db.add.assert_called_once()
        args, _ = mock_db.add.call_args
        event = args[0]
        self.assertIsInstance(event, DriftEvent)
        self.assertEqual(event.repo_id, "uuid-123")
        self.assertEqual(event.pr_number, 123)
        self.assertEqual(event.base_sha, "base123")
        self.assertEqual(event.head_sha, "head456")
        self.assertEqual(event.processing_phase, "queued")

    def test_handle_pr_ignored_action(self):
        mock_db = MagicMock()
        payload = {"action": "closed"}
        
        handle_github_event(mock_db, "pull_request", payload)
        
        mock_db.add.assert_not_called()

    def test_repo_not_found(self):
        mock_db = MagicMock()
        payload = {
            "action": "opened",
            "installation": {"id": 999},
            "repository": {"full_name": "unknown/repo"}
        }
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        handle_github_event(mock_db, "pull_request", payload)
        
        mock_db.add.assert_not_called()
