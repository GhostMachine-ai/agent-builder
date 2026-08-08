#!/usr/bin/env python3
"""
Unit tests for the design_check tool (detector subprocess fully mocked)
"""

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from tools.design_check import _node_version, _vendor_root, design_check

FINDING_WARNING = {
    "antipattern": "gradient-text",
    "name": "Gradient text",
    "description": "Gradient text is decorative rather than meaningful.",
    "severity": "warning",
    "category": "slop",
    "file": "/project/src/App.tsx",
    "line": 31,
    "snippet": "background-clip: text + gradient",
    "importedBy": ["Card.tsx"],
}

FINDING_ERROR = {
    "antipattern": "low-contrast",
    "name": "Low contrast",
    "description": "Text contrast below 4.5:1.",
    "severity": "error",
    "category": "quality",
    "file": "/project/src/styles.css",
    "line": 4,
}

FINDING_ADVISORY = {
    "antipattern": "em-dash-overuse",
    "name": "Em-dash overuse",
    "description": "Too many em dashes.",
    "severity": "warning",
    "category": "slop",
    "file": "/project/src/copy.md",
    "line": 2,
    "advisory": True,
}


def _completed(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def scan_target(tmp_path):
    target = tmp_path / "index.html"
    target.write_text("<html></html>", encoding="utf-8")
    return str(target)


class TestDesignCheckPreflight:
    """Test cases for input and environment validation"""

    def test_empty_paths(self):
        result = design_check(paths=[])

        assert result["status"] == "error"

    def test_nonexistent_path(self):
        result = design_check(paths=["/does/not/exist.html"])

        assert result["status"] == "error"
        assert "does not exist" in result["content"][0]["text"]

    def test_node_missing(self, scan_target):
        with mock.patch("tools.design_check.shutil.which", return_value=None):
            result = design_check(paths=[scan_target])

        assert result["status"] == "error"
        assert "Node.js" in result["content"][0]["text"]

    def test_node_too_old(self, scan_target):
        with (
            mock.patch("tools.design_check.shutil.which", return_value="/usr/bin/node"),
            mock.patch("tools.design_check._node_version", return_value=(18, 19)),
        ):
            result = design_check(paths=[scan_target])

        assert result["status"] == "error"
        assert "22.18" in result["content"][0]["text"]
        assert "v18.19" in result["content"][0]["text"]


class TestDesignCheckScan:
    """Test cases for detector invocation and output handling"""

    def _run(self, scan_target, run_result, **kwargs):
        with (
            mock.patch("tools.design_check.shutil.which", return_value="/usr/bin/node"),
            mock.patch("tools.design_check._node_version", return_value=(22, 18)),
            mock.patch("tools.design_check.subprocess.run", return_value=run_result) as mock_run,
        ):
            result = design_check(paths=[scan_target], **kwargs)
        return result, mock_run

    def test_clean_scan(self, scan_target):
        result, _ = self._run(scan_target, _completed(0, stdout="[]"))

        assert result["status"] == "success"
        assert "No design antipatterns" in result["content"][0]["text"]

    def test_findings_reported(self, scan_target):
        findings = [FINDING_ERROR, FINDING_WARNING, FINDING_ADVISORY]
        result, _ = self._run(scan_target, _completed(2, stdout=json.dumps(findings)))

        assert result["status"] == "success"
        headline = result["content"][0]["text"]
        assert "3 design finding(s)" in headline
        assert "1 error" in headline
        assert "1 warning" in headline
        assert "1 advisory" in headline
        detail = result["content"][1]["text"]
        assert "/project/src/styles.css:4" in detail
        assert "Gradient text" in detail
        assert "imported by: Card.tsx" in detail
        # Structured JSON block round-trips
        parsed = json.loads(result["content"][2]["text"].split("Findings as JSON:\n", 1)[1])
        assert len(parsed) == 3

    def test_truncation(self, scan_target):
        findings = [dict(FINDING_WARNING, line=i) for i in range(60)]
        result, _ = self._run(scan_target, _completed(2, stdout=json.dumps(findings)), max_findings=50)

        assert result["status"] == "success"
        assert "... and 10 more" in result["content"][1]["text"]

    def test_detector_error_exit(self, scan_target):
        result, _ = self._run(scan_target, _completed(1, stderr="Unknown option: --bogus"))

        assert result["status"] == "error"
        assert "Unknown option: --bogus" in result["content"][0]["text"]

    def test_garbage_output(self, scan_target):
        result, _ = self._run(scan_target, _completed(2, stdout="not json at all"))

        assert result["status"] == "error"
        assert "parse" in result["content"][0]["text"].lower()

    def test_timeout(self, scan_target):
        with (
            mock.patch("tools.design_check.shutil.which", return_value="/usr/bin/node"),
            mock.patch("tools.design_check._node_version", return_value=(22, 18)),
            mock.patch(
                "tools.design_check.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="node", timeout=120),
            ),
        ):
            result = design_check(paths=[scan_target])

        assert result["status"] == "error"
        assert "timed out" in result["content"][0]["text"]

    def test_flag_plumbing(self, scan_target):
        _, mock_run = self._run(scan_target, _completed(0, stdout="[]"), scope="type,layout", include_advisory=False)

        argv = mock_run.call_args[0][0]
        assert "--json" in argv
        assert "--quiet" in argv
        assert "--no-config" in argv
        assert "--no-advisory" in argv
        scope_index = argv.index("--scope")
        assert argv[scope_index + 1] == "type,layout"
        assert argv[-1] == str(Path(scan_target).resolve())

    def test_default_flags_omit_optional(self, scan_target):
        _, mock_run = self._run(scan_target, _completed(0, stdout="[]"))

        argv = mock_run.call_args[0][0]
        assert "--scope" not in argv
        assert "--no-advisory" not in argv


class TestVendoredDetector:
    """Sanity checks on the vendored files themselves (no subprocess)"""

    def test_cli_entry_exists(self):
        assert (_vendor_root() / "cli" / "bin" / "cli.js").is_file()

    def test_esm_stub_package_json(self):
        package = json.loads((_vendor_root() / "package.json").read_text(encoding="utf-8"))

        assert package["type"] == "module"

    def test_guidance_present(self):
        assert (_vendor_root() / "guidance" / "SKILL.md").is_file()
        assert (_vendor_root() / "guidance" / "reference" / "craft-floor.md").is_file()


class TestNodeVersionParsing:
    """Test cases for _node_version"""

    def test_parses_version(self):
        with mock.patch("tools.design_check.subprocess.run", return_value=_completed(0, stdout="v22.18.1\n")):
            assert _node_version("node") == (22, 18)

    def test_unparseable_returns_none(self):
        with mock.patch("tools.design_check.subprocess.run", return_value=_completed(0, stdout="weird")):
            assert _node_version("node") is None

    def test_oserror_returns_none(self):
        with mock.patch("tools.design_check.subprocess.run", side_effect=OSError("boom")):
            assert _node_version("node") is None
