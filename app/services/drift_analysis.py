import time
import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import DriftEvent
from app.services.github_api import update_github_check_run


def _create_session():
    engine = create_engine(settings.POSTGRES_CONNECTION_URL, pool_pre_ping=True)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session()


def sample_task(drift_event_id: str):
    session = _create_session()

    try:
        drift_event = session.query(DriftEvent).filter(DriftEvent.id == drift_event_id).first()

        if not drift_event:
            return

        repo_full_name = drift_event.repository.repo_name
        installation_id = drift_event.repository.installation_id
        check_run_id = drift_event.check_run_id

        drift_event.processing_phase = "analyzing"
        session.commit()

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

        drift_event.processing_phase = "completed"
        drift_event.drift_result = "clean"
        session.commit()

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
