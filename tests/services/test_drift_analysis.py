import pytest
import subprocess
from unittest.mock import MagicMock, patch
from pathlib import Path
from uuid import uuid4

from app.services.drift_analysis import _extract_and_save_code_changes, run_drift_analysis


# Helper to create a mock drift event with repository info
def _make_drift_event(base_sha="abc123", head_sha="def456", repo_name="owner/repo"):
    drift_event = MagicMock()
    drift_event.id = uuid4()
    drift_event.base_sha = base_sha
    drift_event.head_sha = head_sha
    drift_event.repository.repo_name = repo_name
    return drift_event


# Test extracting code changes with added, modified, and deleted files
def test_extract_and_save_code_changes_success():
    drift_event = _make_drift_event()
    session = MagicMock()

    # 3 Changed Files
    git_diff_output = "A\tsrc/new_file.py\nM\tsrc/existing.py\nD\tsrc/removed.py\n"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = git_diff_output

    with (
        patch("subprocess.run", return_value=mock_result),
        patch("app.services.drift_analysis.get_local_repo_path") as mock_path,
    ):
        mock_path.return_value = MagicMock(spec=Path, exists=MagicMock(return_value=True))

        _extract_and_save_code_changes(session, drift_event)

    # This should add 3 CodeChange records
    assert session.add.call_count == 3
    session.commit.assert_called_once()

    # Verify the change types recorded
    added_changes = [c.args[0] for c in session.add.call_args_list]
    change_types = [c.change_type for c in added_changes]
    assert change_types == ["added", "modified", "deleted"]


# Test code vs non code file detection in code changes
def test_extract_and_save_code_changes_is_code_detection():
    drift_event = _make_drift_event()
    session = MagicMock()

    # 4 Changed Files with different types
    git_diff_output = "A\tsrc/main.py\nA\tREADME.md\nA\timage.png\nA\tsrc/utils.js\n"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = git_diff_output

    with (
        patch("subprocess.run", return_value=mock_result),
        patch("app.services.drift_analysis.get_local_repo_path") as mock_path,
    ):
        mock_path.return_value = MagicMock(spec=Path, exists=MagicMock(return_value=True))

        _extract_and_save_code_changes(session, drift_event)

    assert session.add.call_count == 4

    added_changes = [c.args[0] for c in session.add.call_args_list]
    is_code_flags = {c.file_path: c.is_code for c in added_changes}

    assert is_code_flags["src/main.py"] is True
    assert is_code_flags["README.md"] is False
    assert is_code_flags["image.png"] is False
    assert is_code_flags["src/utils.js"] is True


# Test with empty git diff output (no changes should be detected)
def test_extract_and_save_code_changes_empty_diff():
    drift_event = _make_drift_event()
    session = MagicMock()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""

    with (
        patch("subprocess.run", return_value=mock_result),
        patch("app.services.drift_analysis.get_local_repo_path") as mock_path,
    ):
        mock_path.return_value = MagicMock(spec=Path, exists=MagicMock(return_value=True))

        _extract_and_save_code_changes(session, drift_event)

    session.add.assert_not_called()
    session.commit.assert_called_once()


# Test raises exception when local repository doesn't exist
def test_extract_and_save_code_changes_repo_not_found():
    drift_event = _make_drift_event()
    session = MagicMock()

    with patch("app.services.drift_analysis.get_local_repo_path") as mock_path:
        mock_path.return_value = MagicMock(spec=Path, exists=MagicMock(return_value=False))

        with pytest.raises(Exception, match="Local repository not found"):
            _extract_and_save_code_changes(session, drift_event)


# Test raises exception when git diff command fails
def test_extract_and_save_code_changes_git_diff_failure():
    drift_event = _make_drift_event()
    session = MagicMock()

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: bad revision"

    with (
        patch("subprocess.run", return_value=mock_result),
        patch("app.services.drift_analysis.get_local_repo_path") as mock_path,
    ):
        mock_path.return_value = MagicMock(spec=Path, exists=MagicMock(return_value=True))

        with pytest.raises(Exception, match="Git diff failed"):
            _extract_and_save_code_changes(session, drift_event)

    session.rollback.assert_called_once()


# Test raises exception on subprocess timeout
def test_extract_and_save_code_changes_timeout():
    drift_event = _make_drift_event()
    session = MagicMock()

    with (
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 60)),
        patch("app.services.drift_analysis.get_local_repo_path") as mock_path,
    ):
        mock_path.return_value = MagicMock(spec=Path, exists=MagicMock(return_value=True))

        with pytest.raises(Exception, match="Timeout while extracting code changes"):
            _extract_and_save_code_changes(session, drift_event)


# Test unknown git status code defaults to "modified"
def test_extract_and_save_code_changes_unknown_status():
    drift_event = _make_drift_event()
    session = MagicMock()

    git_diff_output = "R\tsrc/renamed.py\n"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = git_diff_output

    with (
        patch("subprocess.run", return_value=mock_result),
        patch("app.services.drift_analysis.get_local_repo_path") as mock_path,
    ):
        mock_path.return_value = MagicMock(spec=Path, exists=MagicMock(return_value=True))

        _extract_and_save_code_changes(session, drift_event)

    added_change = session.add.call_args_list[0].args[0]
    assert added_change.change_type == "modified"


# Test malformed git diff line (insufficient parts) is skipped
def test_extract_and_save_code_changes_skips_malformed_lines():
    drift_event = _make_drift_event()
    session = MagicMock()

    git_diff_output = "A\tsrc/valid.py\nmalformed_line\n\nA\tsrc/other.py\n"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = git_diff_output

    with (
        patch("subprocess.run", return_value=mock_result),
        patch("app.services.drift_analysis.get_local_repo_path") as mock_path,
    ):
        mock_path.return_value = MagicMock(spec=Path, exists=MagicMock(return_value=True))

        _extract_and_save_code_changes(session, drift_event)

    # Only 2 valid lines should produce CodeChange records
    assert session.add.call_count == 2


# Test that correct git command is constructed with base and head SHAs
def test_extract_and_save_code_changes_correct_git_command():
    drift_event = _make_drift_event(
        base_sha="sha_base", head_sha="sha_head", repo_name="org/project"
    )
    session = MagicMock()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""

    with (
        patch("subprocess.run", return_value=mock_result) as mock_run,
        patch("app.services.drift_analysis.get_local_repo_path") as mock_path,
    ):
        mock_repo_path = MagicMock(spec=Path, exists=MagicMock(return_value=True))
        mock_path.return_value = mock_repo_path

        _extract_and_save_code_changes(session, drift_event)

    args = mock_run.call_args[0][0]
    assert args[0] == "git"
    assert args[1] == "-C"
    assert args[2] == str(mock_repo_path)
    assert args[3] == "diff"
    assert args[4] == "--name-status"
    assert args[5] == "sha_base...sha_head"


# Helper to set up a mock session with a drift event
def _setup_run_mocks(drift_event_id=None, docs_root_path="/docs"):
    drift_event_id = drift_event_id or str(uuid4())

    drift_event = MagicMock()
    drift_event.id = drift_event_id
    drift_event.repository.repo_name = "owner/repo"
    drift_event.repository.installation_id = 99
    drift_event.repository.docs_root_path = docs_root_path
    drift_event.check_run_id = 12345
    drift_event.processing_phase = "queued"
    drift_event.drift_result = "pending"

    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = drift_event

    return session, drift_event


# Test run_drift_analysis when drift event is not found
def test_run_drift_analysis_event_not_found():
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None

    with patch("app.services.drift_analysis._create_session", return_value=session):
        run_drift_analysis("nonexistent-id")

    session.close.assert_called_once()


# Test run_drift_analysis always closes the session even on error
def test_run_drift_analysis_session_closed_on_error():
    session, drift_event = _setup_run_mocks()

    with (
        patch("app.services.drift_analysis._create_session", return_value=session),
        patch(
            "app.services.drift_analysis.get_local_repo_path",
            side_effect=RuntimeError("boom"),
        ),
    ):
        with pytest.raises(RuntimeError):
            run_drift_analysis(str(drift_event.id))

    session.rollback.assert_called_once()
    session.close.assert_called_once()


# Test run_drift_analysis sets analyzing phase
def test_run_drift_analysis_sets_analyzing_phase():
    session, drift_event = _setup_run_mocks()
    phase_at_commit = []

    original_commit = session.commit

    def capture_phase():
        phase_at_commit.append(drift_event.processing_phase)
        original_commit()

    session.commit = capture_phase

    with (
        patch("app.services.drift_analysis._create_session", return_value=session),
        patch("app.services.drift_analysis.get_local_repo_path") as mock_path,
        patch("app.services.drift_analysis._extract_and_save_code_changes"),
        patch("app.services.drift_analysis.drift_analysis_graph") as mock_graph,
    ):
        mock_path.return_value = Path("/repos/owner/repo")
        mock_graph.invoke.return_value = {"change_elements": [], "findings": []}

        run_drift_analysis(str(drift_event.id))

    # At commit time, phase should be "analyzing"
    assert phase_at_commit[0] == "analyzing"


# Test run_drift_analysis builds initial state with correct values
def test_run_drift_analysis_builds_initial_state():
    session, drift_event = _setup_run_mocks(docs_root_path="/documentation")
    drift_event.id = "test-event-id"
    drift_event.base_sha = "base123"
    drift_event.head_sha = "head456"

    with (
        patch("app.services.drift_analysis._create_session", return_value=session),
        patch("app.services.drift_analysis.get_local_repo_path") as mock_path,
        patch("app.services.drift_analysis._extract_and_save_code_changes"),
        patch("app.services.drift_analysis.drift_analysis_graph") as mock_graph,
    ):
        mock_path.return_value = Path("/repos/owner/repo")
        mock_graph.invoke.return_value = {"change_elements": [], "findings": []}

        run_drift_analysis(str(drift_event.id))

        # Verify get_local_repo_path was called with the repo name
        mock_path.assert_called_once_with("owner/repo")

        # Verify the initial state passed to the graph has all correct values
        invoked_state = mock_graph.invoke.call_args[0][0]
        assert invoked_state["drift_event_id"] == "test-event-id"
        assert invoked_state["base_sha"] == "base123"
        assert invoked_state["head_sha"] == "head456"
        assert invoked_state["session"] is session
        assert invoked_state["repo_path"] == str(Path("/repos/owner/repo"))
        assert invoked_state["docs_root_path"] == "/documentation"
        assert invoked_state["change_elements"] == []
        assert invoked_state["analysis_payloads"] == []
        assert invoked_state["findings"] == []
