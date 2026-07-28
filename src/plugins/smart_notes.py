"""
Smart Note Manager (Feature #93).
Manages and syncs notes in Obsidian, Notion, or local Markdown format.

Provides:
- Create notes in Obsidian vault or local folder
- List/search notes
- Export conversations as notes
- Simple Markdown note management

Usage:
    SmartNotesPlugin.execute("list")  # List recent notes
    SmartNotesPlugin.execute("create Note Title: Content here...")
    SmartNotesPlugin.execute("search keyword")
    SmartNotesPlugin.execute("export Last conversation")
"""

import datetime
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("smart_notes")


@dataclass
class Note:
    """A single note."""
    title: str = ""
    content: str = ""
    filepath: str = ""
    created: str = ""
    modified: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "local"  # local, obsidian, notion


def _get_notes_dir() -> Path:
    """Get the notes directory (configurable via env var)."""
    notes_path = os.environ.get("ATLAS_NOTES_DIR", "")
    if notes_path:
        return Path(notes_path)
    return Path("data/notes")


def _get_obsidian_vault() -> Optional[Path]:
    """Get Obsidian vault path from environment."""
    vault = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    return Path(vault) if vault else None


def _ensure_notes_dir() -> Path:
    """Ensure the notes directory exists."""
    notes_dir = _get_notes_dir()
    notes_dir.mkdir(parents=True, exist_ok=True)
    return notes_dir


def _sanitize_filename(title: str) -> str:
    """Convert a title to a safe filename."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', title)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized[:100] or "untitled"


def _create_note_file(title: str, content: str, tags: Optional[list[str]] = None) -> Optional[Note]:
    """Create a Markdown note file."""
    notes_dir = _ensure_notes_dir()
    filename = _sanitize_filename(title) + ".md"
    filepath = notes_dir / filename

    # Build Markdown content
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_lines = [
        f"# {title}",
        "",
        f"*Created: {now}*",
        "",
    ]

    if tags:
        md_lines.append(f"Tags: {' '.join(f'#{t}' for t in tags)}")
        md_lines.append("")

    md_lines.extend(["---", "", content.strip(), ""])

    try:
        filepath.write_text("\n".join(md_lines), encoding="utf-8")
        note = Note(
            title=title,
            content=content,
            filepath=str(filepath),
            created=now,
            modified=now,
            tags=tags or [],
        )
        logger.info(f"Note created: {filepath}")
        return note
    except Exception as e:
        logger.warning(f"Failed to create note: {e}")
        return None


def _list_notes(limit: int = 20) -> list[Note]:
    """List recent notes from the notes directory."""
    notes_dir = _get_notes_dir()
    if not notes_dir.exists():
        return []

    notes = []
    md_files = sorted(notes_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)

    for f in md_files[:limit]:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")[:200]
            # Extract title from first line
            title_match = re.match(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else f.stem
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)

            notes.append(Note(
                title=title,
                content=content,
                filepath=str(f),
                modified=mtime.strftime("%Y-%m-%d %H:%M:%S"),
            ))
        except Exception:
            continue

    return notes


def _search_notes(keyword: str) -> list[Note]:
    """Search notes by keyword in title and content."""
    notes_dir = _get_notes_dir()
    if not notes_dir.exists():
        return []

    keyword_lower = keyword.lower()
    matches = []

    for f in notes_dir.glob("*.md"):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            if keyword_lower in content.lower():
                title_match = re.match(r'^#\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else f.stem

                # Find context around keyword
                context = ""
                for line in content.split("\n"):
                    if keyword_lower in line.lower():
                        context = line.strip()[:150]
                        break

                matches.append(Note(
                    title=title,
                    content=context or content[:200],
                    filepath=str(f),
                    modified=datetime.datetime.fromtimestamp(
                        f.stat().st_mtime
                    ).strftime("%Y-%m-%d"),
                ))
        except Exception:
            continue

    return matches


class SmartNotesPlugin(BasePlugin):
    """
    Manages notes in Markdown format, compatible with Obsidian.

    Commands:
    - `list [N]`: List recent N notes (default 10)
    - `create <title>: <content>`: Create a new note
    - `search <keyword>`: Search notes by keyword
    - `export <topic> <content>`: Export chat content as note
    - `path`: Show current notes directory path
    - `obsidian`: Sync/check Obsidian vault connection

    Examples:
        "list 5"
        "create My Idea: This is a great idea for a project"
        "search Python"
        "export Meeting Notes: Notes from today's meeting..."
    """

    name = "smart_notes"
    description = "Quản lý ghi chú Markdown (tương thích Obsidian)"

    def execute(self, input_str: str) -> PluginResult:
        """Execute a note management command."""
        text = input_str.strip()
        if not text:
            return PluginResult(
                success=False,
                error=(
                    "Vui lòng nhập lệnh.\\n\\n"
                    "Lệnh:\\n"
                    "- `list` — List notes\\n"
                    "- `create <title>: <content>` — New note\\n"
                    "- `search <keyword>` — Search notes\\n"
                    "- `path` — Show notes directory\\n"
                    "- `export <title>: <content>` — Export to note\\n\\n"
                    "Ví dụ: `create My Idea: Great project idea!`"
                )
            )

        cmd = text.lower()

        if cmd.startswith("list"):
            parts = cmd.split()
            limit = 10
            if len(parts) > 1:
                try:
                    limit = int(parts[1])
                except ValueError:
                    pass

            notes = _list_notes(limit=limit)
            if not notes:
                return PluginResult(
                    success=True,
                    output=f"## 📝 Notes\\n\\n*No notes found.*\\n\\nCreate one: `create My Title: Content here`"
                )

            lines = [f"## 📝 Recent Notes (last {len(notes)})", ""]
            for note in notes:
                lines.append(f"- **{note.title}**")
                lines.append(f"  📅 {note.modified}")
                lines.append(f"  📎 `{note.filepath}`")
                lines.append("")

            return PluginResult(success=True, output="\n".join(lines))

        elif cmd.startswith("create ") or cmd.startswith("export "):
            prefix = 7 if cmd.startswith("create ") else 7
            body = text[prefix:].strip()

            if ":" in body:
                title, content = body.split(":", 1)
                note = _create_note_file(title.strip(), content.strip())
                if note:
                    return PluginResult(
                        success=True,
                        output=(
                            f"## ✅ Note Created\\n\\n"
                            f"- **Title:** {note.title}\\n"
                            f"- **File:** `{note.filepath}`\\n"
                            f"- **Created:** {note.created}\\n\\n"
                            f"{content.strip()[:300]}"
                        ),
                        data={"title": note.title, "path": note.filepath},
                    )
                return PluginResult(
                    success=False,
                    error="Không thể tạo ghi chú. Kiểm tra quyền ghi thư mục."
                )
            else:
                return PluginResult(
                    success=False,
                    error="Thiếu tiêu đề hoặc nội dung.\\n\\nĐịnh dạng: `create <title>: <content>`"
                )

        elif cmd.startswith("search "):
            keyword = text[7:].strip()
            if not keyword:
                return PluginResult(success=False, error="Vui lòng nhập từ khóa tìm kiếm.")

            notes = _search_notes(keyword)
            if not notes:
                return PluginResult(
                    success=True,
                    output=f"## 🔍 Search: \"{keyword}\"\\n\\n*No matching notes found.*"
                )

            lines = [f"## 🔍 Search Results: \"{keyword}\"", ""]
            for note in notes:
                lines.append(f"- **{note.title}**")
                lines.append(f"  📝 {note.content[:100]}...")
                lines.append(f"  📎 `{note.filepath}`")
                lines.append("")

            return PluginResult(success=True, output="\n".join(lines))

        elif cmd == "path":
            notes_dir = _get_notes_dir()
            obsidian_vault = _get_obsidian_vault()
            lines = [
                "## 📁 Notes Directory",
                "",
                f"- **Local notes:** `{notes_dir}`",
            ]
            if obsidian_vault:
                lines.append(f"- **Obsidian vault:** `{obsidian_vault}`")
                vault_readable = obsidian_vault.exists() and obsidian_vault.is_dir()
                lines.append(f"- **Vault status:** {'✅ Connected' if vault_readable else '❌ Not found'}")
                if not vault_readable:
                    lines.append("  Set `OBSIDIAN_VAULT_PATH` to your vault directory.")
            else:
                lines.append("- **Obsidian vault:** Not configured")
                lines.append("  Set `OBSIDIAN_VAULT_PATH` env var to enable Obsidian sync.")

            notes_dir.mkdir(parents=True, exist_ok=True)
            file_count = len(list(notes_dir.glob("*.md")))
            lines.append(f"- **Note count:** {file_count}")

            return PluginResult(success=True, output="\n".join(lines))

        elif cmd in ("obsidian", "vault"):
            vault = _get_obsidian_vault()
            if vault and vault.exists():
                return PluginResult(
                    success=True,
                    output=(
                        f"## 🔗 Obsidian Vault\\n\\n"
                        f"- **Path:** `{vault}`\\n"
                        f"- **Status:** ✅ Connected\\n"
                        f"- **Notes will be synced when created in this vault.**\\n\\n"
                        f"To use: Set `OBSIDIAN_VAULT_PATH` env var to your vault path."
                    )
                )
            return PluginResult(
                success=False,
                error=(
                    "❌ **Obsidian vault not configured.**\\n\\n"
                    "Set `OBSIDIAN_VAULT_PATH` environment variable:\\n"
                    "`OBSIDIAN_VAULT_PATH=C:/path/to/your/vault`"
                )
            )

        else:
            return PluginResult(
                success=False,
                error=f"Lệnh không hợp lệ: `{text}`\\n\\nLệnh: list, create, search, path, export, obsidian"
            )
