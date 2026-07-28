"""
Table Exporter (Feature 167: Markdown Table to CSV Downloader)

Auto-detects Markdown tables in AI responses and adds download buttons
to export them as CSV files.

Parses standard Markdown tables:
| col1 | col2 |
|------|------|
| val1 | val2 |

Usage:
    exporter = TableExporter()
    tables = exporter.extract_tables(markdown_text)
    csv_text = exporter.table_to_csv(tables[0])
    html = exporter.render_download_buttons(tables)  # HTML for UI
"""

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractedTable:
    """Represents a single Markdown table found in text."""
    index: int
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    raw_text: str = ""

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def col_count(self) -> int:
        return len(self.headers) if self.headers else 0

    def to_csv(self) -> str:
        """Convert this table to CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)
        if self.headers:
            writer.writerow(self.headers)
        for row in self.rows:
            writer.writerow(row)
        return output.getvalue().strip()

    def __repr__(self) -> str:
        return (f"ExtractedTable(index={self.index}, "
                f"headers={self.headers}, rows={len(self.rows)})")


# ── Regex for Markdown tables ──

# Matches separator line: |---|---| or |:---|:---:|---:|
_SEPARATOR_PATTERN = r"^\|[\s:]*-+\s*(\|[\s:]*-+\s*)+\|$"

# Matches a full data row: | cell | cell |
_ROW_PATTERN = r"^\|(.+)\|$"


def _parse_table_row(line: str) -> list[str]:
    """Parse a single Markdown table row into cells."""
    cells = []
    # Strip leading/trailing |
    content = line.strip()
    if content.startswith("|"):
        content = content[1:]
    if content.endswith("|"):
        content = content[:-1]
    # Split by | and trim each cell
    for cell in content.split("|"):
        cells.append(cell.strip())
    return cells


class TableExporter:
    """
    Extracts Markdown tables from text and provides CSV download support.

    Usage:
        exporter = TableExporter()
        tables = exporter.extract_tables(markdown_text)
        for t in tables:
            print(t.to_csv())
    """

    def extract_tables(self, markdown_text: str) -> list[ExtractedTable]:
        """
        Extract all Markdown tables from a text block.

        Args:
            markdown_text: Text that may contain Markdown tables

        Returns:
            List of ExtractedTable objects (empty if none found)
        """
        if not markdown_text:
            return []

        tables: list[ExtractedTable] = []
        lines = markdown_text.split("\n")
        current_table: Optional[ExtractedTable] = None
        in_table = False
        table_index = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                if in_table and current_table:
                    if current_table.headers:
                        tables.append(current_table)
                        table_index += 1
                current_table = None
                in_table = False
                continue

            # Check for separator line (| --- | --- |)
            if re.match(_SEPARATOR_PATTERN, stripped):
                if not in_table:
                    # This separator starts a new table
                    current_table = ExtractedTable(index=table_index, raw_text=stripped)
                    in_table = True
                # Skip separator line
                continue

            # Check for data row (| ... |)
            if stripped.startswith("|") and stripped.endswith("|"):
                cells = _parse_table_row(stripped)

                if not in_table:
                    current_table = ExtractedTable(index=table_index, raw_text=stripped)
                    in_table = True

                if current_table is not None:
                    if not current_table.headers:
                        # First row is the header
                        current_table.headers = cells
                    else:
                        # Subsequent rows are data
                        current_table.rows.append(cells)
                continue

            # Non-table line while in a table — end the table
            if in_table and current_table:
                if current_table.headers:
                    tables.append(current_table)
                    table_index += 1
                current_table = None
                in_table = False

        # Don't forget the last table if text ends with one
        if in_table and current_table and current_table.headers:
            tables.append(current_table)

        return tables

    def table_to_csv(self, table: ExtractedTable) -> str:
        """Convert an ExtractedTable to CSV string."""
        return table.to_csv()

    def extract_all_csv(self, markdown_text: str) -> list[str]:
        """
        Extract all tables and return them as CSV strings.

        Args:
            markdown_text: Text with Markdown tables

        Returns:
            List of CSV strings (one per table found)
        """
        tables = self.extract_tables(markdown_text)
        return [t.to_csv() for t in tables]

    def render_download_html(self, tables: list[ExtractedTable]) -> str:
        """
        Render HTML download buttons for each table found.

        Returns inline HTML that Streamlit can render with unsafe_allow_html=True.

        Args:
            tables: List of extracted tables

        Returns:
            HTML string with download buttons (empty if no tables)
        """
        if not tables:
            return ""

        parts = []
        for t in tables:
            csv_data = t.to_csv()
            # Simple base64 encoding for data URI
            import base64
            b64 = base64.b64encode(csv_data.encode("utf-8")).decode("ascii")
            filename = f"table_{t.index + 1}.csv"

            parts.append(
                f'<div style="margin:0.3rem 0;font-size:0.8rem;">'
                f'<a href="data:text/csv;base64,{b64}" '
                f'download="{filename}" '
                f'style="display:inline-block;padding:0.25rem 0.6rem;'
                f'border-radius:6px;background:rgba(102,126,234,0.1);'
                f'color:#667eea;border:1px solid rgba(102,126,234,0.2);'
                f'text-decoration:none;font-size:0.75rem;'
                f'cursor:pointer;">'
                f'📥 Tải bảng dữ liệu #{t.index + 1} ({t.row_count} rows)'
                f'</a></div>'
            )
        return "\n".join(parts)
