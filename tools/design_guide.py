"""
Design guidance tool backed by a vendored subset of Impeccable.

Impeccable (https://github.com/pbakaus/impeccable, Apache-2.0) ships ~35 design
playbooks plus a quality floor. This tool exposes them lazily: list the catalog,
fetch exactly one playbook at a time, and load the project's PRODUCT.md/DESIGN.md
design context.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from strands import tool

# Maximum size read from a PRODUCT.md/DESIGN.md file
_MAX_CONTEXT_FILE_BYTES = 100_000

# Maximum directory levels to walk up when resolving design context
_MAX_WALK_UP_LEVELS = 20

_PROTOCOL_NOTE = (
    "Protocol: read 'craft-floor' immediately before any UI edit and honor its quality floor "
    "and refuse-list; load exactly ONE task-relevant playbook per task; after UI edits, verify "
    "with the design_check tool."
)


def _guidance_root() -> Path:
    """Locate the vendored Impeccable guidance directory inside the installed package."""
    import strands_agents_builder

    return Path(strands_agents_builder.__file__).parent / "vendor" / "impeccable" / "guidance"


def _catalog(root: Path) -> Dict[str, Path]:
    """Map playbook names to files: 'overview' -> SKILL.md, stems of reference/*.md, 'degraded/<stem>'."""
    catalog: Dict[str, Path] = {"overview": root / "SKILL.md"}
    reference = root / "reference"
    for entry in sorted(reference.glob("*.md")):
        catalog[entry.stem] = entry
    for entry in sorted((reference / "degraded").glob("*.md")):
        catalog[f"degraded/{entry.stem}"] = entry
    return catalog


def _command_descriptions(root: Path) -> Dict[str, str]:
    """Load per-command descriptions from Impeccable's command-metadata.json, if present."""
    metadata_path = root / "command-metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    descriptions: Dict[str, str] = {}
    for name, entry in metadata.items():
        if isinstance(entry, dict) and isinstance(entry.get("description"), str):
            descriptions[name] = entry["description"]
    return descriptions


def _list_guides(root: Path) -> Dict[str, Any]:
    descriptions = _command_descriptions(root)
    lines = [_PROTOCOL_NOTE, "", "Available design guides (use action='get' with one name):"]
    for name in _catalog(root):
        description = descriptions.get(name, "")
        if len(description) > 150:
            description = description[:147] + "..."
        lines.append(f"- {name}" + (f": {description}" if description else ""))
    return {"status": "success", "content": [{"text": "\n".join(lines)}]}


def _get_guide(root: Path, name: Optional[str]) -> Dict[str, Any]:
    if not name:
        return {"status": "error", "content": [{"text": "❌ action='get' requires a guide name."}]}
    catalog = _catalog(root)
    guide_path = catalog.get(name)
    if guide_path is None:
        known = ", ".join(catalog)
        return {"status": "error", "content": [{"text": f"❌ Unknown guide '{name}'. Available: {known}"}]}
    try:
        text = guide_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"status": "error", "content": [{"text": f"❌ Could not read guide '{name}': {e}"}]}
    return {"status": "success", "content": [{"text": f"# Design guide: {name}\n\n{text}"}]}


def _find_context_dir(start: Path) -> Optional[Path]:
    """Walk up from start looking for a directory containing PRODUCT.md or DESIGN.md (case-insensitive)."""
    current = start
    for _ in range(_MAX_WALK_UP_LEVELS):
        try:
            names = {entry.name.lower() for entry in current.iterdir() if entry.is_file()}
        except OSError:
            names = set()
        if "product.md" in names or "design.md" in names:
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def _read_context_file(directory: Path, lower_name: str) -> Optional[str]:
    """Read a context file from directory by case-insensitive name, size-capped."""
    try:
        for entry in directory.iterdir():
            if entry.is_file() and entry.name.lower() == lower_name:
                with open(entry, encoding="utf-8", errors="replace") as f:
                    return f.read(_MAX_CONTEXT_FILE_BYTES)
    except OSError:
        pass
    return None


def _load_context(path: Optional[str]) -> Dict[str, Any]:
    start = Path(path or os.getcwd()).resolve()
    if start.is_file():
        start = start.parent
    if not start.is_dir():
        return {"status": "error", "content": [{"text": f"❌ Directory not found: {start}"}]}

    context_dir = _find_context_dir(start)
    if context_dir is None:
        return {
            "status": "success",
            "content": [
                {
                    "text": (
                        "No PRODUCT.md or DESIGN.md found (searched from "
                        f"{start} upward). Proceed with generic design guidance, and consider "
                        "offering to create PRODUCT.md (product strategy, users, brand personality, "
                        "design principles) and DESIGN.md (colors, typography, components) for the project."
                    )
                }
            ],
        }

    sections = [f"Design context resolved from: {context_dir}"]
    for lower_name, label in (("product.md", "PRODUCT.md"), ("design.md", "DESIGN.md")):
        text = _read_context_file(context_dir, lower_name)
        if text is not None:
            sections.append(f"## {label}\n\n{text}")
    return {"status": "success", "content": [{"text": "\n\n".join(sections)}]}


@tool
def design_guide(action: str = "list", name: Optional[str] = None, path: Optional[str] = None) -> Dict[str, Any]:
    """
    Access design guidance for frontend/UI work (powered by Impeccable, Apache-2.0).

    Use this for ANY frontend/UI task (HTML, CSS, JSX/TSX, Vue, Svelte, Astro — components,
    pages, styling). Before your FIRST UI edit of a task, call action="get" with
    name="craft-floor" and honor its quality floor and refuse-list. Call action="context"
    once per project to load its PRODUCT.md/DESIGN.md design context. Load exactly one
    additional task-relevant playbook (see action="list"). After UI edits, verify with the
    design_check tool.

    Args:
        action: "list" to enumerate available guides, "get" to fetch one guide by name,
            "context" to load the project's PRODUCT.md/DESIGN.md design context.
        name: Guide name for action="get" (e.g. "craft-floor", "new-work", "polish",
            "critique", "layout", "overview", "degraded/finish-reviewer").
        path: Starting directory for action="context" (defaults to the current working
            directory); the search walks upward toward the filesystem root.

    Returns:
        A dictionary with "status" and "content" describing the requested guidance.
    """
    root = _guidance_root()
    if not root.is_dir():
        return {
            "status": "error",
            "content": [{"text": f"❌ Vendored design guidance not found at {root}. Reinstall the package."}],
        }

    if action == "list":
        return _list_guides(root)
    if action == "get":
        return _get_guide(root, name)
    if action == "context":
        return _load_context(path)
    return {
        "status": "error",
        "content": [{"text": f"❌ Unknown action '{action}'. Use 'list', 'get', or 'context'."}],
    }
