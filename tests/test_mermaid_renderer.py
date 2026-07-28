"""
Tests for Feature #48: Mermaid.js Diagram Rendering.
"""

import pytest

from src.plugins.mermaid_renderer import (
    MermaidRendererPlugin,
    _detect_and_extract_mermaid,
    _encode_mermaid_for_url,
)


class TestDetectMermaid:
    """Tests for Mermaid code detection."""

    def test_detect_graph(self):
        code = _detect_and_extract_mermaid("graph TD; A-->B;")
        assert code is not None
        assert "graph" in code

    def test_detect_sequencediagram(self):
        code = _detect_and_extract_mermaid("sequenceDiagram; Alice->>John: Hello;")
        assert code is not None
        assert "sequenceDiagram" in code

    def test_detect_flowchart(self):
        code = _detect_and_extract_mermaid("flowchart LR; A-->B;")
        assert code is not None

    def test_detect_mermaid_block(self):
        code = _detect_and_extract_mermaid("```mermaid\ngraph TD;\nA-->B;\n```")
        assert code is not None
        assert "graph" in code

    def test_detect_no_mermaid(self):
        code = _detect_and_extract_mermaid("Just some random text")
        assert code is None

    def test_detect_pie(self):
        code = _detect_and_extract_mermaid('pie title Test "A" : 50 "B" : 50')
        assert code is not None
        assert "pie" in code


class TestEncodeMermaid:
    """Tests for Mermaid URL encoding."""

    def test_encode_simple(self):
        encoded = _encode_mermaid_for_url("graph TD; A-->B;")
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    def test_encode_different_diagrams(self):
        encoded1 = _encode_mermaid_for_url("graph TD; A-->B;")
        encoded2 = _encode_mermaid_for_url("sequenceDiagram; A->>B: Hi;")
        assert encoded1 != encoded2


class TestMermaidRendererPlugin:
    """Tests for the MermaidRendererPlugin class."""

    def test_empty_input(self):
        plugin = MermaidRendererPlugin()
        result = plugin.execute("")
        assert not result.success

    def test_valid_mermaid(self):
        plugin = MermaidRendererPlugin()
        result = plugin.execute("graph TD; A-->B;")
        assert result.success
        assert "Mermaid" in result.output

    def test_sequence_diagram(self):
        plugin = MermaidRendererPlugin()
        result = plugin.execute("sequenceDiagram; Alice->>Bob: Hello;")
        assert result.success
        assert "Mermaid" in result.output

    def test_mermaid_block(self):
        plugin = MermaidRendererPlugin()
        result = plugin.execute("```mermaid\ngraph TD;\nA-->B;\n```")
        assert result.success

    def test_no_mermaid_syntax_found(self):
        plugin = MermaidRendererPlugin()
        result = plugin.execute("this is just plain text with no diagram")
        assert not result.success
