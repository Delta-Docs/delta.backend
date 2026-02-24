import ast
import os
import subprocess
from typing import Any

from app.db.base import CodeChange
from app.services.workflow.state import DriftAnalysisState


def _extract_routes_from_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    routes: list[str] = []

    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue

        for arg in decorator.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("/"):
                routes.append(arg.value)

        for kw in decorator.keywords:
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value, str) and kw.value.startswith("/"):
                routes.append(kw.value)

    return routes


def _extract_elements_from_source(source: str, filename: str = "<string>") -> list[str]:
    elements: list[str] = []

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return elements

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            elements.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            elements.append(node.name)
            routes = _extract_routes_from_decorators(node)
            elements.extend(routes)

    return elements


def _get_git_file_content(repo_path: str, commit_sha: str, file_path: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "show", f"{commit_sha}:{file_path}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return None

def scout_changes(state: DriftAnalysisState) -> dict[str, Any]:
    session = state["session"]
    drift_event_id = state["drift_event_id"]
    repo_path = state["repo_path"]
    base_sha = state["base_sha"]

    code_changes = (
        session.query(CodeChange)
        .filter(
            CodeChange.drift_event_id == drift_event_id,
            CodeChange.is_code.is_(True),
        )
        .all()
    )

    py_changes = [cc for cc in code_changes if cc.file_path.endswith(".py")]

    change_elements: list[dict] = []

    for i, change in enumerate(py_changes, 1):
        elements: list[str] = []
        old_elements: list[str] = []

        if change.change_type == "deleted":
            old_source = _get_git_file_content(repo_path, base_sha, change.file_path)
            if old_source:
                old_elements = _extract_elements_from_source(old_source, change.file_path)

            change_elements.append(
                {
                    "file_path": change.file_path,
                    "change_type": change.change_type,
                    "elements": elements,
                    "old_elements": old_elements,
                }
            )
            continue

        abs_path = os.path.join(repo_path, change.file_path)

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                source = f.read()
        except (FileNotFoundError, OSError) as exc:
            print(f"File read error: {exc}")
            change_elements.append(
                {
                    "file_path": change.file_path,
                    "change_type": change.change_type,
                    "elements": elements,
                    "old_elements": old_elements,
                }
            )
            continue

        elements = _extract_elements_from_source(source, change.file_path)

        if change.change_type == "modified":
            old_source = _get_git_file_content(repo_path, base_sha, change.file_path)
            if old_source:
                old_elements = _extract_elements_from_source(old_source, change.file_path)


        change_elements.append(
            {
                "file_path": change.file_path,
                "change_type": change.change_type,
                "elements": elements,
                "old_elements": old_elements,
            }
        )

    return {"change_elements": change_elements}
