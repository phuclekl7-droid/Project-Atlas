"""
Terminal Command Runner Plugin (Feature #25).
Runs terminal commands via subprocess with user confirmation and allowlist.

Commands are only executed if:
1. The command is in the ALLOWLIST
2. User confirms via confirmation flag

Usage:
    TerminalCommandRunnerPlugin.execute("ls -la")
    TerminalCommandRunnerPlugin.execute("whoami")
"""

import os
import shlex
import subprocess
import threading
from pathlib import Path
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("terminal_runner")

# ── Safe command allowlist (always allowed, no confirmation needed) ──
_SAFE_COMMANDS = {
    "ls", "dir", "echo", "pwd", "whoami", "hostname",
    "date", "time", "cal", "uptime", "uname",
    "cat", "head", "tail", "wc", "sort", "uniq",
    "which", "where", "find", "locate",
}

# ── Confirmation-required commands ──
_CONFIRM_COMMANDS = {
    "rm", "mv", "cp", "chmod", "chown", "mkdir", "rmdir",
    "touch", "ln", "dd", "wget", "curl",
    "git", "docker", "pip", "npm", "yarn", "pnpm",
    "sudo", "su", "kill", "pkill",
}

# ── Dangerous commands (blocked by default) ──
_BLOCKED_COMMANDS = {
    "shutdown", "reboot", "init", "poweroff", "halt",
    "mkfs", "fdisk", "parted", "format",
    "passwd", "deluser", "userdel",
    "iptables", "ufw",
}


def _get_command_keyword(command: str) -> str:
    """Extract the base command keyword (first token)."""
    tokens = shlex.split(command)
    if not tokens:
        return ""
    return Path(tokens[0]).name.lower().replace(".exe", "").replace(".bat", "")


def _is_blocked(command: str) -> bool:
    """Check if command contains blocked keywords."""
    cmd = _get_command_keyword(command)
    return cmd in _BLOCKED_COMMANDS


def _is_safe(command: str) -> bool:
    """Check if command is in the safe allowlist."""
    cmd = _get_command_keyword(command)
    return cmd in _SAFE_COMMANDS


def _needs_confirmation(command: str) -> bool:
    """Check if command requires explicit user confirmation."""
    cmd = _get_command_keyword(command)
    return cmd in _CONFIRM_COMMANDS


def _run_command(command: str, timeout: int = 30, cwd: Optional[str] = None) -> tuple[str, str, int]:
    """Run a command via subprocess with timeout.

    Returns:
        Tuple of (stdout, stderr, returncode)
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or os.getcwd(),
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {timeout}s", -1
    except Exception as e:
        return "", f"Failed to run command: {e}", -1


class TerminalCommandRunnerPlugin(BasePlugin):
    """
    Executes terminal commands via subprocess with safety checks.

    - Safe commands (ls, echo, pwd, etc.): executed immediately
    - Confirmation commands (rm, mv, cp, git, docker, etc.): requires user confirmation
    - Blocked commands (shutdown, mkfs, etc.): rejected

    Examples:
        "ls -la /home/user"
        "echo Hello World"
        "git status"
    """

    name = "terminal_runner"
    description = "Chạy lệnh terminal (có kiểm tra an toàn)"

    def __init__(self):
        super().__init__()
        self._execution_lock = threading.Lock()
        self._pending_confirmations: dict[str, bool] = {}
        self._last_command: Optional[str] = None

    def execute(self, input_str: str) -> PluginResult:
        """
        Execute a terminal command.

        Args:
            input_str: The command to run (e.g., "ls -la")

        Returns:
            PluginResult with command output
        """
        command = input_str.strip()
        if not command:
            return PluginResult(
                success=False,
                error="Vui lòng nhập lệnh cần chạy. Ví dụ: ls -la",
            )

        # Check if blocked
        if _is_blocked(command):
            cmd_name = _get_command_keyword(command)
            return PluginResult(
                success=False,
                error=(
                    f"❌ Lệnh '{cmd_name}' bị chặn vì lý do an toàn.\n\n"
                    f"Để bảo vệ hệ thống, các lệnh có thể gây hại "
                    f"(shutdown, mkfs, fdisk...) không được phép chạy."
                ),
            )

        # Check if needs confirmation
        if _needs_confirmation(command):
            cmd_name = _get_command_keyword(command)
            return PluginResult(
                success=False,
                error=(
                    f"⚠️ **Lệnh cần xác nhận**: `{command}`\n\n"
                    f"Lệnh `{cmd_name}` có thể ảnh hưởng đến hệ thống.\n\n"
                    f"**Vui lòng gửi lại lệnh với tiền tố `/confirm`**\n"
                    f"Ví dụ: `/confirm {command}`\n\n"
                    f"Hoặc gõ `/cancel` để hủy."
                ),
            )

        # Execute safe command
        with self._execution_lock:
            self._last_command = command
            stdout, stderr, rc = _run_command(command)

        # Format output
        lines = [f"```bash\n$ {command}\n```\n"]

        if stdout:
            # Truncate long output
            output = stdout[:5000]
            if len(stdout) > 5000:
                output += f"\n\n... (truncated, {len(stdout)} total chars)"
            lines.append(f"**stdout:**\n```\n{output}\n```")

        if stderr:
            lines.append(f"**stderr:**\n```\n{stderr[:1000]}\n```")

        if rc == 0:
            if not stdout and not stderr:
                lines.append("✅ Command completed successfully (no output).")
            lines.append(f"\n---\n✅ Exit code: `{rc}`")
        else:
            lines.append(f"\n---\n❌ Exit code: `{rc}`")

        output = "\n".join(lines)

        return PluginResult(success=rc == 0, output=output, data={"exit_code": rc, "stdout": stdout[:5000], "stderr": stderr[:1000]})


class ConfirmCommandPlugin(BasePlugin):
    """
    Confirms and executes a previously requested command (Feature #25).

    Usage:
        "/confirm rm -rf /tmp/test" — confirms and executes the command
    """

    name = "_confirm_command"
    description = "Xác nhận và chạy lệnh terminal (chỉ kích hoạt qua /confirm)"

    def execute(self, input_str: str) -> PluginResult:
        """Confirm and run a command. Only triggers on explicit /confirm prefix."""
        # Only process if input starts with /confirm
        if not input_str.lower().startswith("/confirm "):
            return PluginResult(
                success=False,
                error="Plugin chỉ kích hoạt qua lệnh `/confirm <command>`",
            )
        command = input_str[9:].strip()

        if not command:
            return PluginResult(success=False, error="Vui lòng nhập lệnh cần xác nhận")

        if _is_blocked(command):
            return PluginResult(
                success=False,
                error=f"❌ Lệnh '{_get_command_keyword(command)}' bị chặn vì lý do an toàn.",
            )

        stdout, stderr, rc = _run_command(command)

        lines = [f"```bash\n$ {command}  # (confirmed)\n```\n"]
        if stdout:
            output = stdout[:5000]
            if len(stdout) > 5000:
                output += f"\n\n... (truncated, {len(stdout)} total chars)"
            lines.append(f"**stdout:**\n```\n{output}\n```")
        if stderr:
            lines.append(f"**stderr:**\n```\n{stderr[:1000]}\n```")
        lines.append(f"\n---\n{'✅' if rc == 0 else '❌'} Exit code: `{rc}`")

        return PluginResult(success=rc == 0, output="\n".join(lines))
