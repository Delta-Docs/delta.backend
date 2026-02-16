import time
import asyncio
import subprocess
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import DriftEvent, CodeChange
from app.services.github_api import update_github_check_run


# Creates a separate SQLAlchemy session for use in background tasks
def _create_session():
    engine = create_engine(settings.POSTGRES_CONNECTION_URL, pool_pre_ping=True)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session()

# Extracts code changes and its metadata from git diff
def _extract_and_save_code_changes(session, drift_event):
    repo_full_name = drift_event.repository.repo_name
    base_sha = drift_event.base_sha
    head_sha = drift_event.head_sha
    
    # Get the locally cloned repo path
    owner, repo_name = repo_full_name.split("/")
    repos_base = Path(settings.REPOS_BASE_PATH)
    repo_path = repos_base / owner / repo_name
    
    if not repo_path.exists():
        raise Exception(f"Local repository not found at {repo_path}")
    
    try:
        # Get a list of changed files using git diff
        result = subprocess.run(
            ["git", "-C", str(repo_path), "diff", "--name-status", f"{base_sha}...{head_sha}"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise Exception(f"Git diff failed: {result.stderr}")
        
        # Parse the git diff output and create CodeChange records
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
                
            parts = line.split("\t")
            if len(parts) < 2:
                continue
                
            status = parts[0]
            file_path = parts[1]
            
            # Map git file status to change_type
            change_type_map = {
                "A": "added",
                "M": "modified",
                "D": "deleted"
            }
            
            change_type = change_type_map.get(status, "modified")
            
            # Determine if the changed file is a code file (excluding common non-code files)
            non_code_extensions = {".md", ".txt", ".rst", ".pdf", ".doc", ".docx", ".jpg", ".png", ".gif", ".svg"}
            is_code = not any(file_path.lower().endswith(ext) for ext in non_code_extensions)
            
            # Create CodeChange record in DB
            code_change = CodeChange(
                drift_event_id=drift_event.id,
                file_path=file_path,
                change_type=change_type,
                is_code=is_code
            )
            session.add(code_change)
        
        session.commit()
        
    except subprocess.TimeoutExpired:
        raise Exception(f"Timeout while extracting code changes for {repo_full_name}")
    except Exception as e:
        session.rollback()
        raise Exception(f"Error extracting code changes: {str(e)}")

# Main task that orchestrates the drift analysis process for a PR
def run_drift_analysis(drift_event_id: str):
    session = _create_session()

    try:
        # Fetch the drift event from the DB
        drift_event = session.query(DriftEvent).filter(DriftEvent.id == drift_event_id).first()

        if not drift_event:
            return

        repo_full_name = drift_event.repository.repo_name
        installation_id = drift_event.repository.installation_id
        check_run_id = drift_event.check_run_id

        # Mark the drift event as in scouting phase
        drift_event.processing_phase = "scouting"
        session.commit()

        # Update GitHub check run (if present) as in progress - Scouting Phase
        if check_run_id:
            asyncio.run(update_github_check_run(
                repo_full_name=repo_full_name,
                check_run_id=check_run_id,
                installation_id=installation_id,
                status="in_progress",
                title="Scouting Changes",
                summary="Extracting code changes from the PR..."
            ))

        # Extract and save code changes from git diff
        _extract_and_save_code_changes(session, drift_event)

        # TODO: Add more steps of code analysis

        # Mark as completed and set result
        drift_event.processing_phase = "completed"
        drift_event.drift_result = "clean"
        session.commit()

        # Update GitHub check run (if present) as successful with results
        if check_run_id:
            asyncio.run(update_github_check_run(
                repo_full_name=repo_full_name,
                check_run_id=check_run_id,
                installation_id=installation_id,
                status="completed",
                conclusion="success",
                title="No Drift Detected",
                summary="All documentation is up to date."
            ))

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
