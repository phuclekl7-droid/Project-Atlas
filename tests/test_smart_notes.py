"""
Tests for Feature #93: Smart Note Manager (Obsidian Sync).
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.plugins.smart_notes import (
    SmartNotesPlugin,
    _create_note_file,
    _list_notes,
    _search_notes,
    _sanitize_filename,
    Note,
)


class TestSanitizeFilename:
    def test_sanitize_basic(self):
        name = _sanitize_filename("My Note Title")
        assert "My Note Title" in name

    def test_removes_invalid_chars(self):
        name = _sanitize_filename('test: file "name"')
        assert ":" not in name
        assert '"' not in name

    def test_empty_fallback(self):
        name = _sanitize_filename("")
        assert name == "untitled"


class TestCreateNoteFile:
    def test_create_note(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                note = _create_note_file("Test Title", "Test content here")
                assert note is not None
                assert note.title == "Test Title"
                assert Path(note.filepath).exists()

    def test_create_note_with_tags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                note = _create_note_file("Tagged", "Content", tags=["python", "test"])
                assert note is not None
                assert "python" in note.tags

    def test_create_duplicate_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                _create_note_file("Same", "Content 1")
                note2 = _create_note_file("Same", "Content 2")
                assert note2 is not None


class TestListNotes:
    def test_list_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                notes = _list_notes()
                assert notes == []

    def test_list_with_notes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                _create_note_file("Note 1", "Content 1")
                _create_note_file("Note 2", "Content 2")
                notes = _list_notes(limit=10)
                assert len(notes) == 2


class TestSearchNotes:
    def test_search_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                _create_note_file("Python Tips", "Use list comprehensions in Python")
                _create_note_file("Java Tips", "Use streams in Java")
                results = _search_notes("Python")
                assert len(results) >= 1

    def test_search_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                _create_note_file("Title", "Some content")
                results = _search_notes("nonexistent_keyword_xyz")
                assert results == []


class TestSmartNotesPlugin:
    def test_empty_input(self):
        plugin = SmartNotesPlugin()
        result = plugin.execute("")
        assert not result.success

    def test_list_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                plugin = SmartNotesPlugin()
                result = plugin.execute("list")
                assert result.success

    def test_create_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                plugin = SmartNotesPlugin()
                result = plugin.execute("create My Title: Content here")
                assert result.success
                assert "Note Created" in result.output or "Created" in result.output

    def test_create_missing_content(self):
        plugin = SmartNotesPlugin()
        result = plugin.execute("create Title Only")
        assert not result.success

    def test_path_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                plugin = SmartNotesPlugin()
                result = plugin.execute("path")
                assert result.success
                assert tmpdir in result.output

    def test_obsidian_no_vault(self):
        plugin = SmartNotesPlugin()
        with patch.dict(os.environ, {}, clear=True):
            result = plugin.execute("obsidian")
            assert not result.success

    def test_search_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                _create_note_file("Test Note", "This contains a keyword")
                plugin = SmartNotesPlugin()
                result = plugin.execute("search keyword")
                assert result.success

    def test_export_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ATLAS_NOTES_DIR": tmpdir}):
                plugin = SmartNotesPlugin()
                result = plugin.execute("export Meeting Notes: Notes from today")
                assert result.success
