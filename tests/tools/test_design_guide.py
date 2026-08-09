#!/usr/bin/env python3
"""
Unit tests for the design_guide tool
"""

from tools.design_guide import design_guide


class TestDesignGuideList:
    """Test cases for design_guide(action='list')"""

    def test_list_includes_expected_guides(self):
        result = design_guide(action="list")

        assert result["status"] == "success"
        text = result["content"][0]["text"]
        assert "- craft-floor" in text
        assert "- new-work" in text
        assert "- overview" in text
        assert "- degraded/" in text

    def test_list_excludes_live_mode_guides(self):
        result = design_guide(action="list")

        text = result["content"][0]["text"]
        assert "- live\n" not in text
        assert "- live-setup" not in text

    def test_list_includes_protocol_note(self):
        result = design_guide(action="list")

        assert "craft-floor" in result["content"][0]["text"]
        assert "design_check" in result["content"][0]["text"]


class TestDesignGuideGet:
    """Test cases for design_guide(action='get')"""

    def test_get_craft_floor(self):
        result = design_guide(action="get", name="craft-floor")

        assert result["status"] == "success"
        text = result["content"][0]["text"]
        assert len(text) > 500
        # Placeholder regression guard: compiled guidance must have no template placeholders
        assert "{{" not in text

    def test_get_overview(self):
        result = design_guide(action="get", name="overview")

        assert result["status"] == "success"
        assert len(result["content"][0]["text"]) > 500

    def test_get_degraded_guide(self):
        result = design_guide(action="get", name="degraded/finish-reviewer")

        assert result["status"] == "success"
        assert len(result["content"][0]["text"]) > 100

    def test_get_rejects_path_traversal(self):
        result = design_guide(action="get", name="../../../etc/passwd")

        assert result["status"] == "error"

    def test_get_rejects_absolute_path(self):
        result = design_guide(action="get", name="/etc/passwd")

        assert result["status"] == "error"

    def test_get_rejects_unknown_name(self):
        result = design_guide(action="get", name="not-a-real-guide")

        assert result["status"] == "error"
        assert "Unknown guide" in result["content"][0]["text"]

    def test_get_requires_name(self):
        result = design_guide(action="get")

        assert result["status"] == "error"


class TestDesignGuideContext:
    """Test cases for design_guide(action='context')"""

    def test_context_resolves_walking_up(self, tmp_path):
        (tmp_path / "Product.md").write_text("# Product\nBrand personality: bold", encoding="utf-8")
        nested = tmp_path / "src" / "components"
        nested.mkdir(parents=True)

        result = design_guide(action="context", path=str(nested))

        assert result["status"] == "success"
        text = result["content"][0]["text"]
        assert str(tmp_path) in text
        assert "Brand personality: bold" in text

    def test_context_reads_both_files(self, tmp_path):
        (tmp_path / "PRODUCT.md").write_text("product strategy", encoding="utf-8")
        (tmp_path / "DESIGN.md").write_text("design tokens", encoding="utf-8")

        result = design_guide(action="context", path=str(tmp_path))

        assert result["status"] == "success"
        text = result["content"][0]["text"]
        assert "product strategy" in text
        assert "design tokens" in text

    def test_context_without_files_returns_note(self, tmp_path):
        result = design_guide(action="context", path=str(tmp_path / "empty"))

        # Nonexistent start directory is an error
        assert result["status"] == "error"

        (tmp_path / "empty").mkdir()
        result = design_guide(action="context", path=str(tmp_path / "empty"))

        assert result["status"] == "success"
        assert "No PRODUCT.md or DESIGN.md found" in result["content"][0]["text"]


class TestDesignGuideActions:
    """Test cases for action dispatch"""

    def test_unknown_action(self):
        result = design_guide(action="delete-everything")

        assert result["status"] == "error"
        assert "Unknown action" in result["content"][0]["text"]
