import subprocess
from pathlib import Path
from typing import Optional
from app.core.config import settings


async def clone_repository(
    repo_full_name: str,
    access_token: str,
    target_branch: str = "main"
) -> Optional[str]:
    try:
        owner, repo_name = repo_full_name.split("/")
        
        repos_base = Path(settings.REPOS_BASE_PATH)
        owner_dir = repos_base / owner
        repo_path = owner_dir / repo_name
        
        owner_dir.mkdir(parents=True, exist_ok=True)
        
        clone_url = f"https://x-access-token:{access_token}@github.com/{repo_full_name}.git"
        
        result = subprocess.run(
            ["git", "clone", "--branch", target_branch, clone_url, str(repo_path)],
            capture_output=True,
            text=True,
            timeout=1000
        )
        
        if result.returncode == 0:
            return str(repo_path)
        else:
            print(f"Failed to clone repository {repo_full_name}: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print(f"Timeout while cloning repository: {repo_full_name}")
        return None
    except Exception as e:
        print(f"Error cloning repository {repo_full_name}: {str(e)}")
        return None


def remove_cloned_repository(repo_full_name: str) -> bool:
    try:
        owner, repo_name = repo_full_name.split("/")
        
        repos_base = Path(settings.REPOS_BASE_PATH)
        repo_path = repos_base / owner / repo_name
        
        if repo_path.exists():
            import shutil
            shutil.rmtree(repo_path)
            return True
        else:
            return False
            
    except Exception as e:
        print(f"Error removing cloned repository {repo_full_name}: {str(e)}")
        return False


async def pull_branches(
    repo_full_name: str,
    access_token: str,
    branches: list[str]
) -> bool:
    try:
        owner, repo_name = repo_full_name.split("/")
        
        repos_base = Path(settings.REPOS_BASE_PATH)
        repo_path = repos_base / owner / repo_name
        
        if not repo_path.exists():
            return False
        
        remote_url = f"https://x-access-token:{access_token}@github.com/{repo_full_name}.git"
        
        result = subprocess.run(
            ["git", "-C", str(repo_path), "remote", "set-url", "origin", remote_url],
            capture_output=True,
            text=True,
            timeout=50
        )
        
        if result.returncode != 0:
            print(f"Failed to set remote URL for {repo_full_name}: {result.stderr}")
            return False
        
        result = subprocess.run(
            ["git", "-C", str(repo_path), "fetch", "origin"],
            capture_output=True,
            text=True,
            timeout=500
        )
        
        if result.returncode != 0:
            print(f"Failed to fetch branches for {repo_full_name}: {result.stderr}")
            return False
        
        for branch in branches:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "checkout", branch],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                result = subprocess.run(
                    ["git", "-C", str(repo_path), "pull", "origin", branch],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            
            if result.returncode != 0:
                print(f"Failed to pull branch {branch} for {repo_full_name}: {result.stderr}")
                continue
        return True
        
    except subprocess.TimeoutExpired:
        print(f"Timeout while pulling branches for repository: {repo_full_name}")
        return False
    except Exception as e:
        print(f"Error pulling branches for repository {repo_full_name}: {str(e)}")
        return False
