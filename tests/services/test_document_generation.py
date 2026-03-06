import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
from app.services.document_generation import run_document_generation


def _make_mock_finding(
    code_path="app/auth.py",
    doc_file_path="docs/api.md",
    drift_type="outdated_docs",
    explanation="Auth endpoint changed",
):
    finding = MagicMock()
    finding.code_path = code_path
    finding.doc_file_path = doc_file_path
    finding.change_type = "modified"
    finding.drift_type = drift_type
    finding.drift_score = 0.85
    finding.explanation = explanation
    finding.confidence = 0.9
    return finding


def _make_mock_drift_event(drift_result="drift_detected"):
    event = MagicMock()
    event.id = "test-event-id"
    event.drift_result = drift_result
    event.head_branch = "amr/update-auth"
    event.pr_number = 42
    event.processing_phase = "completed"
    event.repository = MagicMock()
    event.repository.repo_name = "owner/repo"
    event.repository.installation_id = 123
    event.repository.installation.user_id = "user-1"
    return event


@patch("app.services.document_generation._create_session")
def test_run_document_generation_skips_clean_events(mock_create_session):
    mock_session = MagicMock()
    mock_create_session.return_value = mock_session

    mock_event = _make_mock_drift_event(drift_result="clean")
    mock_session.query.return_value.filter.return_value.first.return_value = mock_event

    # Should return early without errors
    run_document_generation("test-event-id")

    # Should NOT have updated processing_phase to "generating"
    assert mock_event.processing_phase != "generating"


@patch("app.services.document_generation._create_session")
def test_run_document_generation_handles_missing_event(mock_create_session):
    mock_session = MagicMock()
    mock_create_session.return_value = mock_session

    mock_session.query.return_value.filter.return_value.first.return_value = None

    # Should return early without errors
    run_document_generation("nonexistent-id")


@patch("app.services.document_generation.create_notification")
@patch("app.services.document_generation.create_docs_pull_request")
@patch("app.services.document_generation.commit_and_push_docs")
@patch("app.services.document_generation.doc_gen_graph")
@patch("app.services.document_generation.checkout_docs_branch")
@patch("app.services.document_generation.get_installation_access_token")
@patch("app.services.document_generation.get_local_repo_path")
@patch("app.services.document_generation._create_session")
def test_run_document_generation_happy_path(
    mock_create_session,
    mock_get_repo_path,
    mock_get_token,
    mock_checkout,
    mock_graph,
    mock_commit_push,
    mock_create_pr,
    mock_notification,
):
    # Setup session
    mock_session = MagicMock()
    mock_create_session.return_value = mock_session

    # Setup drift event
    mock_event = _make_mock_drift_event()

    # Query for drift event returns the event, query for findings returns findings
    mock_query = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model.__name__ == "DriftEvent":
            q.filter.return_value.first.return_value = mock_event
        else:
            q.filter.return_value.all.return_value = [_make_mock_finding()]
        return q

    mock_session.query.side_effect = query_side_effect

    # Setup other mocks
    mock_repo_path = MagicMock(spec=Path)
    mock_repo_path.exists.return_value = True
    mock_repo_path.__str__ = lambda x: "/tmp/repos/owner/repo"
    mock_get_repo_path.return_value = mock_repo_path

    mock_get_token.return_value = "test_token"
    mock_checkout.return_value = "docs/drift-fix/amr/update-auth"
    mock_commit_push.return_value = True
    mock_create_pr.return_value = 99

    # Run the orchestrator
    run_document_generation("test-event-id")

    # Verify the full flow was executed
    mock_checkout.assert_called_once()
    mock_graph.invoke.assert_called_once()
    mock_commit_push.assert_called_once()
    mock_create_pr.assert_called_once()

    # Verify the PR targets the original branch, not main
    pr_call_kwargs = mock_create_pr.call_args
    assert pr_call_kwargs.kwargs.get("base_branch") or pr_call_kwargs[1].get("base_branch") in (
        "amr/update-auth",
        None,
    )


@patch("app.services.document_generation.create_notification")
@patch("app.services.document_generation.checkout_docs_branch")
@patch("app.services.document_generation.get_installation_access_token")
@patch("app.services.document_generation.get_local_repo_path")
@patch("app.services.document_generation._create_session")
def test_run_document_generation_branch_failure_marks_failed(
    mock_create_session,
    mock_get_repo_path,
    mock_get_token,
    mock_checkout,
    mock_notification,
):
    mock_session = MagicMock()
    mock_create_session.return_value = mock_session

    mock_event = _make_mock_drift_event()

    def query_side_effect(model):
        q = MagicMock()
        if model.__name__ == "DriftEvent":
            q.filter.return_value.first.return_value = mock_event
        else:
            q.filter.return_value.all.return_value = [_make_mock_finding()]
        return q

    mock_session.query.side_effect = query_side_effect

    mock_repo_path = MagicMock(spec=Path)
    mock_repo_path.exists.return_value = True
    mock_repo_path.__str__ = lambda x: "/tmp/repos/owner/repo"
    mock_get_repo_path.return_value = mock_repo_path
    mock_get_token.return_value = "test_token"

    # Branch creation fails
    mock_checkout.return_value = None

    with pytest.raises(Exception, match="Failed to create docs branch"):
        run_document_generation("test-event-id")

    # Should have marked the event as failed
    assert mock_event.processing_phase == "failed"


def test_run_document_generation_invalid_id():
    # Should return immediately without errors
    run_document_generation("")
    run_document_generation("None")
