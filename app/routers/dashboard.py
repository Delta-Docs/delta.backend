from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.deps import get_db_connection, get_current_user
from app.models.user import User
from app.models.installation import Installation
from app.models.repository import Repository
from app.models.drift import DriftEvent
from app.services.github_api import get_repo_details

router = APIRouter()

@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db_connection),
    current_user: User = Depends(get_current_user)
):
    installations_count = int(
        db.query(func.count(Installation.id))
        .filter(Installation.user_id == current_user.id)
        .scalar() or 0
    )
    
    repos_count = int(
        db.query(func.count(Repository.id))
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .filter(Installation.user_id == current_user.id)
        .scalar() or 0
    )
    
    drift_events_count = int(
        db.query(func.count(DriftEvent.id))
        .join(Repository, DriftEvent.repo_id == Repository.id)
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .filter(Installation.user_id == current_user.id)
        .scalar() or 0
    )
    
    # TODO: Implement logic to calculate the count of PRs raised for review
    pr_waiting_count = 0
    
    return {
        "installations_count": installations_count,
        "repos_linked_count": repos_count,
        "drift_events_count": drift_events_count,
        "pr_waiting_count": pr_waiting_count
    }

@router.get("/repos")
async def get_dashboard_repos(
    db: Session = Depends(get_db_connection),
    current_user: User = Depends(get_current_user)
):
    # First, sync repositories from GitHub API for all user installations
    user_installations = (
        db.query(Installation)
        .filter(Installation.user_id == current_user.id)
        .all()
    )
    
    for installation in user_installations:
        try:
            # Fetch repos from GitHub API
            from app.services.github_api import get_installation_repos
            github_repos = await get_installation_repos(installation.installation_id)
            
            # Sync to database
            from sqlalchemy.dialects.postgresql import insert
            if github_repos:
                values_list = []
                for repo in github_repos:
                    values_list.append({
                        "installation_id": installation.installation_id,
                        "repo_name": repo["full_name"],
                        "is_active": True,
                        "avatar_url": repo.get("owner", {}).get("avatar_url")
                    })
                
                stmt = insert(Repository).values(values_list)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['installation_id', 'repo_name'],
                    set_={"is_active": True, "avatar_url": stmt.excluded.avatar_url}
                )
                db.execute(stmt)
                db.commit()
        except Exception:
            # Silently continue if sync fails for an installation
            continue
    
    # Now fetch from database
    recent_repos = (
        db.query(Repository)
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .filter(Installation.user_id == current_user.id)
        .order_by(Repository.created_at.desc())
        .all()
    )
    
    results = []
    for repo in recent_repos:
        repo_owner, repo_name = repo.repo_name.split('/')
        try:
            details = await get_repo_details(repo.installation_id, repo_owner, repo_name)
            results.append(details)
        except Exception:
             results.append({
                "name": repo.repo_name,
                "description": "Error fetching details",
                "language": "Unknown",
                "stargazers_count": 0,
                "forks_count": 0,
                "avatar_url": None
            })
            
    return results
