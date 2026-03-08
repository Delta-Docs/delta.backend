import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


# Structured output schema for the LLM drift assessment
class LLMDriftFinding(BaseModel):
    drift_detected: bool = Field(
        description="True if the documentation needs updating based on the code change."
    )
    drift_type: Literal["outdated_docs", "missing_docs", "ambiguous_docs", ""] = Field(
        default="", description="Type of drift detected. Empty string if no drift."
    )
    drift_score: float = Field(
        ge=0.0, le=1.0, description="Severity of the drift from 0.0 (none) to 1.0 (critical)."
    )
    explanation: str = Field(
        description="Clear, developer-friendly explanation of what changed and why docs are out of sync."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="How confident the LLM is in this assessment."
    )


# Schema for drift event list response (minimal data for table view)
class DriftEventListResponse(BaseModel):
    id: uuid.UUID
    pr_number: int
    base_branch: str
    head_branch: str
    processing_phase: str
    drift_result: str
    overall_drift_score: Optional[float]
    created_at: datetime
    docs_pr_number: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# Schema for full drift event response (all fields)
class DriftEventResponse(BaseModel):
    id: uuid.UUID
    pr_number: int
    base_branch: str
    head_branch: str
    processing_phase: str
    drift_result: str
    overall_drift_score: Optional[float]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    docs_pr_number: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# Schema for drift finding response
class DriftFindingResponse(BaseModel):
    id: uuid.UUID
    code_path: str
    doc_file_path: Optional[str]
    change_type: Optional[str]
    drift_type: Optional[str]
    drift_score: Optional[float]
    explanation: Optional[str]
    confidence: Optional[float]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for code change response
class CodeChangeResponse(BaseModel):
    id: uuid.UUID
    file_path: str
    change_type: Optional[str]
    is_code: Optional[bool]
    is_ignored: bool

    model_config = ConfigDict(from_attributes=True)


# Schema for drift event detail with nested findings and code changes
class DriftEventDetailResponse(DriftEventResponse):
    findings: list[DriftFindingResponse] = []
    code_changes: list[CodeChangeResponse] = []

    model_config = ConfigDict(from_attributes=True)
