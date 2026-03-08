from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db_connection, get_current_user
from app.models.drift import DriftEvent, DriftFinding, CodeChange
from app.models.user import User
from app.models.installation import Installation
from app.models.repository import Repository
from app.schemas.drift import (
    DriftEventResponse,
    DriftEventDetailResponse,
    DriftFindingResponse,
    CodeChangeResponse,
)
from app.schemas.repository import RepositorySettings, RepositoryActivation, RepositoryResponse

router = APIRouter()


# Endpoint to get all linked repos for the current user
@router.get("/", response_model=list[RepositoryResponse])
def get_repos(
    db: Session = Depends(get_db_connection), current_user: User = Depends(get_current_user)
):
    repos = (
        db.query(Repository)
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .filter(Installation.user_id == current_user.id)
        .all()
    )
    return repos


# Endpoint to Update repo settings like docs path, etc
@router.put("/{repo_id}/settings", response_model=RepositoryResponse)
def update_repo_settings(
    repo_id: UUID,
    settings: RepositorySettings,
    db: Session = Depends(get_db_connection),
    current_user: User = Depends(get_current_user),
):
    # Making sure user actually owns this repo
    repo = (
        db.query(Repository)
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .filter(Repository.id == repo_id, Installation.user_id == current_user.id)
        .first()
    )

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Update only the fields that were received
    update_data = settings.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(repo, field, value)

    db.commit()
    db.refresh(repo)
    return repo


# Endpoint to toggle repo active status
@router.patch("/{repo_id}/activate", response_model=RepositoryResponse)
def toggle_repo_activation(
    repo_id: UUID,
    activation: RepositoryActivation,
    db: Session = Depends(get_db_connection),
    current_user: User = Depends(get_current_user),
):
    # Making sure user owns this repo
    repo = (
        db.query(Repository)
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .filter(Repository.id == repo_id, Installation.user_id == current_user.id)
        .first()
    )

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Update repo active status
    repo.is_active = activation.is_active
    db.commit()
    db.refresh(repo)
    return repo


# Endpoint to get all drift events for a repo
@router.get("/{repo_id}/drift-events", response_model=list[DriftEventResponse])
def get_drift_events(
    repo_id: UUID,
    db: Session = Depends(get_db_connection),
    current_user: User = Depends(get_current_user),
):
    # Making sure the user actually owns the repo
    repo = (
        db.query(Repository)
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .filter(Repository.id == repo_id, Installation.user_id == current_user.id)
        .first()
    )

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Returning the drift events
    events = (
        db.query(DriftEvent)
        .filter(DriftEvent.repo_id == repo_id)
        .order_by(DriftEvent.created_at.desc())
        .all()
    )
    return events


# Endpoint to get a single drift event with full details
@router.get("/{repo_id}/drift-events/{event_id}", response_model=DriftEventDetailResponse)
def get_drift_event_detail(
    repo_id: UUID,
    event_id: UUID,
    db: Session = Depends(get_db_connection),
    current_user: User = Depends(get_current_user),
):
    # Verify user owns the repo
    repo = (
        db.query(Repository)
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .filter(Repository.id == repo_id, Installation.user_id == current_user.id)
        .first()
    )

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Get the drift event
    event = (
        db.query(DriftEvent)
        .filter(DriftEvent.id == event_id, DriftEvent.repo_id == repo_id)
        .first()
    )

    if not event:
        raise HTTPException(status_code=404, detail="Drift event not found")

    return event


# Endpoint to get all findings for a drift event
@router.get(
    "/{repo_id}/drift-events/{event_id}/findings", response_model=list[DriftFindingResponse]
)
def get_drift_findings(
    repo_id: UUID,
    event_id: UUID,
    db: Session = Depends(get_db_connection),
    current_user: User = Depends(get_current_user),
):
    # Verify user owns the repo
    repo = (
        db.query(Repository)
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .filter(Repository.id == repo_id, Installation.user_id == current_user.id)
        .first()
    )

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Verify event exists for this repo
    event = (
        db.query(DriftEvent)
        .filter(DriftEvent.id == event_id, DriftEvent.repo_id == repo_id)
        .first()
    )

    if not event:
        raise HTTPException(status_code=404, detail="Drift event not found")

    # Get findings
    findings = (
        db.query(DriftFinding)
        .filter(DriftFinding.drift_event_id == event_id)
        .order_by(DriftFinding.created_at.desc())
        .all()
    )
    return findings


# Endpoint to get all code changes for a drift event
@router.get(
    "/{repo_id}/drift-events/{event_id}/code-changes", response_model=list[CodeChangeResponse]
)
def get_code_changes(
    repo_id: UUID,
    event_id: UUID,
    db: Session = Depends(get_db_connection),
    current_user: User = Depends(get_current_user),
):
    # Verify user owns the repo
    repo = (
        db.query(Repository)
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .filter(Repository.id == repo_id, Installation.user_id == current_user.id)
        .first()
    )

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Verify event exists for this repo
    event = (
        db.query(DriftEvent)
        .filter(DriftEvent.id == event_id, DriftEvent.repo_id == repo_id)
        .first()
    )

    if not event:
        raise HTTPException(status_code=404, detail="Drift event not found")

    # Get code changes
    changes = (
        db.query(CodeChange)
        .filter(CodeChange.drift_event_id == event_id)
        .all()
    )
    return changes
