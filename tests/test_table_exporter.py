"""
Unit tests for Table Exporter (Markdown Table to CSV).

Tests:
- ExtractedTable dataclass
- extract_tables with valid markdown table
- extract_tables with no tables returns empty list
- extract_tables with multiple tables
- extract_tables with empty text
- table_to_csv format
- extract_all_csv convenience method
- render_download_html generates link tags
- Edge cases: separator-only, malformed rows, single row
"""

import pytest

from src.features.table_exporter import TableExporter, ExtractedTable, _parse_table_row


class TestExtractedTable:
    def test_defaults(self):
        t = ExtractedTable(index=0)
        assert t.index == 0
        assert t.headers == []
        assert t.rows == []
        assert t.row_count == 0
        assert t.col_count == 0

    def test_with_data(self):
        t = ExtractedTable(index=1, headers=["A", "B"], rows=[["1", "2"]])
        assert t.index == 1
        assert t.headers == ["A", "B"]
        assert t.rows == [["1", "2"]]
        assert t.row_count == 1
        assert t.col_count == 2

    def test_to_csv(self):
        t = ExtractedTable(index=0, headers=["Name", "Age"], rows=[["Alice", "30"], ["Bob", "25"]])
        csv_text = t.to_csv()
        assert "Name,Age" in csv_text
        assert "Alice,30" in csv_text
        assert "Bob,25" in csv_text

    def test_to_csv_no_headers(self):
        t = ExtractedTable(index=0, rows=[["a", "b"], ["c", "d"]])
        csv_text = t.to_csv()
        assert "a,b" in csv_text
        assert "c,d" in csv_text

    def test_repr(self):
        t = ExtractedTable(index=0, headers=["X"], rows=[["1"]])
        r = repr(t)
        assert "ExtractedTable" in r
        assert "index=0" in r


class TestParseTableRow:
    def test_simple_row(self):
        cells = _parse_table_row("| a | b | c |")
        assert cells == ["a", "b", "c"]

    def test_row_with_spaces(self):
        cells = _parse_table_row("|  hello  |  world  |")
        assert cells == ["hello", "world"]

    def test_row_no_leading_pipe(self):
        cells = _parse_table_row("a | b | c")
        assert cells == ["a", "b", "c"]

    def test_empty_cells(self):
        cells = _parse_table_row("|| a || b |")
        assert len(cells) >= 3

    def test_single_cell(self):
        cells = _parse_table_row("| just one |")
        assert cells == ["just one"]


class TestTableExporter:
    @pytest.fixture
    def exporter(self):
        return TableExporter()

    def test_extract_single_table(self, exporter):
        md = (
            "| Name | Age | City |\n"
            "|------|-----|------|\n"
            "| Alice | 30 | Hanoi |\n"
            "| Bob | 25 | HCMC |\n"
        )
        tables = exporter.extract_tables(md)
        assert len(tables) == 1
        assert tables[0].headers == ["Name", "Age", "City"]
        assert len(tables[0].rows) == 2
        assert tables[0].rows[0] == ["Alice", "30", "Hanoi"]

    def test_no_tables(self, exporter):
        md = "Hello, this is plain text.\nNo tables here."
        tables = exporter.extract_tables(md)
        assert tables == []

    def test_empty_text(self, exporter):
        tables = exporter.extract_tables("")
        assert tables == []

    def test_multiple_tables(self, exporter):
        md = (
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "Some text\n\n"
            "| X | Y | Z |\n|---|---|---|\n| a | b | c |\n| d | e | f |\n"
        )
        tables = exporter.extract_tables(md)
        assert len(tables) == 2
        assert tables[0].headers == ["A", "B"]
        assert tables[1].headers == ["X", "Y", "Z"]
        assert len(tables[1].rows) == 2

    def test_table_without_separator(self, exporter):
        """Row without separator line should still be detected."""
        md = "| Col1 | Col2 |\n| val1 | val2 |\n"
        tables = exporter.extract_tables(md)
        assert len(tables) == 1
        assert tables[0].headers == ["Col1", "Col2"]

    def test_table_various_separator_styles(self, exporter):
        """Separator with colons (alignment markers) should still work."""
        md = (
            "| Left | Center | Right |\n"
            "|:-----|:------:|------:|\n"
            "| a    |   b    |   c   |\n"
        )
        tables = exporter.extract_tables(md)
        assert len(tables) == 1
        assert tables[0].headers == ["Left", "Center", "Right"]

    def test_table_to_csv(self, exporter):
        md = "| Fruit | Qty |\n|---|---|\n| Apple | 5 |\n| Banana | 3 |\n"
        csvs = exporter.extract_all_csv(md)
        assert len(csvs) == 1
        assert "Fruit,Qty" in csvs[0]
        assert "Apple,5" in csvs[0]

    def test_render_download_html(self, exporter):
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        tables = exporter.extract_tables(md)
        html = exporter.render_download_html(tables)
        assert html != ""
        assert "📥" in html
        assert ".csv" in html
        assert "data:text/csv" in html

    def test_render_download_html_no_tables(self, exporter):
        html = exporter.render_download_html([])
        assert html == ""

    def test_table_with_mixed_separator(self, exporter):
        """Table with various separator lengths."""
        md = (
            "|H1|H2|H3|\n"
            "|---|---|---|\n"
            "|a|b|c|\n"
        )
        tables = exporter.extract_tables(md)
        assert len(tables) == 1
        assert tables[0].headers == ["H1", "H2", "H3"]

    def test_text_with_inline_pipes_not_table(self, exporter):
        """Pipes not in table format should not be detected."""
        md = "Use | to separate | values in bash."
        tables = exporter.extract_tables(md)
        assert tables == []
