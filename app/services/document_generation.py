import asyncio
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import DriftEvent, DriftFinding
from app.services.git_service import (
    get_local_repo_path,
    checkout_docs_branch,
    commit_and_push_docs,
)
from app.services.github_api import (
    get_installation_access_token,
    create_docs_pull_request,
)
from app.services.notification_service import create_notification
from app.agents.state import DocGenState
from app.agents.doc_gen_graph import doc_gen_graph


# Creates a separate SQLAlchemy session for use in background tasks
def _create_session():
    engine = create_engine(settings.POSTGRES_CONNECTION_URL, pool_pre_ping=True)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session()


# Main task that orchestrates the document generation process
def run_document_generation(drift_event_id: str):
    if not drift_event_id or drift_event_id == "None":
        print(f"ERROR: invalid drift_event_id: {drift_event_id!r}")
        return

    session = _create_session()

    try:
        drift_event = session.query(DriftEvent).filter(DriftEvent.id == drift_event_id).first()

        if not drift_event:
            print(f"Event {drift_event_id} not found in DB. Aborting.")
            return

        # Check that drift was actually detected before generating docs
        if drift_event.drift_result not in ("drift_detected", "missing_docs"):
            print(f"No drift to resolve for event {drift_event_id}. Skipping.")
            return

        # Update processing phase to generating
        drift_event.processing_phase = "generating"
        session.commit()

        # Gather drift findings from the DB
        findings = (
            session.query(DriftFinding)
            .filter(DriftFinding.drift_event_id == drift_event_id)
            .all()
        )

        if not findings:
            print(f"No drift findings for event {drift_event_id}. Skipping.")
            return

        drift_findings = [
            {
                "code_path": f.code_path,
                "doc_file_path": f.doc_file_path,
                "change_type": f.change_type,
                "drift_type": f.drift_type,
                "drift_score": f.drift_score,
                "explanation": f.explanation,
                "confidence": f.confidence,
                "matched_doc_paths": [f.doc_file_path] if f.doc_file_path else [],
            }
            for f in findings
        ]

        # Resolve paths and get auth token
        repo = drift_event.repository
        repo_full_name = repo.repo_name
        installation_id = repo.installation_id
        original_branch = drift_event.head_branch
        pr_number = drift_event.pr_number

        repo_path = get_local_repo_path(repo_full_name)

        if not repo_path.exists():
            raise Exception(f"Local repository not found at {repo_path}")

        # Get the access token for git and API operations
        access_token = asyncio.run(get_installation_access_token(installation_id))

        # Step 1: Create the docs branch
        docs_branch = asyncio.run(
            checkout_docs_branch(
                repo_path=str(repo_path),
                original_branch=original_branch,
                access_token=access_token,
                repo_full_name=repo_full_name,
            )
        )

        if not docs_branch:
            raise Exception("Failed to create docs branch")

        # Step 2: Run the LangGraph doc generation pipeline
        initial_state: DocGenState = {
            "drift_findings": drift_findings,
            "repo_path": str(repo_path),
            "target_files": [],
            "rewrite_results": [],
        }

        doc_gen_graph.invoke(initial_state)

        # Step 3: Commit and push the modified .md files
        push_success = asyncio.run(
            commit_and_push_docs(
                repo_path=str(repo_path),
                pr_number=pr_number,
                access_token=access_token,
                repo_full_name=repo_full_name,
            )
        )

        if not push_success:
            raise Exception("Failed to commit and push documentation changes")

        # Step 4: Create the Pull Request
        changes_summary = "\n".join(
            f"- `{f.code_path}`: {f.explanation or f.drift_type}"
            for f in findings
        )

        docs_pr_number = asyncio.run(
            create_docs_pull_request(
                installation_id=installation_id,
                repo_full_name=repo_full_name,
                head_branch=docs_branch,
                base_branch=original_branch,
                pr_number=pr_number,
                changes_summary=changes_summary,
            )
        )

        if docs_pr_number:
            print(f"Created docs PR #{docs_pr_number} for drift event {drift_event_id}")
        else:
            print(f"Warning: docs PR creation returned None for event {drift_event_id}")

        # Mark as completed
        drift_event.processing_phase = "completed"
        drift_event.completed_at = datetime.now(timezone.utc)
        session.commit()

        # Create a notification for the user
        if repo.installation and repo.installation.user_id:
            user_id = repo.installation.user_id
            notif_content = (
                f"Documentation auto-fix PR"
                f"{f' #{docs_pr_number}' if docs_pr_number else ''} "
                f"created for PR #{pr_number} in {repo_full_name}."
            )
            create_notification(session, user_id, notif_content)

    except Exception as e:
        print(f"ERROR in document generation: {e}")
        session.rollback()

        # Mark the event as failed
        try:
            drift_event = session.query(DriftEvent).filter(DriftEvent.id == drift_event_id).first()
            if drift_event:
                drift_event.processing_phase = "failed"
                drift_event.error_message = str(e)

                if drift_event.repository and drift_event.repository.installation:
                    user_id = drift_event.repository.installation.user_id
                    repo_name = drift_event.repository.repo_name
                    if user_id:
                        create_notification(
                            session,
                            user_id,
                            f"Document generation for PR #{drift_event.pr_number} in {repo_name} failed: {str(e)}",
                        )

                session.commit()
        except Exception as inner_e:
            print(f"Failed to mark drift event as failed: {inner_e}")
            session.rollback()

        raise
    finally:
        session.close()
