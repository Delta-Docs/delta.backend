# System prompt that instructs the LLM to act as a strict documentation reviewer
DEEP_ANALYZE_SYSTEM_PROMPT = (
    "You are a strict technical writer verifying API documentation. "
    "Your job is to read a code diff and check if the provided documentation "
    "accurately reflects the NEW state of the code. Pay strict attention to "
    "changed HTTP methods, route paths, required parameters, return types, "
    "and any behavioral changes. "
    "If the documentation is accurate and complete, set drift_detected to false."
)


def build_deep_analyze_user_prompt(
    code_path: str,
    change_type: str,
    elements: list[str],
    old_elements: list[str],
    diff: str,
    matched_doc_snippets: str,
) -> str:
    return (
        f"## Code Change\n"
        f"**File:** `{code_path}` ({change_type})\n"
        f"**New elements:** {elements}\n"
        f"**Old elements:** {old_elements}\n\n"
        f"### Git Diff\n```diff\n{diff}\n```\n\n"
        f"### Current Documentation Snippets\n{matched_doc_snippets}\n\n"
        f"Analyze whether the documentation above accurately reflects the "
        f"NEW state of the code after this diff. Focus on any discrepancies."
    )


# System prompt that instructs the LLM to plan documentation updates
DOC_GEN_PLAN_SYSTEM_PROMPT = (
    "You are a documentation update planner. Given a list of drift findings "
    "(each describing a discrepancy between code and documentation), produce a "
    "structured plan that maps each finding to the specific markdown file and "
    "section that needs to be updated. For each entry output: doc_path (the "
    "relative path to the .md file), section (heading or area to update), "
    "action (one of 'update', 'add', 'remove'), and a brief description of "
    "the required change."
)


# System prompt that instructs the LLM to rewrite a markdown document
DOC_GEN_REWRITE_SYSTEM_PROMPT = (
    "You are an expert technical writer. You will receive the current contents "
    "of a markdown documentation file along with a description of code changes "
    "that have made parts of the document outdated. Rewrite the document so "
    "that it accurately reflects the new state of the code. Preserve the "
    "overall structure and tone. Only modify the sections that are affected by "
    "the code changes. Return the complete updated file content as a single "
    "markdown string."
)


def build_doc_gen_rewrite_prompt(
    doc_path: str,
    current_content: str,
    change_descriptions: list[str],
) -> str:
    changes_block = "\n".join(f"- {desc}" for desc in change_descriptions)
    return (
        f"## Document to Update\n"
        f"**File:** `{doc_path}`\n\n"
        f"### Current Content\n```markdown\n{current_content}\n```\n\n"
        f"### Required Changes\n{changes_block}\n\n"
        f"Rewrite the document above to accurately reflect these code changes. "
        f"Return the full updated markdown content."
    )
