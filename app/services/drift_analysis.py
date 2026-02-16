import time
import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import DriftEvent
from app.services.github_api import update_github_check_run


# Creates a separate SQLAlchemy session for use in background tasks
def _create_session():
    engine = create_engine(settings.POSTGRES_CONNECTION_URL, pool_pre_ping=True)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session()

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

        # Mark the event as analyzing and commit
        drift_event.processing_phase = "analyzing"
        session.commit()

        # Update the GitHub check run (if present) as in progress
        if check_run_id:
            asyncio.run(update_github_check_run(
                repo_full_name=repo_full_name,
                check_run_id=check_run_id,
                installation_id=installation_id,
                status="in_progress",
                title="Analyzing Changes",
                summary="Running drift analysis on your documentation..."
            ))

        time.sleep(10) # Simulate drift analysis task

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
