"""
Personal Finance Analyzer (Feature #97).
Analyzes uploaded financial data (CSV/excel) and provides budget insights.

Features:
- Parse CSV/excel transaction data
- Spending by category
- Monthly trends
- Budget vs actual analysis
- Savings rate calculation
- Top spending insights

Usage:
    FinancePlugin.execute("Category:Food, Amount:100")
    FinancePlugin.execute("Monthly budget: 2000, rent: 800, food: 400, transport: 200")
"""

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("finance")

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False


@dataclass
class Transaction:
    """A single financial transaction."""
    date: str = ""
    description: str = ""
    category: str = "Other"
    amount: float = 0.0
    type: str = "expense"  # income, expense, transfer


@dataclass
class BudgetAnalysis:
    """Result of budget analysis."""
    total_income: float = 0.0
    total_expenses: float = 0.0
    savings: float = 0.0
    savings_rate: float = 0.0
    top_categories: list[tuple[str, float]] = field(default_factory=list)
    monthly_avg: dict[str, float] = field(default_factory=dict)
    insights: list[str] = field(default_factory=list)
    transaction_count: int = 0


# ── Default budget categories ──

_DEFAULT_CATEGORIES = {
    "housing": ["rent", "mortgage", "maintenance", "housing"],
    "food": ["food", "groceries", "restaurant", "dining", "eat"],
    "transport": ["transport", "gas", "fuel", "bus", "train", "taxi", "car"],
    "utilities": ["electric", "water", "internet", "phone", "utility"],
    "entertainment": ["entertainment", "movie", "game", "streaming", "music"],
    "healthcare": ["health", "medical", "pharmacy", "doctor", "hospital"],
    "education": ["education", "tuition", "course", "book", "training"],
    "shopping": ["shopping", "clothes", "electronics", "amazon"],
    "savings": ["savings", "investment", "deposit"],
    "salary": ["salary", "income", "wage", "paycheck", "freelance"],
}


def _categorize(description: str) -> str:
    """Categorize a transaction based on its description."""
    desc_lower = description.lower()
    for category, keywords in _DEFAULT_CATEGORIES.items():
        if any(kw in desc_lower for kw in keywords):
            return category.capitalize()
    return "Other"


def _parse_csv_text(text: str) -> list[Transaction]:
    """Parse CSV-formatted text into transactions."""
    transactions = []
    lines = text.strip().split("\n")

    if not lines:
        return transactions

    # Detect delimiter
    if ";" in lines[0]:
        delimiter = ";"
    elif "\t" in lines[0]:
        delimiter = "\t"
    else:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    for row in reader:
        # Try common column names
        date = row.get("date") or row.get("Date") or row.get("DATE") or row.get("ngày") or ""
        desc = row.get("description") or row.get("Description") or row.get("desc") or row.get("mô tả") or row.get("note") or ""
        category = row.get("category") or row.get("Category") or row.get("danh mục") or ""
        amount_str = row.get("amount") or row.get("Amount") or row.get("AMOUNT") or row.get("số tiền") or row.get("value") or "0"

        # Clean amount
        amount_str = amount_str.replace("$", "").replace("€", "").replace("£", "").replace("₫", "").replace(",", "").strip()
        try:
            amount = float(amount_str)
        except (ValueError, TypeError):
            amount = 0.0

        # Detect sign
        if amount < 0:
            tran_type = "expense"
            amount = abs(amount)
        elif any(w in desc.lower() for w in ["salary", "income", "revenue", "deposit"]):
            tran_type = "income"
        else:
            tran_type = "expense"

        if not category:
            category = _categorize(desc)

        transactions.append(Transaction(
            date=date,
            description=desc,
            category=category,
            amount=amount,
            type=tran_type,
        ))

    return transactions


def _parse_natural_language(text: str) -> list[Transaction]:
    """Parse natural language budget descriptions into transactions."""
    transactions = []

    # "Category:Amount" format
    # Match patterns like "food: 400", "rent = 800", "Category Food 300"
    patterns = [
        r'(?:category\s+)?(\w[\w\s]+?)\s*[:=]\s*(\d+[\d,.]*)',
        r'(?:spent|spend|paid)\s+(\d+[\d,.]*)\s+(?:on|for)\s+(.+?)(?:[,.]|$)',
        r'(\w[\w\s]+?)\s+(?:cost|is|was)\s+(\d+[\d,.]*)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                if match[0].replace(" ", "").isdigit():
                    # Amount first
                    amount = float(match[0].replace(",", ""))
                    category = match[1].strip()
                else:
                    category = match[0].strip()
                    amount_str = match[1].replace(",", "").strip()
                    try:
                        amount = float(amount_str)
                    except ValueError:
                        continue
            else:
                continue

            # Clean category
            category = re.sub(r'\s+', ' ', category).strip().title()
            if category.lower() in _DEFAULT_CATEGORIES:
                category = category.capitalize()

            transactions.append(Transaction(
                category=category,
                amount=amount,
                description=f"{category} expense",
                type="expense",
            ))

        if transactions:
            break  # Use first matching pattern

    return transactions


def _analyze_transactions(transactions: list[Transaction]) -> BudgetAnalysis:
    """Analyze a list of transactions."""
    analysis = BudgetAnalysis()
    analysis.transaction_count = len(transactions)

    if not transactions:
        return analysis

    # Separate income and expenses
    incomes = [t for t in transactions if t.type == "income"]
    expenses = [t for t in transactions if t.type == "expense"]

    analysis.total_income = sum(t.amount for t in incomes)
    analysis.total_expenses = sum(t.amount for t in expenses)
    analysis.savings = analysis.total_income - analysis.total_expenses

    if analysis.total_income > 0:
        analysis.savings_rate = (analysis.savings / analysis.total_income) * 100

    # Category breakdown
    category_totals: dict[str, float] = {}
    for t in expenses:
        category_totals[t.category] = category_totals.get(t.category, 0.0) + t.amount

    analysis.top_categories = sorted(
        category_totals.items(),
        key=lambda x: -x[1],
    )[:5]

    # Generate insights
    if analysis.total_income > 0:
        analysis.insights.append(
            f"💵 **Income:** ${analysis.total_income:,.2f}"
        )
    if analysis.total_expenses > 0:
        analysis.insights.append(
            f"💳 **Expenses:** ${analysis.total_expenses:,.2f}"
        )
        # Top category
        if analysis.top_categories:
            cat, amt = analysis.top_categories[0]
            pct = (amt / analysis.total_expenses) * 100
            analysis.insights.append(
                f"📊 **Top category:** {cat} (${amt:,.2f}) — {pct:.0f}% of expenses"
            )

    analysis.insights.append(
        f"💰 **Savings:** ${analysis.savings:,.2f} ({analysis.savings_rate:.1f}%)"
    )

    if analysis.savings_rate < 0:
        analysis.insights.append(
            "⚠️ **Warning:** You're spending more than you earn!"
        )
    elif analysis.savings_rate < 10:
        analysis.insights.append(
            "📈 **Tip:** Try to save at least 10-20% of your income."
        )
    elif analysis.savings_rate >= 20:
        analysis.insights.append(
            "🌟 **Great job!** Your savings rate is excellent."
        )

    return analysis


def _format_analysis(analysis: BudgetAnalysis) -> str:
    """Format budget analysis as Markdown."""
    lines = [
        "## 💰 Personal Finance Summary",
        "",
    ]

    if analysis.transaction_count > 0:
        lines.append(f"*{analysis.transaction_count} transactions analyzed*")
        lines.append("")

        for insight in analysis.insights:
            lines.append(insight)
        lines.append("")

        # Category breakdown table
        if analysis.top_categories:
            lines.append("### 📊 Spending by Category")
            lines.append("")
            lines.append("| Category | Amount | % of Total |")
            lines.append("|:---------|------:|----------:|")
            for cat, amt in analysis.top_categories:
                pct = (amt / analysis.total_expenses) * 100 if analysis.total_expenses > 0 else 0
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(f"| {cat} | ${amt:,.2f} | {pct:.1f}% {bar} |")
            lines.append("")

        # Summary row
        lines.append("### 📋 Summary")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|:-------|------:|")
        lines.append(f"| Total Income | ${analysis.total_income:,.2f} |")
        lines.append(f"| Total Expenses | ${analysis.total_expenses:,.2f} |")
        lines.append(f"| Net Savings | ${analysis.savings:,.2f} |")
        lines.append(f"| Savings Rate | {analysis.savings_rate:.1f}% |")
        lines.append(f"| Transactions | {analysis.transaction_count} |")
        lines.append("")
    else:
        lines.append("*No transactions found to analyze.*")
        lines.append("")
        lines.append("Try:")
        lines.append("- `Salary: 3000, Rent: 800, Food: 400, Transport: 200`")
        lines.append("- Upload a CSV with columns: date, description, amount, category")

    lines.append("---")
    lines.append("*Analysis by Project Atlas*")
    return "\n".join(lines)


class FinancePlugin(BasePlugin):
    """
    Analyzes personal financial data and provides budget insights.

    Input formats:
    - **Category:Amount list**: `Rent: 800, Food: 400, Transport: 200, Salary: 3000`
    - **CSV paste**: Paste CSV data with headers (date, description, amount, category)
    - **Natural language**: `I spent 400 on food and 800 on rent this month`

    Examples:
        "Salary: 3000, Rent: 800, Food: 400, Transport: 200, Entertainment: 100"
        "date,description,amount,category\\n2024-01-01,Rent,800,Housing\\n2024-01-02,Groceries,150,Food"
        "Monthly budget: income=2500, rent=700, food=350, transport=150, savings=300"

    Shows:
    - Income/expense summary
    - Spending by category (sorted)
    - Savings rate and tips
    """

    name = "finance"
    description = "Phân tích tài chính cá nhân từ dữ liệu thu chi"

    def execute(self, input_str: str) -> PluginResult:
        """Analyze financial data from input."""
        text = input_str.strip()
        if not text:
            return PluginResult(
                success=False,
                error=(
                    "Vui lòng nhập dữ liệu tài chính.\\n\\n"
                    "Định dạng hỗ trợ:\\n"
                    "- `Category: Amount` list\\n"
                    "- CSV (date, description, amount, category)\\n"
                    "- Natural language\\n\\n"
                    "Ví dụ:\\n"
                    "`Salary: 3000, Rent: 800, Food: 400, Transport: 200`"
                )
            )

        try:
            # Try CSV first (if it has headers and multiple lines)
            if "\n" in text and re.search(r'(date|description|amount|category)', text[:200], re.IGNORECASE):
                transactions = _parse_csv_text(text)
            else:
                transactions = _parse_natural_language(text)

            analysis = _analyze_transactions(transactions)
            output = _format_analysis(analysis)

            return PluginResult(
                success=True,
                output=output,
                data={
                    "total_income": analysis.total_income,
                    "total_expenses": analysis.total_expenses,
                    "savings_rate": analysis.savings_rate,
                    "transaction_count": analysis.transaction_count,
                },
            )
        except Exception as e:
            logger.error(f"Finance analysis failed: {e}")
            return PluginResult(
                success=False,
                error=f"Không thể phân tích dữ liệu tài chính: {e}"
            )
