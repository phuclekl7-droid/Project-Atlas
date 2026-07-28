"""
Tests for Feature #53: Diagram Generator Plugin.
"""

import pytest

from src.plugins.diagram_generator import (
    DiagramGeneratorPlugin,
    _detect_diagram_type,
    _build_flowchart,
    _build_sequence,
    _build_pie,
    _build_class_diagram,
)


class TestDetectDiagramType:
    """Tests for diagram type detection."""

    def test_detect_flowchart(self):
        assert _detect_diagram_type("flowchart: A -> B") == "flowchart"
        assert _detect_diagram_type("graph: A -> B") == "flowchart"
        assert _detect_diagram_type("flow: A -> B") == "flowchart"

    def test_detect_sequence(self):
        assert _detect_diagram_type("sequence: A -> B") == "sequence"
        assert _detect_diagram_type("seq: X -> Y") == "sequence"

    def test_detect_pie(self):
        assert _detect_diagram_type("pie: A 30%") == "pie"

    def test_detect_class(self):
        assert _detect_diagram_type("class: User") == "class"

    def test_no_match(self):
        assert _detect_diagram_type("something random") is None


class TestBuildFlowchart:
    """Tests for flowchart generation."""

    def test_simple_flow(self):
        result = _build_flowchart("A -> B, B -> C")
        assert "```mermaid" in result
        assert "flowchart TD" in result
        assert "A --> B" in result
        assert "B --> C" in result

    def test_flow_with_labels(self):
        result = _build_flowchart("A -- login --> B, B -- validate --> C")
        assert "login" in result
        assert "validate" in result


class TestBuildSequence:
    """Tests for sequence diagram generation."""

    def test_simple_sequence(self):
        result = _build_sequence("Client sends request to Server")
        assert "sequenceDiagram" in result
        assert "Client" in result
        assert "Server" in result

    def test_arrow_sequence(self):
        result = _build_sequence("A -> B: Hello")
        assert "A->>B: Hello" in result


class TestBuildPie:
    """Tests for pie chart generation."""

    def test_simple_pie(self):
        result = _build_pie("Python 40%, Java 35%, JS 25%")
        assert "pie" in result
        assert "Python" in result
        assert "40" in result

    def test_pie_with_actual_prefix(self):
        result = _build_pie("pie: A 50%, B 50%")
        assert "A" in result
        assert "50" in result


class TestBuildClassDiagram:
    """Tests for class diagram generation."""

    def test_simple_class(self):
        result = _build_class_diagram("User: login(), logout()")
        assert "classDiagram" in result
        assert "class User" in result
        assert "login()" in result
        assert "logout()" in result


class TestDiagramGeneratorPlugin:
    """Tests for the DiagramGeneratorPlugin class."""

    def test_empty_input(self):
        plugin = DiagramGeneratorPlugin()
        result = plugin.execute("")
        assert not result.success

    def test_flowchart_output(self):
        plugin = DiagramGeneratorPlugin()
        result = plugin.execute("flowchart: Login -> Dashboard")
        assert result.success
        assert "mermaid" in result.output
        assert "Login" in result.output

    def test_pie_output(self):
        plugin = DiagramGeneratorPlugin()
        result = plugin.execute("pie: Python 40%, Java 35%")
        assert result.success
        assert "Python" in result.output
