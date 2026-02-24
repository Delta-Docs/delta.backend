import operator
from typing import Annotated, Any, TypedDict


class DriftAnalysisState(TypedDict):
    drift_event_id: str
    base_sha: str
    head_sha: str
    session: Any
    repo_path: str
    docs_root_path: str
    change_elements: list[dict]
    analysis_payloads: list[dict]
    findings: Annotated[list[dict], operator.add]
