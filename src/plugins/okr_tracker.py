"""
Personal OKR / Goal Tracker (Feature #100).
Tracks personal Objectives and Key Results with SQLite storage.

Supports:
- Multiple objectives with key results
- Progress tracking (0-100%)
- Due dates and priority levels
- Status: draft, active, completed, cancelled
- Weekly check-in reminders
- Export to markdown report

Usage:
    OKRTrackerPlugin.execute("add objective: Learn Python target:2026-12-31")
    OKRTrackerPlugin.execute("list")
    OKRTrackerPlugin.execute("update 1 progress:50")
    OKRTrackerPlugin.execute("report")
"""

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("okr_tracker")

DEFAULT_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "okr.db")


@dataclass
class Objective:
    """A personal objective with key results."""
    id: int = 0
    title: str = ""
    description: str = ""
    priority: str = "medium"  # high, medium, low
    status: str = "active"  # draft, active, completed, cancelled
    progress: int = 0  # 0-100%
    due_date: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    key_results: list = field(default_factory=list)


@dataclass
class KeyResult:
    """A measurable key result under an objective."""
    id: int = 0
    objective_id: int = 0
    title: str = ""
    progress: int = 0  # 0-100%
    notes: str = ""


def _init_db(db_path: str) -> None:
    """Initialize the OKR database tables."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS objectives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'active',
                    progress INTEGER DEFAULT 0,
                    due_date TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS key_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    objective_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    notes TEXT DEFAULT '',
                    FOREIGN KEY (objective_id) REFERENCES objectives(id) ON DELETE CASCADE
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to init OKR DB: {e}")


def _execute_db(db_path: str, query: str, params: tuple = ()) -> Optional[list]:
    """Execute a database query with context manager."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(query, params)
            conn.commit()
            rows = cur.fetchall()
            return [dict(r) for r in rows] if rows else []
    except Exception as e:
        logger.error(f"DB error: {e}")
        return None


class OKRTrackerPlugin(BasePlugin):
    """
    Tracks personal Objectives and Key Results.

    Commands:
    - "add objective: <title> [description:...] [target:YYYY-MM-DD] [priority:high/medium/low]"
    - "list" or "list [all|active|completed]"
    - "show <id>": Show objective details with key results
    - "update <id> progress:<0-100>"
    - "add-kr <objective_id>: <key result title>"
    - "complete <id>": Mark objective as completed
    - "delete <id>"
    - "report": Generate a markdown status report

    Examples:
        "add objective: Learn Python description:Master Python basics target:2026-12-31"
        "add objective: Build a personal project priority:high"
        "add-kr 1: Complete 10 Python exercises"
        "update 1 progress:50"
        "report"
    """

    name = "okr_tracker"
    description = "Quản lý mục tiêu cá nhân (OKRs)"

    def __init__(self):
        super().__init__()
        self._db_path = os.environ.get("OKR_DB_PATH", DEFAULT_DB_PATH)
        _init_db(self._db_path)

    def execute(self, input_str: str) -> PluginResult:
        """Execute an OKR command."""
        text = input_str.strip()
        if not text:
            return PluginResult(
                success=False,
                error=(
                    "Vui lòng nhập lệnh OKR.\n\n"
                    "Ví dụ:\n"
                    "- `add objective: Học Python target:2026-12-31`\n"
                    "- `list` — Xem danh sách\n"
                    "- `report` — Báo cáo chi tiết\n"
                    "- `update 1 progress:50`"
                )
            )

        cmd = text.lower()

        if cmd.startswith("add objective"):
            return self._add_objective(text)
        elif cmd == "list" or cmd.startswith("list "):
            return self._list_objectives(text)
        elif cmd.startswith("show "):
            return self._show_objective(text)
        elif cmd.startswith("update "):
            return self._update_objective(text)
        elif cmd.startswith("add-kr ") or cmd.startswith("add_kr "):
            return self._add_key_result(text)
        elif cmd.startswith("complete "):
            return self._complete_objective(text)
        elif cmd.startswith("delete "):
            return self._delete_objective(text)
        elif cmd == "report":
            return self._generate_report()
        else:
            return PluginResult(
                success=False,
                error=f"Unknown command: {cmd}\n\n"
                      "Available: add objective, list, show, update, add-kr, complete, delete, report"
            )

    def _add_objective(self, text: str) -> PluginResult:
        """Add a new objective."""
        # Remove command prefix
        body = re.sub(r'^add\s+objective\s*:\s*', '', text, flags=re.IGNORECASE).strip()
        if not body:
            return PluginResult(success=False, error="Vui lòng nhập tiêu đề mục tiêu.")

        # Extract fields
        title = body
        description = ""
        due_date = ""
        priority = "medium"

        # Parse target date
        target_match = re.search(r'target[=:]\s*(\d{4}-\d{2}-\d{2})', body, re.IGNORECASE)
        if target_match:
            due_date = target_match.group(1)
            title = title.replace(target_match.group(0), "").strip()

        # Parse priority
        priority_match = re.search(r'priority[=:]\s*(high|medium|low)', body, re.IGNORECASE)
        if priority_match:
            priority = priority_match.group(1).lower()
            title = title.replace(priority_match.group(0), "").strip()

        # Parse description
        desc_match = re.search(r'description[=:]\s*(.+?)(?:\s+(?:target|priority)[=:]|$)', body, re.IGNORECASE)
        if desc_match:
            description = desc_match.group(1).strip()
            title = title.replace(desc_match.group(0), "").strip()

        # Clean up title
        title = title.strip().strip(",:;'\"")
        if not title:
            return PluginResult(success=False, error="Vui lòng nhập tiêu đề mục tiêu.")

        now = time.time()
        result = _execute_db(
            self._db_path,
            "INSERT INTO objectives (title, description, priority, due_date, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (title, description, priority, due_date, now, now),
        )
        if result is None:
            return PluginResult(success=False, error="Không thể thêm mục tiêu.")

        lines = [
            f"✅ **Objective added successfully!**",
            f"",
            f"- **Title:** {title}",
            f"- **Priority:** {priority}",
            f"- **Target:** {due_date or 'No deadline'}",
            f"",
            f"💡 Thêm Key Results: `add-kr <id>: <mục tiêu đo lường>`",
            f"📋 Xem danh sách: `list`",
        ]
        return PluginResult(success=True, output="\n".join(lines))

    def _list_objectives(self, text: str) -> PluginResult:
        """List all objectives with optional status filter."""
        # Parse filter
        filter_status = None
        parts = text.split()
        if len(parts) > 1 and parts[1] in ("all", "active", "completed", "draft", "cancelled"):
            filter_status = parts[1] if parts[1] != "all" else None

        if filter_status:
            rows = _execute_db(
                self._db_path,
                "SELECT * FROM objectives WHERE status = ? ORDER BY priority DESC, updated_at DESC",
                (filter_status,),
            )
        else:
            rows = _execute_db(
                self._db_path,
                "SELECT * FROM objectives ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'draft' THEN 1 ELSE 2 END, updated_at DESC",
            )

        if rows is None or len(rows) == 0:
            return PluginResult(
                success=True,
                output="📭 **No objectives found.**\n\n"
                       "Tạo mục tiêu mới: `add objective: Học Python target:2026-12-31`"
            )

        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        status_icons = {"active": "🔄", "completed": "✅", "draft": "📝", "cancelled": "❌"}

        lines = [
            f"## 🎯 OKR Dashboard",
            f"**Total:** {len(rows)} objectives",
            f"",
        ]
        for row in rows:
            p_icon = priority_icons.get(row["priority"], "⚪")
            s_icon = status_icons.get(row["status"], "📋")
            progress_bar = "▓" * (row["progress"] // 10) + "░" * (10 - row["progress"] // 10)
            lines.append(f"{s_icon} **#{row['id']}** {p_icon} {row['title']}")
            lines.append(f"   `[{progress_bar}] {row['progress']}%`  _{row['status']}_")
            if row["due_date"]:
                lines.append(f"   📅 Due: {row['due_date']}")
            lines.append("")

        lines.append("---")
        lines.append("💡 `show <id>` để xem chi tiết | `report` để xem báo cáo")
        return PluginResult(success=True, output="\n".join(lines))

    def _show_objective(self, text: str) -> PluginResult:
        """Show objective details with key results."""
        match = re.search(r'show\s+(\d+)', text)
        if not match:
            return PluginResult(success=False, error="Vui lòng nhập ID mục tiêu. Ví dụ: `show 1`")
        obj_id = int(match.group(1))

        rows = _execute_db(self._db_path, "SELECT * FROM objectives WHERE id = ?", (obj_id,))
        if not rows:
            return PluginResult(success=False, error=f"Không tìm thấy mục tiêu #{obj_id}")

        obj = rows[0]
        krs = _execute_db(self._db_path, "SELECT * FROM key_results WHERE objective_id = ?", (obj_id,)) or []

        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        status_icons = {"active": "🔄", "completed": "✅", "draft": "📝", "cancelled": "❌"}
        p_icon = priority_icons.get(obj["priority"], "")
        s_icon = status_icons.get(obj["status"], "")

        lines = [
            f"## 🎯 Objective #{obj['id']} {obj['title']}",
            f"",
            f"- **Status:** {s_icon} {obj['status']}",
            f"- **Priority:** {p_icon} {obj['priority']}",
            f"- **Progress:** {obj['progress']}%",
            f"- **Due:** {obj['due_date'] or 'No deadline'}",
            f"",
        ]
        if obj["description"]:
            lines.append(f"> {obj['description']}")
            lines.append("")

        if krs:
            lines.append(f"### Key Results ({len(krs)})")
            for kr in krs:
                kr_bar = "▓" * (kr["progress"] // 10) + "░" * (10 - kr["progress"] // 10)
                lines.append(f"  - `[{kr_bar}] {kr['progress']}%` {kr['title']}")
            lines.append("")

        lines.append("---")
        lines.append("💡 `update <id> progress:N` | `complete <id>` | `add-kr <id>: <title>`")
        return PluginResult(success=True, output="\n".join(lines))

    def _update_objective(self, text: str) -> PluginResult:
        """Update objective progress."""
        match = re.search(r'update\s+(\d+)\s+progress[=:]\s*(\d+)', text)
        if not match:
            return PluginResult(success=False, error="Định dạng: `update <id> progress:<0-100>`")
        obj_id = int(match.group(1))
        progress = min(100, max(0, int(match.group(2))))

        result = _execute_db(
            self._db_path,
            "UPDATE objectives SET progress = ?, updated_at = ? WHERE id = ?",
            (progress, time.time(), obj_id),
        )
        if result is False or result is None:
            return PluginResult(success=False, error=f"Không tìm thấy mục tiêu #{obj_id}")

        # Auto-complete if 100%
        if progress == 100:
            _execute_db(
                self._db_path,
                "UPDATE objectives SET status = 'completed' WHERE id = ? AND status != 'cancelled'",
                (obj_id,),
            )

        return PluginResult(success=True, output=f"✅ **Objective #{obj_id}** progress updated to **{progress}%**")

    def _add_key_result(self, text: str) -> PluginResult:
        """Add a key result to an objective."""
        match = re.search(r'add[-_]kr\s+(\d+)[=:]\s*(.+)', text, re.IGNORECASE)
        if not match:
            return PluginResult(success=False, error="Định dạng: `add-kr <objective_id>: <key result title>`")
        obj_id = int(match.group(1))
        title = match.group(2).strip()
        if not title:
            return PluginResult(success=False, error="Vui lòng nhập tên Key Result.")

        result = _execute_db(
            self._db_path,
            "INSERT INTO key_results (objective_id, title) VALUES (?, ?)",
            (obj_id, title),
        )
        if result is None:
            return PluginResult(success=False, error=f"Không tìm thấy mục tiêu #{obj_id}")

        return PluginResult(success=True, output=f"✅ **Key Result added** to Objective #{obj_id}: {title}")

    def _complete_objective(self, text: str) -> PluginResult:
        """Mark an objective as completed."""
        match = re.search(r'complete\s+(\d+)', text)
        if not match:
            return PluginResult(success=False, error="Vui lòng nhập ID. Ví dụ: `complete 1`")
        obj_id = int(match.group(1))

        result = _execute_db(
            self._db_path,
            "UPDATE objectives SET status = 'completed', progress = 100, updated_at = ? WHERE id = ?",
            (time.time(), obj_id),
        )
        if result is None:
            return PluginResult(success=False, error=f"Không tìm thấy mục tiêu #{obj_id}")

        return PluginResult(success=True, output=f"✅ **Objective #{obj_id}** marked as completed! 🎉")

    def _delete_objective(self, text: str) -> PluginResult:
        """Delete an objective and its key results."""
        match = re.search(r'delete\s+(\d+)', text)
        if not match:
            return PluginResult(success=False, error="Vui lòng nhập ID. Ví dụ: `delete 1`")
        obj_id = int(match.group(1))

        # Delete key results first
        _execute_db(self._db_path, "DELETE FROM key_results WHERE objective_id = ?", (obj_id,))
        _execute_db(self._db_path, "DELETE FROM objectives WHERE id = ?", (obj_id,))

        return PluginResult(success=True, output=f"🗑️ **Objective #{obj_id}** deleted.")

    def _generate_report(self) -> PluginResult:
        """Generate a full OKR status report."""
        rows = _execute_db(self._db_path, "SELECT * FROM objectives ORDER BY priority DESC, updated_at DESC")
        if not rows:
            return PluginResult(success=True, output="📭 Chưa có mục tiêu nào.")

        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        status_labels = {"active": "🔄 In Progress", "completed": "✅ Done", "draft": "📝 Draft", "cancelled": "❌ Cancelled"}

        active = [r for r in rows if r["status"] == "active"]
        completed = [r for r in rows if r["status"] == "completed"]
        draft = [r for r in rows if r["status"] == "draft"]

        total_progress = sum(r["progress"] for r in rows) / max(len(rows), 1)

        lines = [
            f"## 📊 OKR Status Report",
            f"",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Total Objectives:** {len(rows)}",
            f"**Overall Progress:** {total_progress:.0f}%",
            f"",
            f"---",
            f"",
        ]

        if active:
            lines.append(f"### 🔄 Active ({len(active)})")
            for r in active:
                p_icon = priority_icons.get(r["priority"], "")
                bar = "▓" * (r["progress"] // 10) + "░" * (10 - r["progress"] // 10)
                lines.append(f"- **#{r['id']}** {p_icon} {r['title']}")
                lines.append(f"  `[{bar}] {r['progress']}%`")
            lines.append("")

        if completed:
            lines.append(f"### ✅ Completed ({len(completed)}) 🎉")
            for r in completed:
                p_icon = priority_icons.get(r["priority"], "")
                lines.append(f"- {p_icon} **#{r['id']}** {r['title']}")
            lines.append("")

        if draft:
            lines.append(f"### 📝 Draft ({len(draft)})")
            for r in draft:
                lines.append(f"- **#{r['id']}** {r['title']}")
            lines.append("")

        lines.append("---")
        lines.append(f"💡 `add objective:` để thêm mới | `show <id>` để xem chi tiết")
        return PluginResult(success=True, output="\n".join(lines))
