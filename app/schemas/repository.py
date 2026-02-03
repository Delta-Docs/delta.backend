from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class RepositoryBase(BaseModel):
    repo_name: str


class RepositorySettings(BaseModel):
    docs_root_path: Optional[str] = None
    target_branch: Optional[str] = None
    drift_sensitivity: Optional[float] = None
    style_preference: Optional[str] = None
    file_ignore_patterns: Optional[list[str]] = None


class RepositoryActivation(BaseModel):
    is_active: bool


class RepositoryResponse(BaseModel):
    id: UUID
    installation_id: int
    repo_name: str
    is_active: bool
    is_suspended: bool
    avatar_url: Optional[str]
    docs_root_path: Optional[str]
    target_branch: Optional[str]
    drift_sensitivity: Optional[float]
    style_preference: Optional[str]
    file_ignore_patterns: Optional[list[str]]
    last_synced_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True
