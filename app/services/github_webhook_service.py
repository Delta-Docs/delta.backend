from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.user import User
from app.models.installation import Installation
from app.models.repository import Repository
from app.models.drift import DriftEvent

from app.services.github_api import create_github_check_run, get_installation_access_token
from app.services.git_service import clone_repository, remove_cloned_repository, pull_branches
from app.core.queue import task_queue
from app.services.drift_analysis import run_drift_analysis

# Upsert repositorites (Insert if they don't exist or update existing repos)
async def _insert_repositories(db: Session, installation_id: int, repos_list: list, account_avatar_url: str = None):
    if not repos_list:
        return

    values_list = []
    for repo in repos_list:
        values_list.append({
            "installation_id": installation_id,
            "repo_name": repo["full_name"],
            "is_active": True,
            "avatar_url": account_avatar_url 
        })

    # Insert or update on conflict
    stmt = insert(Repository).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=['installation_id', 'repo_name'],
        set_={"is_active": True, "avatar_url": stmt.excluded.avatar_url}
    )
    db.execute(stmt)
    
    try:
        access_token = await get_installation_access_token(installation_id)
        for repo in repos_list:
            repo_full_name = repo["full_name"]
            await clone_repository(repo_full_name, access_token)
    except Exception as e:
        print(f"Error cloning repositories for installation {installation_id}: {str(e)}")

# Handle when GH app is first installed on a GitHub account
async def _handle_installation_created(db: Session, payload: dict):
    installation = payload["installation"]
    account = installation["account"]
    sender = payload["sender"]
    
    # Link installation to an existing user
    user = db.query(User).filter(User.github_user_id == sender["id"]).first()
    user_id = user.id if user else None

    values = {
        "installation_id": installation["id"],
        "account_name": account["login"],
        "account_type": account["type"]
    }
    if user_id:
        values["user_id"] = user_id
        
    # Upsert the installation
    stmt = insert(Installation).values(**values)
    
    update_dict = {
        "account_name": stmt.excluded.account_name,
        "account_type": stmt.excluded.account_type
    }
    if user_id:
        update_dict["user_id"] = stmt.excluded.user_id
        
    stmt = stmt.on_conflict_do_update(
        index_elements=['installation_id'],
        set_=update_dict
    )
    db.execute(stmt)

    if payload.get("repositories"):
        await _insert_repositories(db, installation["id"], payload["repositories"], account.get("avatar_url"))

# Handle when GH app is uninstalled
def _handle_installation_deleted(db: Session, payload: dict):
    inst_id = payload["installation"]["id"]
    
    repos = db.query(Repository).filter(Repository.installation_id == inst_id).all()
    
    for repo in repos:
        try:
            remove_cloned_repository(repo.repo_name)
        except Exception as e:
            print(f"Error removing repository {repo.repo_name}: {str(e)}")
    
    db.query(Installation).filter(Installation.installation_id == inst_id).delete(synchronize_session=False)

# Handle when installation is suspended or unsuspended
def _handle_installation_suspend(db: Session, payload: dict, suspended: bool):
    inst_id = payload["installation"]["id"]
    # Mark all repos as suspended/unsuspended
    db.query(Repository).filter(Repository.installation_id == inst_id).update({"is_suspended": suspended})

# Handle when repos are added to an existing installation
async def _handle_repos_added(db: Session, payload: dict):
    inst_id = payload["installation"]["id"]
    repos = payload["repositories_added"]
    account_avatar_url = payload["installation"]["account"].get("avatar_url")
    await _insert_repositories(db, inst_id, repos, account_avatar_url)

# Handle when repos are removed from an existing installation
def _handle_repos_removed(db: Session, payload: dict):
    inst_id = payload["installation"]["id"]
    repos = payload["repositories_removed"]
    
    repo_full_names = [repo["full_name"] for repo in repos]
    
    if repo_full_names:
        for repo_name in repo_full_names:
            try:
                remove_cloned_repository(repo_name)
            except Exception as e:
                print(f"Error removing repository {repo_name}: {str(e)}")
        
        db.query(Repository).filter(
            Repository.installation_id == inst_id, 
            Repository.repo_name.in_(repo_full_names)
        ).delete(synchronize_session=False)

# Handle PR webhook event (Opened or Updated)
async def _handle_pr_event(db: Session, payload: dict):
    action = payload.get("action")
    if action not in ["opened", "synchronize"]:
        return

    installation_id = payload.get("installation", {}).get("id")
    repo_full_name = payload.get("repository", {}).get("full_name")

    if not installation_id or not repo_full_name:
        print(f"Warning: Missing installation_id or repo_full_name in payload. Action: {action}")
        return

    repo = db.query(Repository).filter(
        Repository.installation_id == installation_id,
        Repository.repo_name == repo_full_name
    ).first()

    if not repo:
        print(f"Warning: Repository not found: {repo_full_name} (inst: {installation_id})")
        return

    base_branch = payload["pull_request"]["base"]["ref"]
    head_branch = payload["pull_request"]["head"]["ref"]
    
    if base_branch == repo.target_branch:
        try:
            access_token = await get_installation_access_token(installation_id)
            branches_to_pull = [base_branch]
            
            if not payload["pull_request"]["head"].get("repo", {}).get("fork"):
                branches_to_pull.append(head_branch)
            
            await pull_branches(repo_full_name, access_token, branches_to_pull)
        except Exception as e:
            print(f"Error pulling branches for {repo_full_name}: {str(e)}")

    # Create a drift event for the PR
    new_event = DriftEvent(
        repo_id=repo.id,
        pr_number=payload["number"],
        base_branch=base_branch,
        head_branch=head_branch,
        base_sha=payload["pull_request"]["base"]["sha"],
        head_sha=payload["pull_request"]["head"]["sha"],
        processing_phase="queued",
        drift_result="pending",
        agent_logs={}
    )
    db.add(new_event)
    db.flush()
    db.refresh(new_event)
    
    # Create a GH check run to show status in PR
    await create_github_check_run(db, new_event.id, repo_full_name, new_event.head_sha, installation_id)

    # Enqueue the drift analysis as a background task
    task_queue.enqueue(run_drift_analysis, str(new_event.id))

# Main Router to handle different types of GH webhook events
async def handle_github_event(db: Session, event_type: str, payload: dict):
    # Installation lifecycle events
    if event_type == "installation":
        action = payload.get("action")
        if action == "created":
            await _handle_installation_created(db, payload)
        elif action == "deleted":
            _handle_installation_deleted(db, payload)
        elif action == "suspend":
            _handle_installation_suspend(db, payload, suspended=True)
        elif action == "unsuspend":
            _handle_installation_suspend(db, payload, suspended=False)
    
    # Repo selection changes
    elif event_type == "installation_repositories":
        action = payload.get("action")
        if action == "added":
            await _handle_repos_added(db, payload)
        elif action == "removed":
            _handle_repos_removed(db, payload)

    # PR Events
    elif event_type == "pull_request":
        await _handle_pr_event(db, payload)
    
    db.commit()
