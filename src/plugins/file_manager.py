"""
File System Manager Plugin (Feature 24)

Allows the AI to read, write, and list files within a configurable allowed directory.
Uses path traversal prevention and allows only text-based file operations.

Commands:
- /read <path> — Read file content
- /write <path> <content> — Write content to file
- /list <path> — List directory contents
- /info <path> — Get file info (size, modified, type)
"""

import os
import stat
import time
from pathlib import Path
from typing import Optional

from src.plugin import BasePlugin, PluginResult


# Default allowed directory for file operations
_DEFAULT_ALLOWED_DIR = os.path.join(os.path.expanduser("~"), "atlas_files")


def _resolve_safe_path(requested_path: str, allowed_dir: str) -> Optional[Path]:
    """Resolve a requested path relative to the allowed directory.

    Prevents path traversal attacks by resolving symlinks and checking
    that the final path starts with the allowed directory.

    Args:
        requested_path: User-requested path (absolute or relative)
        allowed_dir: Root directory for file operations

    Returns:
        Resolved Path if safe, None if path traversal detected
    """
    allowed = Path(allowed_dir).resolve()

    # If the requested path is absolute, check if it's within allowed dir
    if os.path.isabs(requested_path):
        target = Path(requested_path).resolve()
    else:
        target = (allowed / requested_path).resolve()

    # Ensure the target is within the allowed directory
    try:
        target.relative_to(allowed)
        return target
    except ValueError:
        return None


def _is_text_file(filepath: Path) -> bool:
    """Check if a file is likely a text file (not binary).

    Reads the first 1024 bytes and checks for null bytes or
    high ratio of non-printable characters.
    """
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(1024)
        # Check for null bytes (binary indicator)
        if b"\x00" in chunk:
            return False
        # Check proportion of printable characters
        printable = sum(32 <= b <= 126 or b in (9, 10, 13) for b in chunk)
        if len(chunk) > 0 and (printable / len(chunk)) < 0.7:
            return False
        return True
    except Exception:
        return False


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


class FileManagerPlugin(BasePlugin):
    """Plugin for secure file system operations within an allowed directory."""

    def __init__(self, allowed_dir: Optional[str] = None):
        """Initialize with an optional custom allowed directory.

        Args:
            allowed_dir: Root directory for file operations.
                         Defaults to ~/atlas_files.
        """
        self._allowed_dir = allowed_dir or _DEFAULT_ALLOWED_DIR
        # Create the allowed directory if it doesn't exist
        Path(self._allowed_dir).mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "file_manager"

    @property
    def description(self) -> str:
        return "Đọc/viết/quản lý file trong thư mục cho phép (an toàn)"

    @property
    def allowed_dir(self) -> str:
        return self._allowed_dir

    def execute(self, user_input: str) -> PluginResult:
        """Execute file system command.

        Supported commands (case-insensitive):
          /read <path>       — Read text file
          /write <path> ...   — Write text content to file (creates/overwrites)
          /list <path>       — List directory contents
          /info <path>       — Display file metadata
          /mkdir <path>      — Create directory

        Args:
            user_input: Command string starting with /read, /write, /list, /info, or /mkdir

        Returns:
            PluginResult with operation output
        """
        if not user_input or not user_input.strip():
            return PluginResult(success=False, output="", plugin_name=self.name)

        text = user_input.strip()
        parts = text.split(maxsplit=1)

        if len(parts) < 1:
            return PluginResult(success=False, output="", plugin_name=self.name)

        command = parts[0].lower()

        # Check if the input looks like a file command
        if command not in ("/read", "/write", "/list", "/info", "/mkdir"):
            return PluginResult(success=False, output="", plugin_name=self.name)

        # All file commands need at least a path
        if len(parts) < 2 and command != "/list":
            return PluginResult(
                success=False,
                output=f"Sử dụng: {command} <đường_dẫn> [nội_dung]",
                plugin_name=self.name,
            )

        if command == "/read":
            return self._cmd_read(parts[1])
        elif command == "/write":
            # Parse path and content from the remaining text
            # Format: /write <path> <content>
            # Split on first space to separate path and content
            write_parts = parts[1].split(maxsplit=1)
            if len(write_parts) < 2:
                return PluginResult(
                    success=False,
                    output="Sử dụng: /write <đường_dẫn> <nội_dung>",
                    plugin_name=self.name,
                )
            return self._cmd_write(write_parts[0], write_parts[1])
        elif command == "/list":
            path = parts[1] if len(parts) > 1 else "."
            return self._cmd_list(path)
        elif command == "/info":
            return self._cmd_info(parts[1])
        elif command == "/mkdir":
            return self._cmd_mkdir(parts[1])
        else:
            return PluginResult(success=False, output="", plugin_name=self.name)

    # ── Command Handlers ──

    def _cmd_read(self, path_str: str) -> PluginResult:
        """Read and display a text file."""
        target = _resolve_safe_path(path_str.strip(), self._allowed_dir)
        if target is None:
            return PluginResult(
                success=False,
                output=f"❌ Đường dẫn không hợp lệ hoặc nằm ngoài thư mục cho phép: `{self._allowed_dir}`",
                plugin_name=self.name,
            )

        if not target.exists():
            return PluginResult(
                success=False,
                output=f"❌ File không tồn tại: `{target}`",
                plugin_name=self.name,
            )

        if not target.is_file():
            return PluginResult(
                success=False,
                output=f"❌ `{target}` không phải là file",
                plugin_name=self.name,
            )

        if not _is_text_file(target):
            return PluginResult(
                success=False,
                output=f"❌ `{target.name}` không phải file văn bản hoặc chứa dữ liệu nhị phân",
                plugin_name=self.name,
            )

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            # Limit output size
            if len(content) > 5000:
                content = content[:5000] + "\n\n... [truncated, file too large]"
            return PluginResult(
                success=True,
                output=f"📄 **{target.name}** ({_format_size(target.stat().st_size)})\n```\n{content}\n```",
                plugin_name=self.name,
                data={
                    "path": str(target),
                    "size": target.stat().st_size,
                    "lines": content.count("\n") + 1,
                },
            )
        except Exception as e:
            return PluginResult(
                success=False,
                output=f"❌ Lỗi đọc file: {e}",
                plugin_name=self.name,
            )

    def _cmd_write(self, path_str: str, content: str) -> PluginResult:
        """Write text content to a file (creates or overwrites)."""
        target = _resolve_safe_path(path_str.strip(), self._allowed_dir)
        if target is None:
            return PluginResult(
                success=False,
                output=f"❌ Đường dẫn không hợp lệ hoặc nằm ngoài thư mục cho phép",
                plugin_name=self.name,
            )

        # Create parent directories if needed
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return PluginResult(
                success=False,
                output=f"❌ Không thể tạo thư mục: {e}",
                plugin_name=self.name,
            )

        try:
            target.write_text(content, encoding="utf-8")
            return PluginResult(
                success=True,
                output=f"✅ Đã ghi {len(content)} ký tự vào `{target.relative_to(Path(self._allowed_dir))}`",
                plugin_name=self.name,
                data={
                    "path": str(target),
                    "size": len(content),
                },
            )
        except Exception as e:
            return PluginResult(
                success=False,
                output=f"❌ Lỗi ghi file: {e}",
                plugin_name=self.name,
            )

    def _cmd_list(self, path_str: str) -> PluginResult:
        """List directory contents."""
        target = _resolve_safe_path(path_str.strip() or ".", self._allowed_dir)
        if target is None:
            return PluginResult(
                success=False,
                output=f"❌ Đường dẫn không hợp lệ hoặc nằm ngoài thư mục cho phép",
                plugin_name=self.name,
            )

        if not target.exists():
            return PluginResult(
                success=False,
                output=f"❌ Đường dẫn không tồn tại: `{target}`",
                plugin_name=self.name,
            )

        if not target.is_dir():
            return PluginResult(
                success=False,
                output=f"❌ `{target}` không phải là thư mục",
                plugin_name=self.name,
            )

        try:
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            lines = [f"📁 **{target.name}/**"]
            lines.append("")
            lines.append(f"| {'Name':<40} | {'Size':<8} | {'Type':<10} |")
            lines.append(f"| {'-'*40}:|{'-'*8}:|{'-'*10}:|")

            for entry in entries[:50]:  # Limit to 50 entries
                name = entry.name + "/" if entry.is_dir() else entry.name
                size = _format_size(entry.stat().st_size) if entry.is_file() else "-"
                etype = "📁 dir" if entry.is_dir() else "📄 file"
                lines.append(f"| {name:<40} | {size:<8} | {etype:<10} |")

            if len(entries) > 50:
                lines.append(f"\n... và {len(entries) - 50} mục khác")

            return PluginResult(
                success=True,
                output="\n".join(lines),
                plugin_name=self.name,
                data={
                    "path": str(target),
                    "entry_count": len(entries),
                },
            )
        except Exception as e:
            return PluginResult(
                success=False,
                output=f"❌ Lỗi liệt kê: {e}",
                plugin_name=self.name,
            )

    def _cmd_info(self, path_str: str) -> PluginResult:
        """Display file metadata."""
        target = _resolve_safe_path(path_str.strip(), self._allowed_dir)
        if target is None:
            return PluginResult(
                success=False,
                output=f"❌ Đường dẫn không hợp lệ hoặc nằm ngoài thư mục cho phép",
                plugin_name=self.name,
            )

        if not target.exists():
            return PluginResult(
                success=False,
                output=f"❌ File/folder không tồn tại: `{target}`",
                plugin_name=self.name,
            )

        try:
            st = target.stat()
            info_lines = [
                f"📋 **Thông tin:** `{target.name}`",
                f"",
                f"- **Đường dẫn đầy đủ:** `{target.resolve()}`",
                f"- **Loại:** {'📁 Thư mục' if target.is_dir() else '📄 File văn bản' if _is_text_file(target) else '📦 File nhị phân'}",
                f"- **Kích thước:** {_format_size(st.st_size)}",
                f"- **Lần sửa cuối:** {time.ctime(st.st_mtime)}",
                f"- **Lần truy cập cuối:** {time.ctime(st.st_atime)}",
            ]

            if target.is_file():
                permissions = stat.filemode(st.st_mode)
                info_lines.append(f"- **Quyền:** {permissions}")
                info_lines.append(f"- **Dòng:** {target.read_text(encoding='utf-8', errors='replace').count('\\n') + 1}")

            return PluginResult(
                success=True,
                output="\n".join(info_lines),
                plugin_name=self.name,
            )
        except Exception as e:
            return PluginResult(
                success=False,
                output=f"❌ Lỗi đọc thông tin: {e}",
                plugin_name=self.name,
            )

    def _cmd_mkdir(self, path_str: str) -> PluginResult:
        """Create a new directory."""
        target = _resolve_safe_path(path_str.strip(), self._allowed_dir)
        if target is None:
            return PluginResult(
                success=False,
                output=f"❌ Đường dẫn không hợp lệ hoặc nằm ngoài thư mục cho phép",
                plugin_name=self.name,
            )

        if target.exists():
            return PluginResult(
                success=False,
                output=f"❌ `{target.relative_to(Path(self._allowed_dir))}` đã tồn tại",
                plugin_name=self.name,
            )

        try:
            target.mkdir(parents=True, exist_ok=True)
            return PluginResult(
                success=True,
                output=f"✅ Đã tạo thư mục `{target.relative_to(Path(self._allowed_dir))}/`",
                plugin_name=self.name,
            )
        except Exception as e:
            return PluginResult(
                success=False,
                output=f"❌ Lỗi tạo thư mục: {e}",
                plugin_name=self.name,
            )
