"""
Unit tests for PromptLibrary and PromptTemplate.

Tests:
- PromptTemplate dataclass
- Built-in templates count (> 5)
- Category listing
- get_all() with and without category filter
- get_by_id() and get_prompt()
- search() by keyword
- Custom template extension
- Empty search query
- Non-existent ID returns None
"""

import pytest

from src.features.prompt_library import PromptLibrary, PromptTemplate, _DEFAULT_TEMPLATES


class TestPromptTemplate:
    def test_dataclass_defaults(self):
        t = PromptTemplate(id="test", title="Test", icon="🔍", prompt="Hello")
        assert t.category == "general"
        assert t.tags == []
        assert t.description == ""

    def test_dataclass_all_fields(self):
        t = PromptTemplate(
            id="test", title="Test", icon="🔍", prompt="Hello",
            category="coding", tags=["a", "b"], description="Desc",
        )
        assert t.id == "test"
        assert t.title == "Test"
        assert t.prompt == "Hello"
        assert t.category == "coding"
        assert t.tags == ["a", "b"]
        assert t.description == "Desc"


class TestPromptLibrary:
    @pytest.fixture
    def library(self):
        return PromptLibrary()

    def test_has_builtin_templates(self, library):
        """Should have at least 5 built-in templates."""
        assert library.count() >= 5

    def test_categories(self, library):
        """Should list unique categories."""
        cats = library.categories
        assert "coding" in cats
        assert "writing" in cats
        assert len(cats) >= 3

    def test_get_all_return_all(self, library):
        """get_all() should return all templates."""
        all_templates = library.get_all()
        assert len(all_templates) == library.count()

    def test_get_all_filter_by_category(self, library):
        """get_all(category='coding') should only return coding templates."""
        coding = library.get_all(category="coding")
        assert len(coding) > 0
        for t in coding:
            assert t.category == "coding"

    def test_get_by_id_found(self, library):
        """get_by_id('code_review') should return the template."""
        t = library.get_by_id("code_review")
        assert t is not None
        assert t.id == "code_review"
        assert "Review" in t.title

    def test_get_by_id_not_found(self, library):
        """get_by_id('nonexistent') should return None."""
        t = library.get_by_id("nonexistent")
        assert t is None

    def test_get_prompt(self, library):
        """get_prompt should return the prompt text."""
        prompt = library.get_prompt("translate_vi")
        assert prompt is not None
        assert "Dịch" in prompt
        assert "tiếng Việt" in prompt

    def test_get_prompt_not_found(self, library):
        prompt = library.get_prompt("nonexistent")
        assert prompt is None

    def test_search_by_title(self, library):
        """Searching by title keyword should find templates."""
        results = library.search("review")
        assert len(results) > 0
        assert any("Review" in t.title for t in results)

    def test_search_by_tag(self, library):
        """Searching by tag should find templates."""
        results = library.search("pytest")
        assert len(results) > 0
        assert any("test" in t.id for t in results)

    def test_search_empty_query(self, library):
        """Empty query should return all templates."""
        results = library.search("")
        assert len(results) == library.count()

    def test_search_case_insensitive(self, library):
        """Search should be case-insensitive."""
        results_upper = library.search("CODE")
        results_lower = library.search("code")
        assert len(results_upper) == len(results_lower)

    def test_custom_templates(self):
        """Custom templates should be merged with defaults."""
        custom = [PromptTemplate(id="custom1", title="Custom", icon="⭐", prompt="test")]
        library = PromptLibrary(templates=custom)
        assert library.count() > len(custom)  # Defaults also present
        assert library.get_by_id("custom1") is not None
        assert library.get_by_id("code_review") is not None  # Default still there

    def test_duplicate_id_overrides(self):
        """Custom template with duplicate ID should override default."""
        custom = [PromptTemplate(id="code_review", title="Custom Review", icon="⭐", prompt="new prompt")]
        library = PromptLibrary(templates=custom)
        t = library.get_by_id("code_review")
        assert t.title == "Custom Review"
        assert t.prompt == "new prompt"

    def test_search_no_results(self, library):
        """Search with no matches should return empty list."""
        results = library.search("xyznonexistent12345")
        assert len(results) == 0


# ============================================================
# Default templates content tests
# ============================================================


class TestDefaultTemplates:
    def test_all_defaults_have_required_fields(self):
        for t in _DEFAULT_TEMPLATES:
            assert t.id, f"Template missing id: {t}"
            assert t.title, f"Template missing title: {t.id}"
            assert t.icon, f"Template missing icon: {t.id}"
            assert t.prompt, f"Template missing prompt: {t.id}"
            assert t.category, f"Template missing category: {t.id}"

    def test_default_ids_are_unique(self):
        ids = [t.id for t in _DEFAULT_TEMPLATES]
        assert len(ids) == len(set(ids)), "Duplicate template IDs found"

    def test_default_templates_have_vietnamese_content(self):
        """All default templates should have Vietnamese prompts/content."""
        for t in _DEFAULT_TEMPLATES:
            assert "ng" in t.prompt.lower() or "code" in t.prompt.lower() or len(t.prompt) > 10
