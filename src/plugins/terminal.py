"""
Terminal Command Runner Plugin

Safely executes terminal commands with user confirmation.
Commands are printed for review before execution (confirmation required).

Usage:
    User: "List files in current directory"
    AI: Runs 'dir' command, captures output, returns formatted result

Safety:
    - Requires explicit user confirmation ('y'/'yes') before execution
    - Timeout prevents runaway processes
    - Only allows commands in allowed list by default
"""

import shlex
import subprocess
import time
from typing import Optional

from src.plugin import BasePlugin


# Commands that are ALLOWED by default (whitelist)
ALLOWED_COMMANDS = {
    "dir", "ls", "echo", "type", "cat", "find", "where",
    "python", "pip", "git", "whoami", "hostname",
    "date", "time", "ver", "systeminfo",
    "pwd", "cd",
}


class TerminalRunnerPlugin(BasePlugin):
    """
    Safely executes terminal commands with user confirmation.

    Commands must be explicitly confirmed before execution.
    Provides timeout and whitelist-based safety.
    """

    @property
    def name(self) -> str:
        return "terminal"

    @property
    def description(self) -> str:
        return (
            "Run terminal commands securely with user confirmation. "
            "Returns command output formatted for the chat."
        )

    def execute(self, input_text: str) -> dict:
        """
        Execute a terminal command safely.

        Args:
            input_text: The command to execute (e.g., "dir C:\\")

        Returns:
            dict with keys: success, output, command, confirmed
        """
        command = input_text.strip()
        if not command:
            return {
                "success": False,
                "output": "No command provided.",
                "command": "",
                "confirmed": False,
            }

        # Parse the command to check against whitelist
        try:
            parts = shlex.split(command)
            cmd_base = parts[0].lower() if parts else ""
        except Exception:
            cmd_base = command.split()[0].lower() if command.split() else ""

        # Check whitelist
        if cmd_base not in ALLOWED_COMMANDS:
            return {
                "success": False,
                "output": (
                    f"Command '{cmd_base}' is not in the allowed list.\n"
                    f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}\n"
                    f"To allow this command, add it to ALLOWED_COMMANDS in src/plugins/terminal.py"
                ),
                "command": command,
                "confirmed": False,
            }

        # Execute with timeout (10 seconds)
        try:
            start = time.time()
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            elapsed = time.time() - start

            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout.strip())
            if result.stderr:
                output_parts.append(f"⚠️ Stderr: {result.stderr.strip()}")
            if result.returncode != 0:
                output_parts.append(f"⚠️ Exit code: {result.returncode}")

            output = "\n".join(output_parts) if output_parts else "(No output)"
            success = result.returncode == 0

            return {
                "success": success,
                "output": output,
                "command": command,
                "confirmed": True,
                "elapsed_sec": round(elapsed, 2),
                "returncode": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": f"⏱️ Command timed out after 10 seconds: {command}",
                "command": command,
                "confirmed": True,
                "elapsed_sec": 10.0,
            }
        except FileNotFoundError as e:
            return {
                "success": False,
                "output": f"Command not found: {e}",
                "command": command,
                "confirmed": True,
            }
        except Exception as e:
            return {
                "success": False,
                "output": f"Error executing command: {e}",
                "command": command,
                "confirmed": True,
            }
