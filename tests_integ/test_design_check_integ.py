"""
Integration tests for the design_check tool — runs the real vendored detector.

Requires Node.js >= 22.18 on PATH; skipped otherwise.
"""

import shutil

import pytest

from tools.design_check import _node_version, design_check

# Single-line CSS declaration: the gradient-text rule keys on this form
GRADIENT_TEXT_CSS = (
    "h1 { background: linear-gradient(90deg, #ff0080, #7928ca); "
    "-webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }"
)
GRADIENT_TEXT_HTML = f"""<!doctype html>
<html><head><style>
{GRADIENT_TEXT_CSS}
</style></head><body><h1>Hello</h1></body></html>
"""

CLEAN_HTML = """<!doctype html>
<html><head><style>
body { color: #1a1a1a; background: #ffffff; font-size: 1rem; line-height: 1.5; }
</style></head><body><p>Hello</p></body></html>
"""


def _node_available() -> bool:
    node = shutil.which("node")
    if node is None:
        return False
    version = _node_version(node)
    return version is not None and version >= (22, 18)


pytestmark = pytest.mark.skipif(not _node_available(), reason="requires Node.js >= 22.18 on PATH")


def test_detects_gradient_text(tmp_path):
    target = tmp_path / "index.html"
    target.write_text(GRADIENT_TEXT_HTML, encoding="utf-8")

    result = design_check(paths=[str(tmp_path)])

    assert result["status"] == "success"
    combined = " ".join(block["text"] for block in result["content"])
    assert "gradient-text" in combined or "Gradient text" in combined


def test_clean_html_has_no_findings(tmp_path):
    target = tmp_path / "clean.html"
    target.write_text(CLEAN_HTML, encoding="utf-8")

    result = design_check(paths=[str(target)])

    assert result["status"] == "success"
    assert "No design antipatterns" in result["content"][0]["text"]
