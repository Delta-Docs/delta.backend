from unittest.mock import AsyncMock, MagicMock, patch

from app.services.workflow.nodes.aggregate_results import aggregate_results
from app.services.workflow.state import DriftAnalysisState


# Helper function to build a minimal state dictionary
def _make_state(
    findings: list[dict] | None = None,
    change_elements: list[dict] | None = None,
    analysis_payloads: list[dict] | None = None,
    drift_event_id: str = "evt-1",
) -> DriftAnalysisState:
    return {
        "drift_event_id": drift_event_id,
        "base_sha": "abc123",
        "head_sha": "def456",
        "session": MagicMock(),
        "repo_path": "/tmp/repo",
        "docs_root_path": "/docs",
        "change_elements": change_elements or [],
        "analysis_payloads": analysis_payloads or [],
        "findings": findings or [],
    }


# Helper function to create a mock DriftEvent with repository relationship.
def _make_drift_event(check_run_id=None, repo_name="owner/repo", installation_id=12345):
    repo = MagicMock()
    repo.repo_name = repo_name
    repo.installation_id = installation_id

    event = MagicMock()
    event.check_run_id = check_run_id
    event.repository = repo
    return event


# Tests that empty findings produce a clean result with score 0.0 and no DriftFinding rows.
def test_no_findings_clean():
    state = _make_state(findings=[])
    drift_event = _make_drift_event()
    state["session"].query.return_value.filter.return_value.first.return_value = drift_event

    result = aggregate_results(state)

    assert result == {"findings": []}

    # DriftEvent should be updated to clean
    assert drift_event.overall_drift_score == 0.0
    assert drift_event.drift_result == "clean"
    assert drift_event.processing_phase == "completed"
    assert "No documentation drift" in drift_event.summary

    # No DriftFinding rows should be added
    state["session"].add.assert_not_called()
    state["session"].commit.assert_called_once()


# Tests that findings present result in drift_detected and DriftFinding rows being created.
def test_drift_detected_persists_findings():
    findings = [
        {
            "code_path": "src/routes.py",
            "change_type": "modified",
            "drift_type": "outdated_docs",
            "drift_score": 0.85,
            "explanation": "Route /date renamed to /today",
            "confidence": 0.9,
        },
    ]
    state = _make_state(findings=findings)
    drift_event = _make_drift_event()
    state["session"].query.return_value.filter.return_value.first.return_value = drift_event

    with patch("app.services.workflow.nodes.aggregate_results.DriftFinding") as mock_finding_cls:
        mock_finding_cls.return_value = MagicMock()
        result = aggregate_results(state)

    assert result == {"findings": []}
    assert drift_event.drift_result == "drift_detected"
    assert drift_event.overall_drift_score == 0.85
    assert drift_event.processing_phase == "completed"

    # Only one DriftFinding row should be staged
    state["session"].add.assert_called_once()


# Tests that a finding with missing_docs sets drift_result to 'missing_docs'.
def test_missing_docs_result():
    findings = [
        {
            "code_path": "src/new.py",
            "change_type": "added",
            "drift_type": "missing_docs",
            "drift_score": 1.0,
            "explanation": "New code has no docs",
            "confidence": 1.0,
        },
        {
            "code_path": "src/routes.py",
            "change_type": "modified",
            "drift_type": "outdated_docs",
            "drift_score": 0.7,
            "explanation": "Route changed",
            "confidence": 0.8,
        },
    ]
    state = _make_state(findings=findings)
    drift_event = _make_drift_event()
    state["session"].query.return_value.filter.return_value.first.return_value = drift_event

    with patch("app.services.workflow.nodes.aggregate_results.DriftFinding") as mock_finding_cls:
        mock_finding_cls.return_value = MagicMock()
        aggregate_results(state)

    assert drift_event.drift_result == "missing_docs"
    assert drift_event.overall_drift_score == 1.0

    # Two DriftFinding rows should be staged
    assert state["session"].add.call_count == 2


# Tests that when check_run_id exists, update_github_check_run is called.
@patch(
    "app.services.workflow.nodes.aggregate_results.update_github_check_run", new_callable=AsyncMock
)
def test_check_run_updated(mock_update):
    findings = [
        {
            "code_path": "src/api.py",
            "change_type": "modified",
            "drift_type": "outdated_docs",
            "drift_score": 0.8,
            "explanation": "API changed",
            "confidence": 0.9,
        },
    ]
    state = _make_state(findings=findings)
    drift_event = _make_drift_event(check_run_id=999)
    state["session"].query.return_value.filter.return_value.first.return_value = drift_event

    with patch("app.services.workflow.nodes.aggregate_results.DriftFinding") as mock_finding_cls:
        mock_finding_cls.return_value = MagicMock()
        aggregate_results(state)

    mock_update.assert_called_once()


# Tests that when there is no check_run_id, the update helper is not called.
@patch(
    "app.services.workflow.nodes.aggregate_results.update_github_check_run", new_callable=AsyncMock
)
def test_check_run_skipped_when_none(mock_update):
    state = _make_state(findings=[])
    drift_event = _make_drift_event(check_run_id=None)
    state["session"].query.return_value.filter.return_value.first.return_value = drift_event

    aggregate_results(state)

    mock_update.assert_not_called()


# Tests that the agent_logs JSONB field is populated.
def test_agent_logs_populated():
    state = _make_state(
        findings=[],
        change_elements=[
            {"file_path": "a.py", "elements": ["Foo"], "old_elements": []},
            {"file_path": "b.py", "elements": ["Bar"], "old_elements": []},
        ],
        analysis_payloads=[{"code_path": "a.py"}],
    )
    drift_event = _make_drift_event()
    state["session"].query.return_value.filter.return_value.first.return_value = drift_event

    aggregate_results(state)

    logs = drift_event.agent_logs
    assert "Scouting" in logs
    assert "Retrieval" in logs
    assert "Analysis" in logs
    assert "Result" in logs
    assert "a.py" in logs["Scouting"]
    assert "b.py" in logs["Scouting"]
    assert "clean" in logs["Result"]
