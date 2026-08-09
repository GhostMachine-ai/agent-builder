"""
Run one of Impeccable's specialist design subagents as a nested Strands agent.

Impeccable (https://github.com/pbakaus/impeccable, Apache-2.0) defines four
specialist subagents (finish reviewer, asset producer, documenter, manual edit
applier). This tool loads a vendored agent definition and runs it as a nested
Strands agent with the tools its definition declares.
"""

import sys
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

from strands import Agent, tool

# Impeccable agent definitions declare Claude Code tool names; map them to Strands tools.
# Glob/Grep have no direct Strands equivalent — shell covers both.
_TOOL_NAME_MAP = {
    "Read": ("file_read",),
    "Write": ("file_write",),
    "Edit": ("editor",),
    "Bash": ("shell",),
    "Glob": ("shell",),
    "Grep": ("shell",),
}


def _agents_root() -> Path:
    """Locate the vendored Impeccable agent definitions inside the installed package."""
    import strands_agents_builder

    return Path(strands_agents_builder.__file__).parent / "vendor" / "impeccable" / "agents"


def _catalog(root: Path) -> Dict[str, Path]:
    """Map agent names to definition files; the 'impeccable-' prefix is optional."""
    catalog: Dict[str, Path] = {}
    for entry in sorted(root.glob("*.md")):
        catalog[entry.stem] = entry
        if entry.stem.startswith("impeccable-"):
            catalog[entry.stem.removeprefix("impeccable-")] = entry
    return catalog


def _parse_definition(text: str) -> Tuple[Dict[str, str], str]:
    """Split an agent definition into (frontmatter fields, body).

    Frontmatter is the block between the leading '---' lines. Only simple
    single-line "key: value" fields are extracted — enough for description/tools.
    """
    fields: Dict[str, str] = {}
    if not text.startswith("---"):
        return fields, text
    lines = text.split("\n")
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return fields, text
    for line in lines[1:end]:
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields, "\n".join(lines[end + 1 :]).strip()


def _declared_tools(fields: Dict[str, str]) -> List[str]:
    """Translate the definition's declared tool names into available Strands tool names."""
    declared = [name.strip() for name in fields.get("tools", "").split(",") if name.strip()]
    strands_names: List[str] = []
    for name in declared:
        for mapped in _TOOL_NAME_MAP.get(name, ()):
            if mapped not in strands_names:
                strands_names.append(mapped)
    return strands_names


@tool
def design_agent(agent: str, task: str) -> Dict[str, Any]:
    """
    Delegate design work to one of Impeccable's specialist subagents (Apache-2.0).

    Runs the named agent as a nested Strands agent with the tools its definition
    declares. Available agents:

    - finish-reviewer: reviews a finished UI build against its design direction and
      quality bar, returning an ordered list of material fixes (read-only; you apply
      the fixes).
    - asset-producer: produces the visual assets (textures, illustrations, images) a
      design calls for.
    - documenter: writes/updates DESIGN.md capturing the current visual design system.
    - manual-edit-applier: applies a reviewer's list of edits to UI files precisely.

    Each agent expects specific inputs (file paths, screenshots, design context) —
    read its expectations first via design_guide(action="get",
    name="degraded/<agent>") or include everything relevant in the task text:
    artifact paths, PRODUCT.md/DESIGN.md paths, and any review findings.

    Args:
        agent: Agent name (e.g. "finish-reviewer" or "impeccable-finish-reviewer").
        task: Full task briefing for the agent, including the file paths and context
            it needs. The agent runs in the current working directory.

    Returns:
        A dictionary with "status" and "content" carrying the agent's findings/output.
    """
    if not task or not task.strip():
        return {"status": "error", "content": [{"text": "❌ Provide a task briefing for the agent."}]}

    root = _agents_root()
    if not root.is_dir():
        return {
            "status": "error",
            "content": [{"text": f"❌ Vendored agent definitions not found at {root}. Reinstall the package."}],
        }

    catalog = _catalog(root)
    definition_path = catalog.get(agent)
    if definition_path is None:
        known = ", ".join(sorted(name for name in catalog if not name.startswith("impeccable-")))
        return {"status": "error", "content": [{"text": f"❌ Unknown agent '{agent}'. Available: {known}"}]}

    try:
        fields, body = _parse_definition(definition_path.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        return {"status": "error", "content": [{"text": f"❌ Could not read agent definition: {e}"}]}

    from strands_agents_builder.tools import get_tools

    available = get_tools()
    selected = [available[name] for name in _declared_tools(fields) if name in available]

    # Capture stdout so the nested agent's streaming output is returned, not printed
    original_stdout = sys.stdout
    captured = StringIO()
    sys.stdout = captured
    try:
        nested = Agent(tools=selected, messages=[], system_prompt=body)
        response = nested(task)
        result_str = str(response) if response else ""
    except Exception as e:
        return {"status": "error", "content": [{"text": f"❌ Design agent '{agent}' failed: {e}"}]}
    finally:
        sys.stdout = original_stdout

    output = captured.getvalue()
    full_output = (output + "\n" + result_str).strip() if output and result_str else (output or result_str).strip()
    return {"status": "success", "content": [{"text": f"Design agent '{agent}' result:\n\n{full_output}"}]}
