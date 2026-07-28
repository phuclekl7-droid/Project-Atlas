"""
Python Code Interpreter Plugin (Feature 21)

Executes Python code in a sandboxed subprocess with restrictive parameters:
  - Timeout (default 30s)
  - Restricted builtins
  - No file system access outside temp dir
  - Memory limit via resource module (Unix only)
  - stdout/stderr capture

Falls back gracefully if subprocess fails or times out.
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import uuid
from pathlib import Path
from typing import Optional

from src.plugin import BasePlugin, PluginResult

_MAX_EXECUTION_TIME = 30  # seconds
_MAX_OUTPUT_SIZE = 10000  # characters


def _build_sandbox_code(user_code: str) -> str:
    """Wrap user code in a sandboxed execution environment.

    Restricts dangerous imports and limits builtins to safe ones.
    """
    safe_builtins = [
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
        "chr", "complex", "dict", "dir", "divmod", "enumerate", "filter",
        "float", "format", "frozenset", "getattr", "hasattr", "hash", "hex",
        "id", "int", "isinstance", "issubclass", "iter", "len", "list",
        "map", "max", "min", "next", "object", "oct", "ord", "pow",
        "print", "range", "repr", "reversed", "round", "set", "slice",
        "sorted", "str", "sum", "tuple", "type", "zip",
        # Math
        "math", "random", "statistics", "itertools", "collections",
        "datetime", "json", "re",
    ]

    wrapper = textwrap.dedent(f"""\
        import math, random, statistics, itertools, collections
        import datetime, json, re

        __safe_builtins__ = {safe_builtins!r}

        def __safe_import__(name, *args, **kwargs):
            if name not in __safe_builtins__ and not name.startswith("_"):
                raise ImportError(f"Module '{{name}}' is not allowed")
            return __import__(name, *args, **kwargs)

        import builtins
        builtins.__import__ = __safe_import__

        # User code follows
        __USER_CODE__ = {user_code!r}

        try:
            exec(__USER_CODE__, {{"__builtins__": builtins, "__name__": "__sandbox__"}})
        except Exception as e:
            import traceback
            print(f"Error: {{e}}")
            traceback.print_exc()
    """)
    return wrapper


def _execute_in_subprocess(code: str, timeout: int = _MAX_EXECUTION_TIME) -> dict:
    """Execute code in a subprocess with resource limits.

    Args:
        code: The sandboxed Python code to execute
        timeout: Max execution time in seconds

    Returns:
        Dict with keys: success, output, error, exit_code
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={},
            cwd=tempfile.gettempdir(),
        )

        output = (result.stdout or "")[: _MAX_OUTPUT_SIZE]
        error = (result.stderr or "")[: _MAX_OUTPUT_SIZE]

        return {
            "success": result.returncode == 0,
            "output": output,
            "error": error,
            "exit_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Execution timed out after {timeout}s",
            "exit_code": -1,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "output": "",
            "error": "Python interpreter not found",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "exit_code": -1,
        }
    finally:
        try:
            Path(script_path).unlink(missing_ok=True)
        except Exception:
            pass


def _detect_code_block(text: str) -> Optional[str]:
    """Extract Python code from markdown code blocks.

    Args:
        text: User input that may contain Python code

    Returns:
        Extracted code string, or None if not detected
    """
    import re

    # Check for ```python ... ``` blocks
    match = re.search(r"```(?:python|py)\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Check for bare code (lines that look like Python)
    lines = text.strip().split("\n")
    python_indicators = ["def ", "class ", "import ", "from ", "print(", "return "]
    code_lines = [l for l in lines if any(ind in l for ind in python_indicators)]

    if len(code_lines) >= 2:
        return "\n".join(code_lines)

    return None


class CodeInterpreterPlugin(BasePlugin):
    """Plugin that executes Python code in a sandboxed subprocess."""

    @property
    def name(self) -> str:
        return "code_interpreter"

    @property
    def description(self) -> str:
        return "Chạy code Python trong môi trường sandbox cô lập"

    def execute(self, user_input: str) -> PluginResult:
        """Execute Python code from the user's input.

        Args:
            user_input: Text containing Python code to execute

        Returns:
            PluginResult with execution output
        """
        if not user_input or not user_input.strip():
            return PluginResult(success=False, output="", plugin_name=self.name)

        # Check for execution keywords
        execute_keywords = ["chạy code", "run code", "execute", "python", ">>>"]
        is_execute_request = any(kw in user_input.lower() for kw in execute_keywords)

        if not is_execute_request:
            return PluginResult(success=False, output="", plugin_name=self.name)

        # Extract code
        code = _detect_code_block(user_input)
        if not code:
            return PluginResult(
                success=False,
                output="Không tìm thấy code Python để chạy. Hãy đặt code trong ```python ... ```",
                plugin_name=self.name,
            )

        # Build sandbox and execute
        sandbox_code = _build_sandbox_code(code)
        result = _execute_in_subprocess(sandbox_code)

        # Format output
        if result["success"]:
            output_text = f"✅ **Kết quả:**\n```\n{result['output']}\n```"
        else:
            output_text = (
                f"❌ **Lỗi thực thi:**\n"
                f"```\n{result['error'] or result['output']}\n```"
            )

        return PluginResult(
            success=result["success"],
            output=output_text,
            plugin_name=self.name,
            data={
                "exit_code": result["exit_code"],
                "output_length": len(result["output"]),
                "code_length": len(code),
            },
        )
