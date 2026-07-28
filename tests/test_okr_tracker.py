"""
Tests for Feature #100: Personal OKR / Goal Tracker.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.plugins.okr_tracker import OKRTrackerPlugin


@pytest.fixture
def plugin(tmp_path):
    """Create an OKR tracker with a temp database."""
    db_path = str(tmp_path / "test_okr.db")
    with patch.dict(os.environ, {"OKR_DB_PATH": db_path}):
        p = OKRTrackerPlugin()
        yield p


class TestOKRTrackerPlugin:
    """Tests for the OKRTrackerPlugin class."""

    def test_empty_input(self, plugin):
        result = plugin.execute("")
        assert not result.success

    def test_add_objective(self, plugin):
        result = plugin.execute("add objective: Learn Python target:2026-12-31")
        assert result.success
        assert "Objective" in result.output

    def test_add_objective_without_target(self, plugin):
        result = plugin.execute("add objective: Build a nice project")
        assert result.success

    def test_add_objective_with_priority(self, plugin):
        result = plugin.execute("add objective: Deploy Atlas priority:high")
        assert result.success

    def test_add_objective_empty_title(self, plugin):
        result = plugin.execute("add objective:")
        assert not result.success

    def test_list_empty(self, plugin):
        result = plugin.execute("list")
        assert result.success
        assert "no objectives" in result.output.lower()

    def test_list_with_objectives(self, plugin):
        plugin.execute("add objective: Learn Python")
        plugin.execute("add objective: Build a project priority:high")
        result = plugin.execute("list")
        assert result.success
        assert "Learn Python" in result.output
        assert "Build a project" in result.output

    def test_list_by_status(self, plugin):
        plugin.execute("add objective: Active one")
        result = plugin.execute("list active")
        assert result.success

    def test_show_objective(self, plugin):
        plugin.execute("add objective: My Objective")
        result = plugin.execute("show 1")
        assert result.success
        assert "My Objective" in result.output

    def test_show_nonexistent(self, plugin):
        result = plugin.execute("show 999")
        assert not result.success

    def test_show_bad_format(self, plugin):
        result = plugin.execute("show abc")
        assert not result.success

    def test_update_progress(self, plugin):
        plugin.execute("add objective: Test Goal")
        result = plugin.execute("update 1 progress:50")
        assert result.success
        assert "50%" in result.output

    def test_update_nonexistent(self, plugin):
        result = plugin.execute("update 999 progress:50")
        assert not result.success

    def test_complete_objective(self, plugin):
        plugin.execute("add objective: Test Goal")
        result = plugin.execute("complete 1")
        assert result.success
        assert "completed" in result.output.lower()

    def test_add_key_result(self, plugin):
        plugin.execute("add objective: Learn Python")
        result = plugin.execute("add-kr 1: Complete 10 exercises")
        assert result.success

    def test_add_key_result_bad_format(self, plugin):
        result = plugin.execute("add-kr bad input")
        assert not result.success

    def test_delete_objective(self, plugin):
        plugin.execute("add objective: To Delete")
        result = plugin.execute("delete 1")
        assert result.success

    def test_generate_report(self, plugin):
        plugin.execute("add objective: Goal 1")
        plugin.execute("add objective: Goal 2")
        result = plugin.execute("report")
        assert result.success
        assert "OKR" in result.output
        assert "Goal 1" in result.output

    def test_unknown_command(self, plugin):
        result = plugin.execute("some random command")
        assert not result.success

    def test_add_with_description(self, plugin):
        result = plugin.execute("add objective: Master Python description:Complete tutorials target:2026-12-31")
        assert result.success
