"""
Unit tests for Research Paper Writer Plugin.

Tests:
- ResearchPaper and PaperSection dataclasses
- Outline generation from topic
- Paper formatting as Markdown
- APA citation formatting
- Plugin execution with commands: outline, abstract, cite
- Plugin metadata
- Error handling (empty input, malformed commands)
"""

import pytest

from src.plugin import BasePlugin, PluginResult
from src.plugins.research_writer import (
    ResearchWriterPlugin,
    PaperSection,
    ResearchPaper,
    _generate_outline,
    _format_paper,
    _format_apa_citation,
    _PAPER_TEMPLATES,
)


# ============================================================
# Data Model Tests
# ============================================================


class TestDataModels:
    def test_paper_section_defaults(self):
        section = PaperSection()
        assert section.heading == ""
        assert section.content == ""
        assert section.subsections == []

    def test_paper_section_with_values(self):
        section = PaperSection(heading="Introduction", content="Hello world")
        assert section.heading == "Introduction"
        assert section.content == "Hello world"

    def test_research_paper_defaults(self):
        paper = ResearchPaper()
        assert paper.title == "Untitled Research"
        assert paper.authors == []
        assert paper.sections == []
        assert paper.references == []

    def test_research_paper_with_values(self):
        paper = ResearchPaper(
            title="AI Research",
            authors=["John Doe"],
            sections=[PaperSection(heading="Intro")],
        )
        assert paper.title == "AI Research"
        assert paper.authors == ["John Doe"]
        assert len(paper.sections) == 1


# ============================================================
# APA Citation Tests
# ============================================================


class TestFormatApaCitation:
    def test_basic_citation(self):
        result = _format_apa_citation("Smith, J.", "2024", "AI Advances", "Journal of AI")
        assert "Smith, J." in result
        assert "2024" in result
        assert "AI Advances" in result
        assert "Journal of AI" in result

    def test_multiple_authors(self):
        result = _format_apa_citation("Smith, J. & Doe, A.", "2023", "ML Basics", "JMLR")
        assert "Smith, J." in result
        assert "2023" in result


# ============================================================
# Outline Generation Tests
# ============================================================


class TestGenerateOutline:
    def test_default_template(self):
        paper = _generate_outline("Machine Learning in Healthcare")
        assert paper.title == "Machine Learning in Healthcare"
        assert len(paper.sections) >= 6  # Standard IMRaD has 6 sections
        assert paper.sections[0].heading == "Introduction"

    def test_survey_template(self):
        paper = _generate_outline("Quantum Computing", template="survey")
        assert len(paper.sections) >= 5
        assert "Survey" in _PAPER_TEMPLATES["survey"]["description"]

    def test_technical_template(self):
        paper = _generate_outline("System Design", template="technical")
        assert "System Architecture" in [s.heading for s in paper.sections]

    def test_case_study_template(self):
        paper = _generate_outline("Company Analysis", template="case_study")
        assert "Case Description" in [s.heading for s in paper.sections]

    def test_date_is_set(self):
        paper = _generate_outline("Test Topic")
        assert paper.date is not None
        assert len(paper.date) > 0


# ============================================================
# Paper Formatting Tests
# ============================================================


class TestFormatPaper:
    def test_basic_format(self):
        paper = ResearchPaper(title="Test Paper")
        output = _format_paper(paper)
        assert "# Test Paper" in output
        assert "Project Atlas" in output

    def test_includes_authors(self):
        paper = ResearchPaper(title="Test", authors=["Alice", "Bob"])
        output = _format_paper(paper)
        assert "Alice" in output
        assert "Bob" in output

    def test_includes_abstract(self):
        paper = ResearchPaper(title="Test", abstract="This is an abstract.")
        output = _format_paper(paper)
        assert "Abstract" in output
        assert "This is an abstract" in output

    def test_includes_keywords(self):
        paper = ResearchPaper(title="Test", keywords=["AI", "ML"])
        output = _format_paper(paper)
        assert "Keywords" in output
        assert "AI" in output
        assert "ML" in output

    def test_includes_sections(self):
        paper = ResearchPaper(
            title="Test",
            sections=[PaperSection(heading="Introduction", content="Content here.")],
        )
        output = _format_paper(paper)
        assert "1. Introduction" in output
        assert "Content here." in output

    def test_includes_references(self):
        paper = ResearchPaper(title="Test", references=["Smith, J. (2024)."])
        output = _format_paper(paper)
        assert "References" in output
        assert "Smith" in output


# ============================================================
# Plugin Metadata Tests
# ============================================================


class TestResearchWriterMetadata:
    def test_plugin_name(self):
        plugin = ResearchWriterPlugin()
        assert plugin.name == "research_writer"

    def test_plugin_description(self):
        plugin = ResearchWriterPlugin()
        assert plugin.description is not None
        assert len(plugin.description) > 0

    def test_is_baseplugin_subclass(self):
        assert issubclass(ResearchWriterPlugin, BasePlugin)


# ============================================================
# Plugin Execution Tests
# ============================================================


class TestResearchWriterExecute:
    def test_empty_input(self):
        plugin = ResearchWriterPlugin()
        result = plugin.execute("")
        assert result.success is False

    def test_basic_topic(self):
        """Plain topic should generate outline."""
        plugin = ResearchWriterPlugin()
        result = plugin.execute("Machine Learning")
        assert result.success is True
        assert "Machine Learning" in result.output
        assert "Introduction" in result.output

    def test_outline_command(self):
        """'outline: topic' should generate outline."""
        plugin = ResearchWriterPlugin()
        result = plugin.execute("outline: AI in Healthcare")
        assert result.success is True
        assert "AI in Healthcare" in result.output
        assert "Introduction" in result.output

    def test_outline_with_template(self):
        """'outline: topic survey' should use survey template."""
        plugin = ResearchWriterPlugin()
        result = plugin.execute("outline: AI review survey")
        assert result.success is True
        assert "AI review" in result.output or "survey" in result.output.lower()

    def test_abstract_command(self):
        """'abstract: text' should format abstract."""
        plugin = ResearchWriterPlugin()
        result = plugin.execute("abstract: This paper explores deep learning applications in healthcare.")
        assert result.success is True
        assert "Abstract" in result.output
        assert "deep learning" in result.output

    def test_cite_command(self):
        """'cite: authors year title source' should format APA citation."""
        plugin = ResearchWriterPlugin()
        result = plugin.execute("cite: Smith, J. 2024 AI Advances Journal of AI")
        assert result.success is True
        assert "APA" in result.output or "Citation" in result.output
        assert "Smith, J." in result.output

    def test_cite_missing_year(self):
        """Cite command without year should return error."""
        plugin = ResearchWriterPlugin()
        result = plugin.execute("cite: Smith, J. Some Title Some Source")
        assert result.success is False

    def test_invalid_command_falls_through(self):
        """Unknown command should be treated as topic."""
        plugin = ResearchWriterPlugin()
        result = plugin.execute("random text that is not a command")
        assert result.success is True  # Falls through to topic generation


# ============================================================
# Paper Templates Tests
# ============================================================


class TestPaperTemplates:
    def test_all_templates_have_sections(self):
        for name, template in _PAPER_TEMPLATES.items():
            assert len(template["sections"]) >= 4, f"Template {name} has too few sections"
            assert "description" in template

    def test_research_template_has_standard_sections(self):
        sections = _PAPER_TEMPLATES["research"]["sections"]
        assert "Introduction" in sections
        assert "Conclusion" in sections

    def test_survey_template_is_comprehensive(self):
        sections = _PAPER_TEMPLATES["survey"]["sections"]
        assert "Literature Review" in str(sections) or "Taxonomy" in str(sections)
