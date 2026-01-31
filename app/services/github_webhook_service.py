from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.user import User
from app.models.installation import Installation
from app.models.repository import Repository

def _insert_repositories(db: Session, installation_id: int, repos_list: list, account_avatar_url: str = None):
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

    stmt = insert(Repository).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=['installation_id', 'repo_name'],
        set_={"is_active": True, "avatar_url": stmt.excluded.avatar_url}
    )
    db.execute(stmt)

def _handle_installation_created(db: Session, payload: dict):
    installation = payload["installation"]
    account = installation["account"]
    sender = payload["sender"]
    
    user = db.query(User).filter(User.github_user_id == sender["id"]).first()
    user_id = user.id if user else None

    values = {
        "installation_id": installation["id"],
        "account_name": account["login"],
        "account_type": account["type"]
    }
    if user_id:
        values["user_id"] = user_id
        
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
        _insert_repositories(db, installation["id"], payload["repositories"], account.get("avatar_url"))

def _handle_installation_deleted(db: Session, payload: dict):
    inst_id = payload["installation"]["id"]
    db.query(Installation).filter(Installation.installation_id == inst_id).delete(synchronize_session=False)

def _handle_installation_suspend(db: Session, payload: dict, suspended: bool):
    inst_id = payload["installation"]["id"]
    db.query(Repository).filter(Repository.installation_id == inst_id).update({"is_suspended": suspended})

def _handle_repos_added(db: Session, payload: dict):
    inst_id = payload["installation"]["id"]
    repos = payload["repositories_added"]
    account_avatar_url = payload["installation"]["account"].get("avatar_url")
    _insert_repositories(db, inst_id, repos, account_avatar_url)

def _handle_repos_removed(db: Session, payload: dict):
    inst_id = payload["installation"]["id"]
    repos = payload["repositories_removed"]
    
    repo_full_names = [repo["full_name"] for repo in repos]
    
    if repo_full_names:
        db.query(Repository).filter(
            Repository.installation_id == inst_id, 
            Repository.repo_name.in_(repo_full_names)
        ).delete(synchronize_session=False)

def handle_github_event(db: Session, event_type: str, payload: dict):
    if event_type == "installation":
        action = payload.get("action")
        if action == "created":
            _handle_installation_created(db, payload)
        elif action == "deleted":
            _handle_installation_deleted(db, payload)
        elif action == "suspend":
            _handle_installation_suspend(db, payload, suspended=True)
        elif action == "unsuspend":
            _handle_installation_suspend(db, payload, suspended=False)
    
    elif event_type == "installation_repositories":
        action = payload.get("action")
        if action == "added":
            _handle_repos_added(db, payload)
        elif action == "removed":
            _handle_repos_removed(db, payload)
    
    db.commit()
