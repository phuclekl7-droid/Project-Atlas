"""
Tests for Feature #56: Mindmap Interactive View.
"""

import pytest

from src.plugins.mindmap_generator import (
    MindmapPlugin,
    MindmapNode,
    _parse_text_to_tree,
    _parse_indented_lines,
    _build_markdown_mindmap,
)


class TestMindmapNode:
    """Tests for MindmapNode class."""

    def test_create_node(self):
        node = MindmapNode(label="Root")
        assert node.label == "Root"
        assert node.children == []

    def test_add_child(self):
        node = MindmapNode(label="Root")
        child = node.add_child("Child")
        assert child.label == "Child"
        assert child.level == 1
        assert len(node.children) == 1

    def test_count_nodes(self):
        root = MindmapNode(label="Root")
        root.add_child("Child 1")
        c2 = root.add_child("Child 2")
        c2.add_child("Grandchild")
        assert root.count_nodes() == 4

    def test_max_depth(self):
        root = MindmapNode(label="Root")
        c = root.add_child("Level 1")
        c.add_child("Level 2")
        assert root.max_depth() == 2


class TestParseTextToTree:
    """Tests for text parsing."""

    def test_colon_format(self):
        tree = _parse_text_to_tree("Python: Basics, OOP, Async")
        assert tree.label == "Python"
        assert len(tree.children) == 3

    def test_nested_colon(self):
        tree = _parse_text_to_tree("Project: Core: auth, db | UI: web, mobile")
        assert tree.label == "Project"
        assert len(tree.children) == 2

    def test_path_notation(self):
        tree = _parse_text_to_tree("A > B > C")
        assert tree.label == "A"
        assert len(tree.children) == 1
        assert tree.children[0].label == "B"

    def test_comma_list(self):
        tree = _parse_text_to_tree("apple, banana, cherry")
        assert tree.label == "apple"
        assert len(tree.children) == 2

    def test_pipe_separator(self):
        tree = _parse_text_to_tree("Section 1 | Section 2 | Section 3")
        assert len(tree.children) == 2

    def test_single_topic(self):
        tree = _parse_text_to_tree("Just a Title")
        assert tree.label == "Just a Title"
        assert len(tree.children) == 0

    def test_empty_text(self):
        tree = _parse_text_to_tree("")
        assert tree.label == "Empty"

    def test_indented_lines(self):
        text = "My Project\n  - Planning\n  - Development\n    - Frontend\n    - Backend\n  - Testing"
        tree = _parse_text_to_tree(text)
        assert tree.label == "My Project"
        assert len(tree.children) == 3

    def test_markdown_list(self):
        text = "Topics\n  * Python\n  * JavaScript\n  * Rust"
        tree = _parse_text_to_tree(text)
        assert tree.label == "Topics"
        assert len(tree.children) == 3


class TestBuildMarkdownMindmap:
    """Tests for Markdown rendering."""

    def test_basic_markdown(self):
        root = MindmapNode(label="Root")
        root.add_child("Item 1")
        root.add_child("Item 2")
        md = _build_markdown_mindmap(root)
        assert "Root" in md
        assert "Item 1" in md
        assert "Item 2" in md
        assert "Mindmap" in md

    def test_empty_tree_markdown(self):
        root = MindmapNode(label="Only Node")
        md = _build_markdown_mindmap(root)
        assert "Only Node" in md


class TestMindmapPlugin:
    """Tests for MindmapPlugin class."""

    def test_empty_input(self):
        plugin = MindmapPlugin()
        result = plugin.execute("")
        assert not result.success

    def test_simple_mindmap(self):
        plugin = MindmapPlugin()
        result = plugin.execute("Python: Basics, OOP, Async")
        assert result.success
        assert "Mindmap" in result.output
        assert "Python" in result.output

    def test_nested_mindmap(self):
        plugin = MindmapPlugin()
        result = plugin.execute("Project: Core: auth, db | UI: web")
        assert result.success

    def test_path_format(self):
        plugin = MindmapPlugin()
        result = plugin.execute("A > B > C")
        assert result.success

    def test_markdown_mode(self):
        plugin = MindmapPlugin()
        result = plugin.execute("/markdown Python: Basics, OOP")
        assert result.success

    def test_ascii_mode(self):
        plugin = MindmapPlugin()
        result = plugin.execute("/ascii Python: Basics, OOP")
        assert result.success

    def test_bracket_mode(self):
        plugin = MindmapPlugin()
        result = plugin.execute("/bracket Python: Basics, OOP")
        assert result.success

    def test_command_without_content(self):
        plugin = MindmapPlugin()
        result = plugin.execute("/markdown")
        assert not result.success
