import time
import jwt
import httpx
from pathlib import Path
from app.core.config import settings
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.drift import DriftEvent

async def get_installation_access_token(installation_id: int) -> str:
    try:
        key_path = Path(settings.GITHUB_PRIVATE_KEY_PATH)
        with open(key_path, 'rb') as f:
            private_key = f.read()
    except FileNotFoundError:
        raise Exception(f"Private Key not found at {settings.GITHUB_PRIVATE_KEY_PATH}")

    # JWT Payload
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": settings.GITHUB_APP_ID
    }
    
    encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {encoded_jwt}",
                "Accept": "application/vnd.github+json"
            }
        )
        
        if token_res.status_code != 201:
            raise Exception(f"Token Error: {token_res.text}")
            
        return token_res.json()["token"]

async def get_repo_details(installation_id: int, owner: str, repo_name: str):
    access_token = await get_installation_access_token(installation_id)

    async with httpx.AsyncClient() as client:
        repo_res = await client.get(
            f"https://api.github.com/repos/{owner}/{repo_name}",
            headers={
                "Authorization": f"Bearer {access_token}", 
                "Accept": "application/vnd.github+json"
            }
        )

        if repo_res.status_code != 200:
            raise Exception(f"GitHub API Error: {repo_res.text}")

        data = repo_res.json()

        return {
            "name": data.get("name"),
            "description": data.get("description"),
            "language": data.get("language"),
            "stargazers_count": data.get("stargazers_count"),
            "forks_count": data.get("forks_count")
        }

async def create_github_check_run(db: Session, drift_event_id, repo_full_name: str, head_sha: str, installation_id: int):
    try:
        access_token = await get_installation_access_token(installation_id)
        
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"https://api.github.com/repos/{repo_full_name}/check-runs",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json"
                },
                json={
                    "name": "Delta Docs Run",
                    "head_sha": head_sha,
                    "status": "queued",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "output": {
                        "title": "PR Queued",
                        "summary": "Waiting for worker..."
                    }
                }
            )
            
            if res.status_code != 201:
                print(f"Error creating check run: {res.text}")
                return None
                
            data = res.json()
            check_run_id = data.get("id")
            
            db.query(DriftEvent).filter(DriftEvent.id == drift_event_id).update({"check_run_id": check_run_id})
            db.commit()
            
            return check_run_id

    except Exception as e:
        print(f"Exception in create_github_check_run: {str(e)}")
        return None
