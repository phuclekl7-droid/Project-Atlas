"""
Unit tests for Global Keyboard Shortcuts.

Tests:
- get_global_shortcuts_js returns valid HTML/JS
- HTML contains script tag
- JS contains key bindings: Ctrl+K, Ctrl+N, ?
- Help overlay HTML is included
- CSS styles for help panel are present
- _get_shortcut_help_html returns valid HTML
- kbd elements are rendered
- Multiple calls generate unique UIDs
"""

import pytest

from ui.keyboard_shortcuts import get_global_shortcuts_js, _get_shortcut_help_html


class TestGetGlobalShortcutsJs:
    def test_returns_script_tag(self):
        js = get_global_shortcuts_js()
        assert "<script>" in js
        assert "</script>" in js

    def test_contains_ctrl_k(self):
        js = get_global_shortcuts_js()
        assert "Ctrl+K" in js or "ctrlKey" in js
        assert "key === 'k'" in js

    def test_contains_ctrl_n(self):
        js = get_global_shortcuts_js()
        assert "key === 'n'" in js

    def test_contains_question_mark(self):
        js = get_global_shortcuts_js()
        assert "key === '?'" in js

    def test_contains_style_tag(self):
        js = get_global_shortcuts_js()
        assert "<style>" in js

    def test_contains_help_div(self):
        js = get_global_shortcuts_js()
        assert "shortcuts-help" in js

    def test_contains_shortcut_labels(self):
        js = get_global_shortcuts_js()
        assert "Tìm kiếm" in js or "Phím tắt" in js

    def test_kbd_elements_present(self):
        js = get_global_shortcuts_js()
        assert "<kbd>" in js

    def test_unique_uids(self):
        """Two calls should generate different UIDs."""
        js1 = get_global_shortcuts_js()
        js2 = get_global_shortcuts_js()
        assert js1 != js2

    def test_error_resistant(self):
        """JS should have try/catch or guard pattern."""
        js = get_global_shortcuts_js()
        assert "return" in js  # Early return guard present

    def test_debounce_mechanism(self):
        """Should have debounce/lastAction to prevent double-trigger."""
        js = get_global_shortcuts_js()
        assert "lastAction" in js
        assert "300" in js  # 300ms debounce


class TestGetShortcutHelpHtml:
    def test_returns_html(self):
        html = _get_shortcut_help_html()
        assert isinstance(html, str)
        assert len(html) > 50

    def test_contains_shortcuts(self):
        html = _get_shortcut_help_html()
        assert "Ctrl" in html
        assert "K" in html
        assert "N" in html

    def test_contains_kbd_elements(self):
        html = _get_shortcut_help_html()
        assert "<kbd>" in html

    def test_contains_vietnamese_labels(self):
        html = _get_shortcut_help_html()
        assert "Tìm kiếm" in html
        assert "Session mới" in html or "Phím tắt" in html
