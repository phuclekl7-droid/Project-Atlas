"""
Unit tests for Python Code Interpreter Plugin.

Tests:
- Code block detection from markdown
- Sandbox code wrapper construction
- Subprocess execution (mocked)
- Plugin execution flow
- Error handling (timeout, no code, non-Python input)
- Plugin metadata
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.plugin import BasePlugin, PluginResult
from src.plugins.code_interpreter import (
    CodeInterpreterPlugin,
    _build_sandbox_code,
    _detect_code_block,
    _execute_in_subprocess,
)


# ============================================================
# Plugin Metadata Tests
# ============================================================


class TestCodeInterpreterMetadata:
    def test_plugin_name(self):
        plugin = CodeInterpreterPlugin()
        assert plugin.name == "code_interpreter"

    def test_plugin_description(self):
        plugin = CodeInterpreterPlugin()
        assert plugin.description is not None
        assert len(plugin.description) > 0
        assert "python" in plugin.description.lower() or "code" in plugin.description.lower()

    def test_is_baseplugin_subclass(self):
        assert issubclass(CodeInterpreterPlugin, BasePlugin)


# ============================================================
# Code Block Detection Tests
# ============================================================


class TestDetectCodeBlock:
    def test_python_fence(self):
        """```python ... ``` should be detected."""
        code = _detect_code_block("```python\nprint('hello')\nprint('world')\n```")
        assert code is not None
        assert "print('hello')" in code
        assert "print('world')" in code

    def test_py_fence(self):
        """```py ... ``` should be detected."""
        code = _detect_code_block("```py\nx = 1 + 2\nprint(x)\n```")
        assert code is not None
        assert "x = 1 + 2" in code

    def test_bare_code_lines(self):
        """Lines with Python indicators should be detected."""
        code = _detect_code_block("def hello():\n    print('hi')\n\nhello()")
        assert code is not None
        assert "def hello()" in code

    def test_no_code(self):
        """Plain text without Python should return None."""
        code = _detect_code_block("Hello, how are you today?")
        assert code is None

    def test_empty_text(self):
        """Empty string should return None."""
        code = _detect_code_block("")
        assert code is None

    def test_single_indicator_line(self):
        """Only one line with Python indicator should not match."""
        code = _detect_code_block("print('hello')")
        assert code is None  # Needs 2+ lines with indicators

    def test_fence_without_language(self):
        """``` without language tag should still be checked."""
        code = _detect_code_block("```\nprint('hello')\n```")
        assert code is None  # No python/py tag, won't match


# ============================================================
# Sandbox Code Builder Tests
# ============================================================


class TestBuildSandboxCode:
    def test_includes_user_code(self):
        """User code should be embedded in the sandbox wrapper."""
        sandbox = _build_sandbox_code("print(42)")
        assert "print(42)" in sandbox

    def test_includes_safe_builtins(self):
        """Safe builtins list should be included."""
        sandbox = _build_sandbox_code("x = 1")
        assert "safe_builtins" in sandbox
        assert "math" in sandbox
        assert "json" in sandbox

    def test_sandbox_has_exec_call(self):
        """Sandbox should execute user code via exec()."""
        sandbox = _build_sandbox_code("x = 1")
        assert "exec" in sandbox
        assert "__sandbox__" in sandbox


# ============================================================
# Subprocess Execution Tests (mocked)
# ============================================================


class TestExecuteInSubprocess:
    @pytest.fixture
    def mock_success_result(self):
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = "Hello, world!\n"
        mock.stderr = ""
        return mock

    @pytest.fixture
    def mock_error_result(self):
        mock = MagicMock()
        mock.returncode = 1
        mock.stdout = ""
        mock.stderr = "NameError: name 'x' is not defined\n"
        return mock

    def test_successful_execution(self, mock_success_result):
        with patch("src.plugins.code_interpreter.subprocess.run", return_value=mock_success_result):
            result = _execute_in_subprocess("print('Hello, world!')")

        assert result["success"] is True
        assert "Hello" in result["output"]
        assert result["exit_code"] == 0

    def test_error_execution(self, mock_error_result):
        with patch("src.plugins.code_interpreter.subprocess.run", return_value=mock_error_result):
            result = _execute_in_subprocess("print(undefined_var)")

        assert result["success"] is False
        assert "NameError" in result["error"]
        assert result["exit_code"] == 1

    def test_timeout(self):
        with patch(
            "src.plugins.code_interpreter.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="python", timeout=30),
        ):
            result = _execute_in_subprocess("import time; time.sleep(999)")

        assert result["success"] is False
        assert "timed out" in result["error"].lower()
        assert result["exit_code"] == -1

    def test_file_not_found(self):
        with patch(
            "src.plugins.code_interpreter.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = _execute_in_subprocess("print('hi')")

        assert result["success"] is False
        assert result["exit_code"] == -1


# ============================================================
# Plugin Execution Tests
# ============================================================


class TestCodeInterpreterExecute:
    def test_empty_input(self):
        plugin = CodeInterpreterPlugin()
        result = plugin.execute("")
        assert result.success is False

    def test_non_code_input(self):
        """Plain text without execution keywords should pass through."""
        plugin = CodeInterpreterPlugin()
        result = plugin.execute("Hello, what's the weather like?")
        assert result.success is False  # No execution keyword match

    def test_code_without_block(self):
        """'run code' keyword but without code block."""
        plugin = CodeInterpreterPlugin()
        result = plugin.execute("chạy code")
        assert result.success is False
        assert "```" in result.output or "code" in result.output.lower()

    def test_successful_execution(self):
        """Full flow with mocked subprocess."""
        plugin = CodeInterpreterPlugin()
        mock_subprocess_result = MagicMock()
        mock_subprocess_result.returncode = 0
        mock_subprocess_result.stdout = "42\n"
        mock_subprocess_result.stderr = ""

        with patch("src.plugins.code_interpreter.subprocess.run", return_value=mock_subprocess_result):
            result = plugin.execute("chạy code ```python\nprint(42)\n```")

        assert result.success is True
        assert "42" in result.output


# ============================================================
# Data Structure Tests
# ============================================================


class TestCodeInterpreterData:
    def test_success_data_contains_exit_code(self):
        """Successful result should include exit_code in data."""
        plugin = CodeInterpreterPlugin()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok\n"
        mock_result.stderr = ""

        with patch("src.plugins.code_interpreter.subprocess.run", return_value=mock_result):
            result = plugin.execute("chạy code ```python\nprint('ok')\n```")

        assert result.data is not None
        assert "exit_code" in result.data
        assert result.data["exit_code"] == 0
        assert "output_length" in result.data
        assert "code_length" in result.data


# ============================================================
# Execution Keyword Detection Tests
# ============================================================


class TestExecutionKeywords:
    def test_vietnamese_keyword(self):
        """'chạy code' should trigger execution."""
        plugin = CodeInterpreterPlugin()
        with patch("src.plugins.code_interpreter._detect_code_block", return_value="print('hi')"):
            with patch("src.plugins.code_interpreter._execute_in_subprocess") as mock_exec:
                mock_exec.return_value = {"success": True, "output": "hi\n", "error": "", "exit_code": 0}
                result = plugin.execute("chạy code ```python\nprint('hi')\n```")
        assert result.success is True

    def test_english_keyword(self):
        """'run code' should trigger execution."""
        plugin = CodeInterpreterPlugin()
        with patch("src.plugins.code_interpreter._detect_code_block", return_value="print('hi')"):
            with patch("src.plugins.code_interpreter._execute_in_subprocess") as mock_exec:
                mock_exec.return_value = {"success": True, "output": "hi\n", "error": "", "exit_code": 0}
                result = plugin.execute("run code ```python\nprint('hi')\n```")
        assert result.success is True

    def test_python_keyword(self):
        """'python' keyword should trigger."""
        plugin = CodeInterpreterPlugin()
        with patch("src.plugins.code_interpreter._detect_code_block", return_value="print('hi')"):
            with patch("src.plugins.code_interpreter._execute_in_subprocess") as mock_exec:
                mock_exec.return_value = {"success": True, "output": "hi\n", "error": "", "exit_code": 0}
                result = plugin.execute("python code ```python\nprint('hi')\n```")
        assert result.success is True
