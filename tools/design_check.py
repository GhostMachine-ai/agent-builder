"""
Deterministic design-quality linter backed by a vendored subset of Impeccable.

Impeccable (https://github.com/pbakaus/impeccable, Apache-2.0) ships a standalone
Node-based detector with 59 rules for UI anti-patterns ("AI slop" tells and quality
issues). This tool shells out to the vendored copy and returns structured findings.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from strands import tool

# Minimum Node.js version required by the vendored detector
_MIN_NODE_VERSION = (22, 18)

# Seconds before a detector run is aborted
_DETECT_TIMEOUT_SECONDS = 120


def _vendor_root() -> Path:
    """Locate the vendored Impeccable directory inside the installed package.

    Assumes a real on-disk install (hatchling wheels are not imported from zip).
    """
    import strands_agents_builder

    return Path(strands_agents_builder.__file__).parent / "vendor" / "impeccable"


def _node_version(node: str) -> Optional[Tuple[int, int]]:
    """Return (major, minor) of the Node.js executable, or None if undeterminable."""
    try:
        result = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.match(r"v(\d+)\.(\d+)", result.stdout.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _format_finding(finding: Dict[str, Any]) -> str:
    severity = finding.get("severity", "?")
    if finding.get("advisory"):
        severity = f"{severity} (advisory)"
    location = str(finding.get("file", "?"))
    line = finding.get("line")
    if line is not None:
        location = f"{location}:{line}"
    text = f"{severity} | {location} | {finding.get('name', finding.get('antipattern', '?'))}"
    description = finding.get("description")
    if description:
        text += f" — {description}"
    snippet = finding.get("snippet")
    if snippet:
        text += f" [snippet: {snippet}]"
    imported_by = finding.get("importedBy")
    if imported_by:
        text += f" (imported by: {', '.join(imported_by)})"
    return text


def _summarize(findings: List[Dict[str, Any]], max_findings: int) -> List[Dict[str, str]]:
    advisory = [f for f in findings if f.get("advisory")]
    errors = [f for f in findings if not f.get("advisory") and f.get("severity") == "error"]
    warnings = [f for f in findings if not f.get("advisory") and f.get("severity") == "warning"]
    files = {f.get("file") for f in findings}
    by_category: Dict[str, int] = {}
    for finding in findings:
        category = str(finding.get("category", "unknown"))
        by_category[category] = by_category.get(category, 0) + 1
    categories = ", ".join(f"{name}: {count}" for name, count in sorted(by_category.items()))

    headline = (
        f"🎨 {len(findings)} design finding(s) ({len(errors)} error, {len(warnings)} warning, "
        f"{len(advisory)} advisory) across {len(files)} file(s). By category: {categories}. "
        "Fix error/warning findings before declaring UI work done; use judgment on advisory ones."
    )

    shown = findings[:max_findings]
    lines = [_format_finding(f) for f in shown]
    if len(findings) > max_findings:
        lines.append(f"... and {len(findings) - max_findings} more (raise max_findings or narrow paths)")

    content = [{"text": headline}, {"text": "\n".join(lines)}]
    content.append({"text": "Findings as JSON:\n" + json.dumps(shown, indent=2)})
    return content


@tool
def design_check(
    paths: List[str],
    scope: Optional[str] = None,
    include_advisory: bool = True,
    max_findings: int = 50,
) -> Dict[str, Any]:
    """
    Scan UI code for design anti-patterns and quality issues (powered by Impeccable, Apache-2.0).

    Runs a deterministic detector with 59 rules against HTML/CSS/JSX/TSX/Vue/Svelte/Astro
    files. Run this after ANY frontend/UI edits, on the changed files or their directory, and
    fix all error/warning findings before declaring the task done. Requires Node.js >= 22.18
    on PATH. Pair with the design_guide tool, which provides the design guidance to follow
    while building.

    Args:
        paths: Files or directories to scan.
        scope: Optional comma-separated design domains to restrict to (e.g. "type", "layout").
        include_advisory: Include advisory findings (softer suggestions) in the results.
        max_findings: Maximum number of findings to include in the output.

    Returns:
        A dictionary with "status" and "content" summarizing the findings.
    """
    if not paths:
        return {"status": "error", "content": [{"text": "❌ Provide at least one file or directory to scan."}]}

    resolved: List[str] = []
    for raw_path in paths:
        candidate = Path(raw_path).resolve()
        if not candidate.exists():
            return {"status": "error", "content": [{"text": f"❌ Path does not exist: {raw_path}"}]}
        resolved.append(str(candidate))

    node = shutil.which("node")
    if node is None:
        return {
            "status": "error",
            "content": [
                {
                    "text": (
                        "❌ design_check requires Node.js >= 22.18 (used by the vendored Impeccable "
                        "detector), but no `node` executable was found on PATH. Install it from "
                        "https://nodejs.org/ and try again."
                    )
                }
            ],
        }
    version = _node_version(node)
    if version is not None and version < _MIN_NODE_VERSION:
        return {
            "status": "error",
            "content": [
                {
                    "text": (
                        f"❌ design_check requires Node.js >= 22.18; found v{version[0]}.{version[1]}. "
                        "Upgrade from https://nodejs.org/ and try again."
                    )
                }
            ],
        }

    vendor_root = _vendor_root()
    cli_js = vendor_root / "cli" / "bin" / "cli.js"
    if not cli_js.is_file():
        return {
            "status": "error",
            "content": [{"text": f"❌ Vendored detector not found at {cli_js}. Reinstall the package."}],
        }

    command = [node, str(cli_js), "detect", "--json", "--quiet", "--no-config"]
    if scope:
        command += ["--scope", scope]
    if not include_advisory:
        command.append("--no-advisory")
    command += resolved

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=_DETECT_TIMEOUT_SECONDS,
            cwd=str(vendor_root),
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "content": [{"text": f"❌ Design check timed out after {_DETECT_TIMEOUT_SECONDS}s. Narrow the paths."}],
        }
    except OSError as e:
        return {"status": "error", "content": [{"text": f"❌ Failed to run the design detector: {e}"}]}

    # Exit code 2 means "findings present" — a successful scan, not an error
    if result.returncode not in (0, 2):
        stderr_tail = result.stderr.strip()[-2000:] or "(no error output)"
        return {
            "status": "error",
            "content": [{"text": f"❌ Design detector failed (exit {result.returncode}):\n{stderr_tail}"}],
        }

    try:
        findings = json.loads(result.stdout)
    except json.JSONDecodeError:
        stdout_head = result.stdout.strip()[:500] or "(empty output)"
        return {
            "status": "error",
            "content": [{"text": f"❌ Could not parse detector output as JSON:\n{stdout_head}"}],
        }

    if not findings:
        return {"status": "success", "content": [{"text": "✅ No design antipatterns found."}]}
    return {"status": "success", "content": _summarize(findings, max_findings)}
