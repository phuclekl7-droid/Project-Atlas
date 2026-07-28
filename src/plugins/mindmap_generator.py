"""
Mindmap Interactive View (Feature #56).
Generates text-based mindmaps from conversations or structured data.

Provides:
- Automatic mindmap generation from text/keywords
- ASCII/Unicode mindmap rendering
- Markdown hierarchical output
- Multiple layout styles (tree, radial, bracket)

Usage:
    MindmapPlugin.execute("Python: basics, OOP, async")
    MindmapPlugin.execute("Project Atlas: Core, Memory, Plugins, UI")
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("mindmap")


@dataclass
class MindmapNode:
    """A single node in the mindmap tree."""
    label: str = ""
    children: list["MindmapNode"] = field(default_factory=list)
    level: int = 0
    icon: str = ""

    def add_child(self, label: str) -> "MindmapNode":
        child = MindmapNode(label=label, level=self.level + 1)
        self.children.append(child)
        return child

    def to_text(self, style: str = "tree", prefix: str = "") -> list[str]:
        """
        Render this node and its children as text lines.

        Args:
            style: "tree" (Unicode), "ascii" (ASCII-only), "bracket" (indented brackets)
            prefix: Current line prefix (for recursion)

        Returns:
            List of text lines
        """
        lines = []

        if style == "bracket":
            # Indented bracket style
            indent = "  " * self.level
            icon_str = f"{self.icon} " if self.icon else ""
            if self.children:
                lines.append(f"{indent}{icon_str}{self.label} {{")
                for child in self.children:
                    lines.extend(child.to_text(style))
                lines.append(f"{indent}}}")
            else:
                lines.append(f"{indent}{icon_str}{self.label}")
        else:
            # Tree or ASCII style
            if self.level == 0:
                # Root
                icon_str = f"{self.icon} " if self.icon else ""
                lines.append(f"{icon_str}{self.label}")
                for child in self.children:
                    lines.extend(child.to_text(style, "  "))
            else:
                indent = "  " * (self.level - 1)
                if style == "ascii":
                    continuation = "|   "
                    last_branch = "\\-- "
                    mid_branch = "|-- "
                else:
                    continuation = "│   "
                    last_branch = "└── "
                    mid_branch = "├── "

                icon_str = f"{self.icon} " if self.icon else ""
                child_count = len(self.children)

                for i, child in enumerate(self.children):
                    is_last = (i == child_count - 1)
                    branch = last_branch if is_last else mid_branch
                    lines.append(f"{prefix}{branch}{icon_str}{child.label}")
                    child_prefix = prefix + ("    " if is_last else continuation)
                    lines.extend(child.to_text(style, child_prefix))

        return lines

    def count_nodes(self) -> int:
        """Count total nodes in the tree (including self)."""
        return 1 + sum(child.count_nodes() for child in self.children)

    def max_depth(self) -> int:
        """Get maximum depth from this node."""
        if not self.children:
            return self.level
        return max(child.max_depth() for child in self.children)


def _parse_text_to_tree(text: str) -> MindmapNode:
    """
    Parse structured text into a mindmap tree.

    Supports formats:
    - "Topic: subtopic1, subtopic2, subtopic3"
    - "A > B > C" (path notation)
    - Indented lines (2-space = level)
    - "Topic - subtopic | subtopic2" (pipe separator)
    - "Topic\\n  - item1\\n  - item2" (Markdown list)
    """
    root = MindmapNode(label="Root")
    text = text.strip()

    if not text:
        root.label = "Empty"
        return root

    # Detect format
    lines = text.split("\n")

    if len(lines) > 1:
        # Multi-line: detect indentation-based structure
        return _parse_indented_lines(lines)

    # Single line: try colon format ("Topic: items")
    if ":" in text and not text.startswith("http"):
        parts = text.split(":", 1)
        root.label = parts[0].strip()

        # Rest is comma or pipe-separated
        rest = parts[1].strip()
        if "|" in rest:
            items = [i.strip() for i in rest.split("|") if i.strip()]
        else:
            items = [i.strip() for i in rest.split(",") if i.strip()]

        for item in items:
            if ":" in item:
                # Nested: "subtopic: subsub1, subsub2"
                sub_parts = item.split(":", 1)
                child = root.add_child(sub_parts[0].strip())
                for sub in [s.strip() for s in sub_parts[1].split(",") if s.strip()]:
                    child.add_child(sub)
            else:
                root.add_child(item)

        return root

    # Path notation: "A > B > C"
    if " > " in text:
        parts = [p.strip() for p in text.split(" > ")]
        root.label = parts[0]
        current = root
        for part in parts[1:]:
            current = current.add_child(part)
        return root

    # Simple list: "item1, item2, item3" or "item1 | item2 | item3"
    if "," in text or "|" in text:
        sep = "|" if "|" in text else ","
        items = [i.strip() for i in text.split(sep) if i.strip()]
        if items:
            root.label = items[0] if len(items) > 1 else items[0]
            if len(items) > 1:
                for item in items[1:]:
                    root.add_child(item)
        return root

    # Single topic
    root.label = text
    return root


def _parse_indented_lines(lines: list[str]) -> MindmapNode:
    """Parse indented lines into a tree structure."""
    root = MindmapNode(label="Root")

    # Find first non-empty line
    first_line = ""
    first_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped:
            first_line = stripped
            first_idx = i
            break

    if not first_line:
        return root

    # First line is the title
    root.label = first_line

    # Parse remaining lines with indentation
    path_stack: list[tuple[int, MindmapNode]] = [(0, root)]

    for line in lines[first_idx + 1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        # Calculate indent level
        indent = len(line) - len(line.lstrip())
        level = indent // 2  # 2 spaces = 1 level

        # Clean up list markers
        clean = re.sub(r'^[-*+•]\s+', '', stripped)
        clean = re.sub(r'^\d+[.)]\s+', '', clean)

        # Pop stack to correct level
        while path_stack and path_stack[-1][0] >= level:
            path_stack.pop()

        if path_stack:
            parent_node = path_stack[-1][1]
            new_node = parent_node.add_child(clean)
            path_stack.append((level, new_node))
        else:
            new_node = root.add_child(clean)
            path_stack.append((level, new_node))

    return root


def _build_markdown_mindmap(node: MindmapNode) -> str:
    """Build a Markdown representation of the mindmap."""
    lines = [
        f"## 🧠 Mindmap: {node.label}",
        "",
    ]

    if node.children:
        for child in node.children:
            _render_markdown_node(child, lines, 2)
    else:
        lines.append(f"- {node.label}")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by Project Atlas*")

    return "\n".join(lines)


def _render_markdown_node(node: MindmapNode, lines: list[str], depth: int):
    """Recursively render a mindmap node as Markdown."""
    indent = "  " * (depth - 1)
    icon = f"{node.icon} " if node.icon else ""
    prefix = "#" * min(depth, 6)

    if node.children:
        lines.append(f"{indent}- **{icon}{node.label}**")
        for child in node.children:
            _render_markdown_node(child, lines, depth + 1)
    else:
        lines.append(f"{indent}- {icon}{node.label}")


class MindmapPlugin(BasePlugin):
    """
    Generates text-based mindmaps from structured text input.

    Input formats:
    - **Colon**: `Topic: item1, item2, item3` — simple list
    - **Nested**: `Topic: Subtopic: sub1, sub2 | Other: o1, o2` — two levels
    - **Path**: `A > B > C` — linear chain
    - **Indented**: Multi-line with 2-space indent levels
    - **Markdown list**: Lines starting with -, *, +

    Examples:
        "Project Atlas: Core, Memory, Plugins, UI"
        "Python: Basics: variables, types | OOP: classes, inheritance | Async: coroutines"
        "A > B > C > D"
        "My Project\\n  - Planning\\n  - Development\\n    - Frontend\\n    - Backend\\n  - Testing"

    Use `/mindmap on` to see ASCII tree view or `/mindmap markdown` for Markdown view.
    """

    name = "mindmap"
    description = "Tạo sơ đồ tư duy (mindmap) từ văn bản có cấu trúc"

    def execute(self, input_str: str) -> PluginResult:
        """Generate a mindmap from input text."""
        text = input_str.strip()
        if not text:
            return PluginResult(
                success=False,
                error=(
                    "Vui lòng nhập nội dung để tạo mindmap.\\n\\n"
                    "Định dạng hỗ trợ:\\n"
                    "- `Chủ đề: mục 1, mục 2, mục 3`\\n"
                    "- `Chủ đề: Phần A: chi tiết 1, chi tiết 2 | Phần B: ...`\\n"
                    "- `A > B > C` (đường dẫn)\\n"
                    "- Nhiều dòng với thụt lề 2 spaces\\n\\n"
                    "Ví dụ:\\n"
                    "`Python: Basics, OOP: classes, inheritance | Async: coroutines`"
                )
            )

        # Parse commands
        mode = "tree"
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower()
            if cmd == "/markdown":
                mode = "markdown"
                text = parts[1].strip() if len(parts) > 1 else ""
            elif cmd == "/ascii":
                mode = "ascii"
                text = parts[1].strip() if len(parts) > 1 else ""
            elif cmd == "/bracket":
                mode = "bracket"
                text = parts[1].strip() if len(parts) > 1 else ""

        if not text:
            return PluginResult(
                success=False,
                error="Vui lòng nhập nội dung sau lệnh.\\nVí dụ: `/markdown Python: basics, OOP`"
            )

        try:
            tree = _parse_text_to_tree(text)

            if mode == "markdown":
                output = _build_markdown_mindmap(tree)
            else:
                ascii_mode = "ascii" if mode == "ascii" else "tree"
                lines = tree.to_text(style=ascii_mode)
                output = "\n".join([
                    f"## 🧠 Mindmap: {tree.label}",
                    "",
                    "```",
                    *lines,
                    "```",
                    "",
                    f"_{tree.count_nodes()} nodes · depth {tree.max_depth()}_",
                ])

            return PluginResult(
                success=True,
                output=output,
                data={
                    "root": tree.label,
                    "node_count": tree.count_nodes(),
                    "depth": tree.max_depth(),
                },
            )
        except Exception as e:
            logger.error(f"Mindmap generation failed: {e}")
            return PluginResult(
                success=False,
                error=f"Không thể tạo mindmap: {e}"
            )
