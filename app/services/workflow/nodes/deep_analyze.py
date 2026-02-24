import subprocess
from typing import Literal

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.services.workflow.state import DriftAnalysisState


class LLMDriftFinding(BaseModel):
    drift_detected: bool = Field(
        description="True if the documentation needs updating based on the code change."
    )
    drift_type: Literal["outdated_docs", "missing_docs", "ambiguous_docs", ""] = Field(
        default="",
        description="Type of drift detected. Empty string if no drift."
    )
    drift_score: float = Field(
        ge=0.0, le=1.0,
        description="Severity of the drift from 0.0 (none) to 1.0 (critical)."
    )
    explanation: str = Field(
        description="Clear, developer-friendly explanation of what changed and why docs are out of sync."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="How confident the LLM is in this assessment."
    )


_SYSTEM_PROMPT = (
    "You are a strict technical writer verifying API documentation. "
    "Your job is to read a code diff and check if the provided documentation "
    "accurately reflects the NEW state of the code. Pay strict attention to "
    "changed HTTP methods, route paths, required parameters, return types, "
    "and any behavioral changes. "
    "If the documentation is accurate and complete, set drift_detected to false."
)


def _get_git_diff(repo_path: str, base_sha: str, head_sha: str, file_path: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "diff", base_sha, head_sha, "--", file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return None


def deep_analyze(state: DriftAnalysisState) -> dict:
    print(f"\n{'─'*60}")
    print("[ANALYZE] Starting deep_analyze node")
    print(f"{'─'*60}")

    analysis_payloads: list[dict] = state["analysis_payloads"]
    repo_path: str = state["repo_path"]
    base_sha: str = state["base_sha"]
    head_sha: str = state["head_sha"]

    if not analysis_payloads:
        print("[ANALYZE] No analysis payloads — skipping LLM calls")
        return {"findings": []}

    print(f"[ANALYZE] {len(analysis_payloads)} payload(s) to analyze")
    print(f"[ANALYZE] base_sha={base_sha[:10]}... head_sha={head_sha[:10]}...")

    llm = ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0,
    )
    structured_llm = llm.with_structured_output(LLMDriftFinding)

    new_findings: list[dict] = []

    for i, payload in enumerate(analysis_payloads, 1):
        code_path: str = payload["code_path"]
        change_type: str = payload["change_type"]
        elements: list[str] = payload.get("elements", [])
        old_elements: list[str] = payload.get("old_elements", [])
        matched_doc_snippets: str = payload.get("matched_doc_snippets", "")

        print(f"\n[ANALYZE] [{i}/{len(analysis_payloads)}] {code_path} ({change_type})")

        diff = _get_git_diff(repo_path, base_sha, head_sha, code_path)

        if diff is None:
            print("[ANALYZE]   ↳ Could not retrieve git diff — skipping")
            continue

        if not diff.strip():
            print("[ANALYZE]   ↳ Empty diff — skipping")
            continue

        user_prompt = (
            f"## Code Change\n"
            f"**File:** `{code_path}` ({change_type})\n"
            f"**New elements:** {elements}\n"
            f"**Old elements:** {old_elements}\n\n"
            f"### Git Diff\n```diff\n{diff}\n```\n\n"
            f"### Current Documentation Snippets\n{matched_doc_snippets}\n\n"
            f"Analyze whether the documentation above accurately reflects the "
            f"NEW state of the code after this diff. Focus on any discrepancies."
        )

        try:
            result: LLMDriftFinding = structured_llm.invoke(
                [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            )
        except Exception as exc:
            print(f"[ANALYZE]   ↳ LLM error: {exc}")
            continue

        print(f"[ANALYZE]   ↳ drift_detected={result.drift_detected}, "
              f"type={result.drift_type}, score={result.drift_score:.2f}, "
              f"confidence={result.confidence:.2f}")

        if result.drift_detected:
            new_findings.append(
                {
                    "code_path": code_path,
                    "change_type": change_type,
                    "drift_type": result.drift_type,
                    "drift_score": result.drift_score,
                    "explanation": result.explanation,
                    "confidence": result.confidence,
                    "matched_doc_paths": payload.get("matched_doc_paths", []),
                }
            )

    print(f"\n[ANALYZE] Done — {len(new_findings)} finding(s) from LLM analysis")

    return {"findings": new_findings}
