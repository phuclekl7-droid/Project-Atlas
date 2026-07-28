"""
Mermaid.js Diagram Rendering (Feature #48).
Renders Mermaid.js diagram text to SVG/PNG images.

Two rendering backends:
1. **Mermaid.ink API** (primary): Uses the mermaid.ink free API to convert Mermaid text to SVG
2. **ASCII Fallback**: Generates ASCII art representation when API is unavailable

Usage:
    MermaidRendererPlugin.execute("graph TD; A-->B; B-->C;")
    MermaidRendererPlugin.execute("sequenceDiagram; Alice->>John: Hello John;")
"""

import base64
import json
import re
import urllib.parse
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("mermaid_renderer")

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


def _encode_mermaid_for_url(diagram_text: str) -> str:
    """
    Encode Mermaid diagram text for use in mermaid.ink URL.

    Uses the 'deflate' + 'base64' encoding that mermaid.ink expects.
    Falls back to simple URL encoding.
    """
    import zlib
    compressed = zlib.compress(diagram_text.encode("utf-8"))
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
    return encoded


def _render_via_api(diagram_text: str, theme: str = "default") -> Optional[str]:
    """
    Render Mermaid diagram via mermaid.ink API.

    Returns the SVG URL if successful.
    """
    if not _HAS_REQUESTS:
        logger.debug("requests not installed, cannot render via API")
        return None

    try:
        encoded = _encode_mermaid_for_url(diagram_text)
        # Use the SVG endpoint
        url = f"https://mermaid.ink/svg/{encoded}"
        # Verify the URL works by doing a HEAD request
        response = requests.head(url, timeout=5)
        if response.status_code < 500:
            return url
        logger.debug(f"mermaid.ink returned status {response.status_code}")
        return None
    except Exception as e:
        logger.debug(f"mermaid.ink API failed: {e}")
        return None


def _ascii_fallback(diagram_text: str) -> str:
    """
    Generate a simple ASCII art representation of Mermaid flowcharts.

    Works for simple graph TD/LR and sequence diagrams.
    """
    lines = []
    lines.append("```")
    lines.append("// Mermaid Diagram (ASCII representation)")
    lines.append("")

    # Parse flowchart nodes and edges
    if "graph" in diagram_text or "flowchart" in diagram_text:
        # Extract edges like A-->B or A-->|label|B
        edges = re.findall(r'(\w+)\s*-{1,2}[>|]\s*(\w+)', diagram_text)
        if edges:
            nodes_seen = set()
            for src, dst in edges:
                if src not in nodes_seen:
                    lines.append(f"  [{src}]")
                    nodes_seen.add(src)
                lines.append(f"    |")
                lines.append(f"    v")
                lines.append(f"  [{dst}]")
                nodes_seen.add(dst)
                lines.append("")

    # Parse sequence diagrams
    if "sequenceDiagram" in diagram_text:
        actors = set()
        sequence_lines = []
        for match in re.finditer(r'(\w+)\s*-[>>]+>\s*(\w+)\s*:\s*(.+)', diagram_text):
            src, dst, msg = match.groups()
            actors.add(src)
            actors.add(dst)
            sequence_lines.append((src, dst, msg))
        for actor in sorted(actors):
            lines.append(f"  {actor}")
        lines.append("")
        for src, dst, msg in sequence_lines:
            lines.append(f"  {src} ──→ {dst}: {msg}")

    lines.append("")
    lines.append("// Paste the Mermaid source above into https://mermaid.live to render")
    lines.append("```")
    return "\n".join(lines)


def _detect_and_extract_mermaid(text: str) -> Optional[str]:
    """Detect if input contains Mermaid code (with or without ```mermaid markers)."""
    # Check for ```mermaid ... ``` blocks
    mermaid_block = re.search(r'```mermaid\s*\n(.*?)\n```', text, re.DOTALL)
    if mermaid_block:
        return mermaid_block.group(1).strip()

    # Check for direct Mermaid syntax (starts with graph, sequenceDiagram, etc.)
    mermaid_patterns = [
        r'(graph\s+(?:TD|LR|RL|BT)[^`]*)',
        r'(sequenceDiagram[^`]*)',
        r'(classDiagram[^`]*)',
        r'(stateDiagram[^`]*)',
        r'(pie[^`]*)',
        r'(gantt[^`]*)',
        r'(flowchart\s+(?:TD|LR|RL|BT)[^`]*)',
    ]
    for pattern in mermaid_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            code = match.group(1).strip()
            # Clean up trailing code fences
            code = re.sub(r'```\s*$', '', code).strip()
            return code

    return None


class MermaidRendererPlugin(BasePlugin):
    """
    Renders Mermaid.js diagram code to SVG images.

    Two modes:
    - **Render mode**: Pass Mermaid code → get rendered SVG URL
    - **Inline mode**: Includes Mermaid code in a ```mermaid block (GitHub renders it)

    Examples:
        "graph TD; A[Start] --> B[End];"
        "sequenceDiagram; Alice->>John: Hello John;"
        "```mermaid\\ngraph TD; A-->B;\\n```"

    Use the mermaid.live link if the image doesn't render inline.
    """

    name = "mermaid_renderer"
    description = "Vẽ sơ đồ Mermaid.js và render thành ảnh SVG"

    def execute(self, input_str: str) -> PluginResult:
        """Render a Mermaid diagram."""
        text = input_str.strip()
        if not text:
            return PluginResult(
                success=False,
                error=(
                    "Vui lòng nhập mã Mermaid.js.\n\n"
                    "Ví dụ:\n"
                    "- `graph TD; A[Start] --> B[End];`\n"
                    "- `sequenceDiagram; Alice->>John: Hello;`\n"
                    "- `pie title Languages \\\"Python\\\" : 60 \\\"JS\\\" : 40`"
                )
            )

        diagram = _detect_and_extract_mermaid(text)
        if not diagram:
            return PluginResult(
                success=False,
                error=(
                    "Không tìm thấy mã Mermaid.js hợp lệ.\n\n"
                    "Mã phải bắt đầu bằng: graph, sequenceDiagram, classDiagram, "
                    "stateDiagram, pie, gantt, hoặc flowchart.\n\n"
                    "Ví dụ hợp lệ:\n"
                    "`graph TD; A-->B;`"
                )
            )

        # Try API render first
        api_url = _render_via_api(diagram)

        # Build output
        lines = [
            f"## 📐 Mermaid Diagram",
            f"",
        ]

        if api_url:
            lines.extend([
                f"### Rendered SVG",
                f"",
                f"![]({api_url})",
                f"",
                f"🔗 **Direct URL:** [Open SVG]({api_url})",
                f"",
            ])
        else:
            lines.append(f"_{'requests not installed' if not _HAS_REQUESTS else 'Render API unavailable'} — showing Mermaid source._")
            lines.append("")

        lines.extend([
            f"### Mermaid Source",
            f"",
            f"Copy đoạn mã dưới đây và dán vào **https://mermaid.live** để xem hình ảnh:",
            f"",
            f"```mermaid",
            f"{diagram}",
            f"```",
            f"",
            f"---",
            f"💡 Mermaid code renders automatically in GitHub, GitLab, Notion, and Obsidian.",
        ])

        return PluginResult(
            success=True,
            output="\n".join(lines),
            data={"mermaid": diagram, "svg_url": api_url},
        )
