"""
Unit tests for Code Theme Picker.

Tests:
- get_available_themes returns all themes
- get_theme_info returns correct metadata
- get_theme_css returns CSS for non-default themes
- get_theme_css returns empty for default theme
- All themes have required fields (name, icon, css)
- Theme CSS contains valid style elements
- Default fallback for unknown theme ID
"""

import pytest

from ui.code_theme_picker import (
    get_available_themes,
    get_theme_info,
    get_theme_css,
    _THEMES,
    _DEFAULT_THEME,
)


class TestCodeThemePicker:
    def test_available_themes(self):
        themes = get_available_themes()
        assert len(themes) >= 4  # monokai, github_dark, onedark, solarized + default
        assert "default" in themes
        assert "monokai" in themes
        assert "github_dark" in themes

    def test_theme_info_default(self):
        info = get_theme_info("default")
        assert info is not None
        assert info["name"] == "Default"
        assert info["css"] == ""

    def test_theme_info_monokai(self):
        info = get_theme_info("monokai")
        assert info is not None
        assert info["name"] == "Monokai"
        assert "pre" in info["css"]
        assert "background" in info["css"]

    def test_theme_info_github_dark(self):
        info = get_theme_info("github_dark")
        assert info is not None
        assert "GitHub" in info["name"]
        assert info["css"] != ""

    def test_theme_info_onedark(self):
        info = get_theme_info("onedark")
        assert info is not None
        assert "OneDark" in info["name"] or "One Dark" in info["name"]

    def test_theme_info_solarized(self):
        info = get_theme_info("solarized")
        assert info is not None
        assert "Solarized" in info["name"]

    def test_unknown_theme_falls_back_to_default(self):
        info = get_theme_info("nonexistent_theme")
        assert info is not None
        assert info["name"] == "Default"
        assert info["css"] == ""

    def test_get_theme_css_default_empty(self):
        assert get_theme_css("default") == ""

    def test_get_theme_css_non_default(self):
        css = get_theme_css("monokai")
        assert "!important" in css
        assert "background" in css

    def test_get_theme_css_unknown_returns_empty(self):
        assert get_theme_css("nonexistent") == ""

    def test_all_themes_have_required_fields(self):
        for tid, info in _THEMES.items():
            assert "name" in info, f"Theme {tid} missing 'name'"
            assert "icon" in info, f"Theme {tid} missing 'icon'"
            assert "description" in info, f"Theme {tid} missing 'description'"
            assert "css" in info, f"Theme {tid} missing 'css'"

    def test_all_css_is_valid_style(self):
        for tid, info in _THEMES.items():
            css = info["css"]
            if css:  # Non-default themes
                assert "{" in css, f"Theme {tid} CSS missing {{"
                assert "}" in css, f"Theme {tid} CSS missing }}"
                assert "color" in css or "background" in css

    def test_theme_names_are_unique(self):
        names = [info["name"] for info in _THEMES.values()]
        assert len(names) == len(set(names)), "Duplicate theme names found"

    def test_dark_themes_have_dark_backgrounds(self):
        """Dark code themes should have dark background colors."""
        for tid in ["monokai", "github_dark", "onedark", "solarized"]:
            info = get_theme_info(tid)
            css = info["css"]
            # All dark themes should use dark bg
            assert "#272822" in css or "#0d1117" in css or "#1e2127" in css or "#002b36" in css

    def test_render_code_theme_picker_runs(self):
        """render_code_theme_picker should not crash when called."""
        from ui.code_theme_picker import render_code_theme_picker
        # We can't fully test Streamlit rendering, but we can at least
        # verify the import works and the function is callable.
        assert callable(render_code_theme_picker)
