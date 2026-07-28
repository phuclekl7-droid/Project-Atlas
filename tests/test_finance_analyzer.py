"""
Tests for Feature #97: Personal Finance Analyzer.
"""

import pytest

from src.plugins.finance_analyzer import (
    FinancePlugin,
    _categorize,
    _parse_csv_text,
    _parse_natural_language,
    _analyze_transactions,
    _format_analysis,
    Transaction,
    BudgetAnalysis,
)


class TestCategorize:
    """Tests for transaction categorization."""

    def test_food(self):
        assert _categorize("groceries at walmart").lower() == "food"

    def test_housing(self):
        assert _categorize("rent payment").lower() == "housing"

    def test_transport(self):
        assert _categorize("bus fare").lower() == "transport"

    def test_unknown_default(self):
        assert _categorize("random purchase").lower() == "other"

    def test_entertainment(self):
        assert _categorize("netflix subscription").lower() == "entertainment"


class TestParseNaturalLanguage:
    """Tests for natural language parsing."""

    def test_category_amount_format(self):
        txns = _parse_natural_language("Rent: 800, Food: 400, Transport: 200")
        assert len(txns) >= 1

    def test_category_equals_format(self):
        txns = _parse_natural_language("rent = 800, food = 400")
        assert len(txns) >= 1

    def test_income_detection(self):
        txns = _parse_natural_language("Salary: 3000, Rent: 800")
        assert len(txns) >= 1


class TestParseCSV:
    """Tests for CSV parsing."""

    def test_csv_with_headers(self):
        csv_text = "date,description,amount,category\n2024-01-01,Rent,800,Housing\n2024-01-02,Groceries,150,Food"
        txns = _parse_csv_text(csv_text)
        assert len(txns) >= 1

    def test_csv_no_data(self):
        txns = _parse_csv_text("")
        assert txns == []

    def test_csv_with_semicolons(self):
        csv_text = "date;description;amount;category\n2024-01-01;Rent;800;Housing"
        txns = _parse_csv_text(csv_text)
        assert len(txns) >= 1


class TestAnalyzeTransactions:
    """Tests for transaction analysis."""

    def test_empty_transactions(self):
        analysis = _analyze_transactions([])
        assert analysis.transaction_count == 0
        assert analysis.total_income == 0

    def test_basic_analysis(self):
        txns = [
            Transaction(amount=3000, type="income", category="Salary"),
            Transaction(amount=800, type="expense", category="Housing"),
            Transaction(amount=400, type="expense", category="Food"),
        ]
        analysis = _analyze_transactions(txns)
        assert analysis.transaction_count == 3
        assert analysis.total_income == 3000
        assert analysis.total_expenses == 1200
        assert analysis.savings == 1800

    def test_savings_rate(self):
        txns = [
            Transaction(amount=2000, type="income", category="Salary"),
            Transaction(amount=500, type="expense", category="Rent"),
        ]
        analysis = _analyze_transactions(txns)
        assert analysis.savings_rate == 75.0

    def test_top_categories(self):
        txns = [
            Transaction(amount=500, type="expense", category="Food"),
            Transaction(amount=800, type="expense", category="Rent"),
            Transaction(amount=200, type="expense", category="Transport"),
        ]
        analysis = _analyze_transactions(txns)
        assert len(analysis.top_categories) >= 1
        # Rent (800) should be top
        assert analysis.top_categories[0][0] == "Rent"

    def test_negative_savings_warning(self):
        txns = [
            Transaction(amount=1000, type="income", category="Salary"),
            Transaction(amount=1200, type="expense", category="Spending"),
        ]
        analysis = _analyze_transactions(txns)
        assert analysis.savings < 0
        assert any("Warning" in i for i in analysis.insights)

    def test_good_savings_rate(self):
        txns = [
            Transaction(amount=5000, type="income", category="Salary"),
            Transaction(amount=1000, type="expense", category="Expenses"),
        ]
        analysis = _analyze_transactions(txns)
        assert analysis.savings_rate >= 20
        assert any("Great" in i for i in analysis.insights)


class TestFormatAnalysis:
    """Tests for analysis formatting."""

    def test_format_empty(self):
        analysis = BudgetAnalysis()
        output = _format_analysis(analysis)
        assert "Finance" in output or "Summary" in output

    def test_format_with_data(self):
        analysis = BudgetAnalysis(
            total_income=5000,
            total_expenses=2000,
            savings=3000,
            savings_rate=60.0,
            top_categories=[("Rent", 800), ("Food", 400)],
            transaction_count=10,
            insights=["Income: $5,000.00", "Great savings rate!"],
        )
        output = _format_analysis(analysis)
        assert "$5,000" in output
        assert "Rent" in output


class TestFinancePlugin:
    """Tests for FinancePlugin class."""

    def test_empty_input(self):
        plugin = FinancePlugin()
        result = plugin.execute("")
        assert not result.success

    def test_budget_input(self):
        plugin = FinancePlugin()
        result = plugin.execute("Salary: 3000, Rent: 800, Food: 400, Transport: 200")
        assert result.success
        assert "Finance" in result.output or "Summary" in result.output

    def test_csv_input(self):
        plugin = FinancePlugin()
        result = plugin.execute(
            "date,description,amount,category\n2024-01-01,Rent,800,Housing"
        )
        assert result.success
