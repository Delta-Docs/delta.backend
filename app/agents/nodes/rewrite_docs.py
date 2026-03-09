from pathlib import Path
from typing import Any

from app.agents.llm import get_llm
from app.agents.state import DriftAnalysisState
from app.agents.prompts import (
    get_rewrite_system_prompt,
    build_doc_gen_rewrite_prompt,
)


# Node rewrites each target doc file using the LLM
def rewrite_docs(state: DriftAnalysisState) -> dict[str, Any]:
    target_files: list[dict] = state["target_files"]
    repo_path: str = state["repo_path"]
    style_preference: str = state.get("style_preference", "professional")

    if not target_files:
        return {"rewrite_results": []}

    # Initialise Gemini for rewriting
    llm = get_llm(temperature=0.2)

    rewrite_results: list[dict] = []

    # Group targets by doc_path so each file is rewritten once with all its changes
    grouped: dict[str, list[str]] = {}
    for target in target_files:
        doc_path = target["doc_path"]
        description = target.get("description", "")
        grouped.setdefault(doc_path, []).append(description)

    for doc_path, change_descriptions in grouped.items():
        # Read the current file content
        full_path = Path(repo_path) / doc_path

        # Security check: ensure the path is within the repo
        try:
            resolved = full_path.resolve()
            repo_resolved = Path(repo_path).resolve()
            if not str(resolved).startswith(str(repo_resolved)):
                print(f"Path traversal blocked for {doc_path}")
                continue
        except Exception:
            print(f"Could not resolve path {doc_path}")
            continue

        if not full_path.exists():
            print(f"Doc file not found: {full_path}")
            continue

        try:
            current_content = full_path.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"Error reading {full_path}: {exc}")
            continue

        user_prompt = build_doc_gen_rewrite_prompt(
            doc_path=doc_path,
            current_content=current_content,
            change_descriptions=change_descriptions,
        )

        try:
            result = llm.invoke(
                [
                    {"role": "system", "content": get_rewrite_system_prompt(style_preference)},
                    {"role": "user", "content": user_prompt},
                ]
            )
            new_content: str = str(result.content) if hasattr(result, "content") else str(result)

            # Strip markdown code fences if the LLM wrapped the output
            if new_content.startswith("```markdown"):
                new_content = new_content[len("```markdown") :].strip()
            if new_content.startswith("```"):
                new_content = new_content[3:].strip()
            if new_content.endswith("```"):
                new_content = new_content[:-3].strip()

            rewrite_results.append(
                {
                    "doc_path": doc_path,
                    "new_content": new_content,
                }
            )
        except Exception as exc:
            print(f"LLM error rewriting {doc_path}: {exc}")
            continue

    return {"rewrite_results": rewrite_results}
