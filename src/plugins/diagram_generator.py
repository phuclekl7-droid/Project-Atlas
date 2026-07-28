"""
Diagram Generator Plugin (Feature #53).
Generates Mermaid.js diagrams from natural language descriptions.

Produces Mermaid text that can be rendered by any Mermaid-compatible viewer
(mermaid.ink, GitHub markdown, VS Code plugins, etc.)

Supported diagram types:
- Flowchart (graph TD/LR)
- Sequence diagram (sequenceDiagram)
- Class diagram (classDiagram)
- State diagram (stateDiagram-v2)
- Pie chart (pie)
- Gantt chart (gantt)

Usage:
    DiagramGeneratorPlugin.execute("flowchart: User logs in -> system checks password")
    DiagramGeneratorPlugin.execute("sequence: Client sends request to Server")
    DiagramGeneratorPlugin.execute("pie: Python 40%, Java 25%, JS 35%")
"""

import re
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("diagram_generator")


def _detect_diagram_type(text: str) -> Optional[str]:
    """Detect the diagram type from the input text."""
    text_lower = text.strip().lower()
    prefixes = {
        "flowchart": "flowchart",
        "flow": "flowchart",
        "graph": "flowchart",
        "sequence": "sequence",
        "seq": "sequence",
        "class": "class",
        "state": "state",
        "pie": "pie",
        "gantt": "gantt",
        "timeline": "timeline",
    }
    for prefix, dtype in prefixes.items():
        if text_lower.startswith(prefix):
            return dtype
    return None


def _build_flowchart(text: str) -> str:
    """Build a Mermaid flowchart diagram."""
    # Remove prefix
    body = re.sub(r'^(flowchart|flow|graph)\s*:\s*', '', text, flags=re.IGNORECASE)
    nodes = []
    edges = []

    # Parse "A -> B" or "A --> B" patterns
    for match in re.finditer(r'([A-Za-z0-9_\s]+?)\s*-{1,2}[>|]\s*([A-Za-z0-9_\s]+?)(?:\s*[:-]?\s*(.*?))?(?=\s*[,;]|\s*$|\s+[A-Za-z]+\s*[:-])', body):
        source = match.group(1).strip()
        target = match.group(2).strip()
        label = match.group(3).strip() if match.group(3) else ""
        if source not in nodes:
            nodes.append(source)
        if target not in nodes:
            nodes.append(target)
        edges.append((source, target, label))

    # If no edges found, treat as linear chain
    if not edges:
        parts = re.split(r'\s*[,;]\s*|\s*->\s*|\s*-->\s*', body)
        parts = [p.strip() for p in parts if p.strip()]
        for i in range(len(parts) - 1):
            if parts[i] not in nodes:
                nodes.append(parts[i])
            if parts[i + 1] not in nodes:
                nodes.append(parts[i + 1])
            edges.append((parts[i], parts[i + 1], ""))

    lines = ["```mermaid", "flowchart TD"]
    for edge in edges:
        if edge[2]:
            lines.append(f"    {edge[0]} -->|{edge[2]}| {edge[1]}")
        else:
            lines.append(f"    {edge[0]} --> {edge[1]}")
    lines.append("```")
    return "\n".join(lines)


def _build_sequence(text: str) -> str:
    """Build a Mermaid sequence diagram."""
    body = re.sub(r'^(sequence|seq)\s*:\s*', '', text, flags=re.IGNORECASE)
    parts = re.split(r'\s*[,;]\s*', body)
    actors = []
    messages = []

    for part in parts:
        part = part.strip()
        # "A sends message to B" or "A -> B: message"
        msg_match = re.match(r'(.+?)\s+(?:sends|say|tells?|asks?)\s+(.+?)\s+(?:to|that)\s+(.+?)$', part, re.IGNORECASE)
        arrow_match = re.match(r'(.+?)\s*-[>|]\s*(.+?)(?::\s*(.*))?$', part)

        if msg_match:
            actor1 = msg_match.group(1).strip()
            action = msg_match.group(2).strip()
            actor2 = msg_match.group(3).strip()
            if actor1 not in actors:
                actors.append(actor1)
            if actor2 not in actors:
                actors.append(actor2)
            messages.append((actor1, actor2, action))
        elif arrow_match:
            actor1 = arrow_match.group(1).strip()
            actor2 = arrow_match.group(2).strip()
            label = arrow_match.group(3).strip() if arrow_match.group(3) else ""
            if actor1 not in actors:
                actors.append(actor1)
            if actor2 not in actors:
                actors.append(actor2)
            messages.append((actor1, actor2, label))

    if not messages:
        # Simple: "Client sends request to Server"
        words = body.split()
        if len(words) >= 3:
            actors = ["Actor1", "Actor2"]
            messages = [("Actor1", "Actor2", body[:60])]

    lines = ["```mermaid", "sequenceDiagram"]
    for actor in actors:
        lines.append(f"    participant {actor}")
    for msg in messages:
        lines.append(f"    {msg[0]}->>{msg[1]}: {msg[2]}")
    lines.append("```")
    return "\n".join(lines)


def _build_pie(text: str) -> str:
    """Build a Mermaid pie chart."""
    body = re.sub(r'^pie\s*:\s*', '', text, flags=re.IGNORECASE)
    title = "Pie Chart"
    data = []

    # Parse "Label: value%" or "Label value%"
    for match in re.finditer(r'([A-Za-z\s]+)\s*[:\s]\s*(\d+(?:\.\d+)?)\s*%?', body):
        label = match.group(1).strip()
        value = match.group(2)
        data.append((label, value))

    lines = ["```mermaid", "pie"]
    if title:
        lines.append(f"    title {title}")
    for label, value in data:
        lines.append(f"    \"{label}\" : {value}")
    lines.append("```")
    return "\n".join(lines)


def _build_class_diagram(text: str) -> str:
    """Build a Mermaid class diagram."""
    body = re.sub(r'^class\s*:\s*', '', text, flags=re.IGNORECASE)
    classes = []

    # Parse "ClassName: method1(), method2()" or "ClassName <|-- BaseClass"
    for line in body.split(","):
        line = line.strip()
        if not line:
            continue
        class_match = re.match(r'([A-Za-z0-9_]+)\s*:\s*(.+?)$', line)
        if class_match:
            name = class_match.group(1).strip()
            members = [m.strip() for m in class_match.group(2).split(",") if m.strip()]
            classes.append((name, members))
        else:
            classes.append((line, []))

    lines = ["```mermaid", "classDiagram"]
    for name, members in classes:
        lines.append(f"    class {name} {{")
        for m in members:
            lines.append(f"        +{m}")
        lines.append("    }")
    lines.append("```")
    return "\n".join(lines)


def _generate_diagram(input_str: str) -> str:
    """Generate a Mermaid diagram from natural language input."""
    dtype = _detect_diagram_type(input_str) or "flowchart"

    if dtype == "sequence":
        return _build_sequence(input_str)
    elif dtype == "pie":
        return _build_pie(input_str)
    elif dtype == "class":
        return _build_class_diagram(input_str)
    else:
        return _build_flowchart(input_str)


class DiagramGeneratorPlugin(BasePlugin):
    """
    Generates Mermaid.js diagrams from natural language descriptions.

    Supported diagram types:
    - Flowchart: "flowchart: A -> B, B -> C"
    - Sequence: "sequence: Client sends request to Server"
    - Pie chart: "pie: Python 40%, Java 25%, JavaScript 35%"
    - Class diagram: "class: User: login(), logout(), Profile: save()"

    Examples:
        "flowchart: User enters credentials -> system validates -> access granted"
        "sequence: Browser sends HTTP request to Server"
        "pie: Python 60%, JavaScript 25%, Go 15%"

    Outputs Mermaid markup that renders in GitHub, GitLab, Notion, etc.
    """

    name = "diagram_generator"
    description = "Tạo sơ đồ Mermaid.js (flowchart, sequence, pie chart)"

    def execute(self, input_str: str) -> PluginResult:
        """Generate a diagram from the input description."""
        if not input_str.strip():
            return PluginResult(
                success=False,
                error=(
                    "Vui lòng nhập mô tả sơ đồ.\n\n"
                    "Ví dụ:\n"
                    "- `flowchart: A -> B, B -> C`\n"
                    "- `sequence: Client sends request to Server`\n"
                    "- `pie: Python 40%, Java 35%, JS 25%`"
                )
            )

        try:
            diagram = _generate_diagram(input_str)
            lines = [
                f"## 📐 Diagram Generated",
                f"",
                diagram,
                f"",
                f"💡 *Copy đoạn mã trên và dán vào **mermaid.live** hoặc GitHub markdown để xem hình ảnh.*",
                f"",
                f"### 📝 Mermaid Source",
                f"```markdown",
                diagram.replace("```mermaid", "").replace("```", "").strip(),
                f"```",
            ]
            output = "\n".join(lines)
            return PluginResult(success=True, output=output, data={"mermaid": diagram})
        except Exception as e:
            logger.error(f"Diagram generation failed: {e}")
            return PluginResult(success=False, error=f"Không thể tạo sơ đồ: {e}")
