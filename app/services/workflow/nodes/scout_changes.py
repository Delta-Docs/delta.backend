import ast
import os
import subprocess

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


def scout_changes(state: DriftAnalysisState) -> dict:
    print(f"\n{'─'*60}")
    print("[SCOUT] Starting scout_changes node")
    print(f"{'─'*60}")

    session = state["session"]
    drift_event_id = state["drift_event_id"]
    repo_path = state["repo_path"]
    base_sha = state["base_sha"]

    print(f"[SCOUT] base_sha = {base_sha[:10]}...")

    code_changes = (
        session.query(CodeChange)
        .filter(
            CodeChange.drift_event_id == drift_event_id,
            CodeChange.is_code.is_(True),
        )
        .all()
    )
    print(f"[SCOUT] Found {len(code_changes)} code change(s) in DB")

    py_changes = [cc for cc in code_changes if cc.file_path.endswith(".py")]
    print(f"[SCOUT] Filtered to {len(py_changes)} Python file(s)")

    change_elements: list[dict] = []

    for i, change in enumerate(py_changes, 1):
        elements: list[str] = []
        old_elements: list[str] = []
        print(f"\n[SCOUT] [{i}/{len(py_changes)}] Processing: {change.file_path} ({change.change_type})")

        if change.change_type == "deleted":
            old_source = _get_git_file_content(repo_path, base_sha, change.file_path)
            if old_source:
                old_elements = _extract_elements_from_source(old_source, change.file_path)
            print(f"[SCOUT]   ↳ Deleted — old_elements: {old_elements}")
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
            print(f"[SCOUT]   ↳ File read error: {exc}")
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
            print(f"[SCOUT]   ↳ elements:     {elements}")
            print(f"[SCOUT]   ↳ old_elements: {old_elements}")
        else:
            print(f"[SCOUT]   ↳ elements: {elements} (added, no old version)")

        change_elements.append(
            {
                "file_path": change.file_path,
                "change_type": change.change_type,
                "elements": elements,
                "old_elements": old_elements,
            }
        )

    total_elements = sum(len(ce["elements"]) + len(ce["old_elements"]) for ce in change_elements)
    print(f"\n[SCOUT] Done — {len(change_elements)} file(s) processed, {total_elements} element(s) extracted total")

    return {"change_elements": change_elements}
