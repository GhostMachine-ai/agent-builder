#!/usr/bin/env python3
"""
Unit tests for the design_agent tool (nested Agent mocked)
"""

from unittest import mock

from tools.design_agent import _agents_root, _catalog, _declared_tools, _parse_definition, design_agent

EXPECTED_AGENTS = [
    "impeccable-asset-producer",
    "impeccable-documenter",
    "impeccable-finish-reviewer",
    "impeccable-manual-edit-applier",
]


class TestVendoredAgentDefinitions:
    """Sanity checks on the vendored agent definition files"""

    def test_all_four_agents_vendored(self):
        catalog = _catalog(_agents_root())

        for name in EXPECTED_AGENTS:
            assert name in catalog
            # Prefix-less alias resolves to the same file
            assert catalog[name.removeprefix("impeccable-")] == catalog[name]

    def test_definitions_parse_with_tools_and_body(self):
        for name in EXPECTED_AGENTS:
            path = _catalog(_agents_root())[name]
            fields, body = _parse_definition(path.read_text(encoding="utf-8"))

            assert fields["name"] == name
            assert _declared_tools(fields), f"{name} declared no mappable tools"
            assert len(body) > 200
            assert not body.startswith("---")


class TestParseDefinition:
    """Test cases for frontmatter parsing"""

    def test_parses_frontmatter_and_body(self):
        fields, body = _parse_definition("---\nname: x\ntools: Read, Bash\n---\n# Body\ntext")

        assert fields == {"name": "x", "tools": "Read, Bash"}
        assert body == "# Body\ntext"

    def test_no_frontmatter(self):
        fields, body = _parse_definition("# Just a body")

        assert fields == {}
        assert body == "# Just a body"

    def test_unterminated_frontmatter(self):
        text = "---\nname: x\nno closing fence"
        fields, body = _parse_definition(text)

        assert fields == {}
        assert body == text


class TestDeclaredTools:
    """Test cases for tool-name mapping"""

    def test_maps_and_dedupes(self):
        tools = _declared_tools({"tools": "Read, Write, Edit, Bash, Glob, Grep"})

        assert tools == ["file_read", "file_write", "editor", "shell"]

    def test_unknown_names_ignored(self):
        assert _declared_tools({"tools": "Read, TotallyUnknown"}) == ["file_read"]

    def test_missing_field(self):
        assert _declared_tools({}) == []


class TestDesignAgentRun:
    """Test cases for the design_agent tool itself"""

    def test_empty_task(self):
        result = design_agent(agent="finish-reviewer", task="  ")

        assert result["status"] == "error"

    def test_unknown_agent(self):
        result = design_agent(agent="nonexistent", task="review this")

        assert result["status"] == "error"
        assert "finish-reviewer" in result["content"][0]["text"]

    def test_runs_nested_agent(self):
        mock_agent_instance = mock.MagicMock(return_value="ordered fixes: none")
        with mock.patch("tools.design_agent.Agent", return_value=mock_agent_instance) as mock_agent_cls:
            result = design_agent(agent="finish-reviewer", task="Review artifact at /tmp/app")

        assert result["status"] == "success"
        assert "ordered fixes: none" in result["content"][0]["text"]
        # System prompt is the definition body (frontmatter stripped)
        system_prompt = mock_agent_cls.call_args.kwargs["system_prompt"]
        assert "finishing reviewer" in system_prompt
        assert not system_prompt.startswith("---")
        mock_agent_instance.assert_called_once_with("Review artifact at /tmp/app")

    def test_nested_agent_failure(self):
        with mock.patch("tools.design_agent.Agent", side_effect=RuntimeError("model unavailable")):
            result = design_agent(agent="documenter", task="document the design system")

        assert result["status"] == "error"
        assert "model unavailable" in result["content"][0]["text"]

    def test_prefixed_name_accepted(self):
        mock_agent_instance = mock.MagicMock(return_value="done")
        with mock.patch("tools.design_agent.Agent", return_value=mock_agent_instance):
            result = design_agent(agent="impeccable-asset-producer", task="produce hero texture")

        assert result["status"] == "success"
