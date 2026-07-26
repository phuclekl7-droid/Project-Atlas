"""
Calculator Plugin — performs basic arithmetic operations.

Usage:
    "2 + 3"     → 2 + 3 = 5
    "10 - 4"    → 10 - 4 = 6
    "6 * 7"     → 6 × 7 = 42
    "20 / 4"    → 20 ÷ 4 = 5
    "2 ^ 10"    → 2^10 = 1024
    "sqrt 16"   → √16 = 4
    "5 % 2"     → 5 mod 2 = 1
"""

import math
import operator
import re
from typing import Optional

from src.plugin import BasePlugin, PluginResult


# ── Pattern definitions (order matters — more specific first) ──
_PATTERNS = [
    # power: "2 ^ 10" or "2**10"
    (re.compile(r"^(-?\d+\.?\d*)\s*(\^|\*\*)\s*(-?\d+\.?\d*)$"), "power"),
    # multiply: "6 * 7"
    (re.compile(r"^(-?\d+\.?\d*)\s*(\*)\s*(-?\d+\.?\d*)$"), "mul"),
    # divide: "20 / 4"
    (re.compile(r"^(-?\d+\.?\d*)\s*(/)\s*(-?\d+\.?\d*)$"), "div"),
    # add: "2 + 3"
    (re.compile(r"^(-?\d+\.?\d*)\s*(\+)\s*(-?\d+\.?\d*)$"), "add"),
    # subtract: "10 - 4"
    (re.compile(r"^(-?\d+\.?\d*)\s*(-)\s*(-?\d+\.?\d*)$"), "sub"),
    # modulo: "5 % 2"
    (re.compile(r"^(-?\d+\.?\d*)\s*(%)\s*(-?\d+\.?\d*)$"), "mod"),
    # sqrt: "sqrt 16" or "sqrt(16)"
    (re.compile(r"^sqrt\s*\(?\s*(-?\d+\.?\d*)\s*\)?\s*$"), "sqrt"),
    # factorial: "5!" or "-3!"
    (re.compile(r"^(-?\d+)\s*!$"), "fact"),
]

_OPERATORS = {
    "add": operator.add,
    "sub": operator.sub,
    "mul": operator.mul,
    "div": operator.truediv,
    "power": operator.pow,
    "mod": operator.mod,
}

_OP_SYMBOLS = {
    "add": "+",
    "sub": "-",
    "mul": "×",
    "div": "÷",
    "power": "^",
    "mod": "%",
}


def _format_number(n: float) -> str:
    """Format a number nicely — integer if whole, otherwise limit decimals."""
    if n == int(n):
        return str(int(n))
    # Remove trailing zeros
    s = f"{n:.10f}".rstrip("0").rstrip(".")
    return s


class CalculatorPlugin(BasePlugin):
    """
    Performs basic arithmetic: +, -, ×, ÷, ^, √, %, !

    Examples:
        "2 + 3" → 5
        "sqrt 16" → 4
    """

    name = "calculator"
    description = "Tính toán cơ bản: +, -, ×, ÷, ^, √, %, !"

    def execute(self, input_str: str) -> PluginResult:
        """
        Parse and evaluate a mathematical expression.

        Args:
            input_str: e.g., "2 + 3", "sqrt 16", "5!"

        Returns:
            PluginResult with the result or error message
        """
        expr = input_str.strip()

        if not expr:
            return PluginResult(
                success=False,
                error="Vui lòng nhập phép tính. Ví dụ: 2 + 3, sqrt 16, 5!",
            )

        # Try each pattern
        for pattern, op_name in _PATTERNS:
            match = pattern.match(expr)
            if match:
                if op_name == "sqrt":
                    return self._calc_unary(op_name, match.group(1))
                elif op_name == "fact":
                    return self._calc_unary(op_name, match.group(1))
                else:
                    return self._calc_binary(op_name, match.group(1), match.group(3))

        # No pattern matched
        return PluginResult(
            success=False,
            error=(
                f"Không hiểu phép tính: '{expr}'\n\n"
                f"Các phép tính hỗ trợ:\n"
                f"  +   : 2 + 3\n"
                f"  -   : 10 - 4\n"
                f"  ×   : 6 * 7\n"
                f"  ÷   : 20 / 4\n"
                f"  ^   : 2 ^ 10\n"
                f"  %   : 5 % 2\n"
                f"  √   : sqrt 16\n"
                f"  !   : 5!"
            ),
        )

    def _calc_binary(self, op_name: str, a_str: str, b_str: str) -> PluginResult:
        """Two-operand operation (add, sub, mul, div, power, mod)."""
        try:
            a = float(a_str)
            b = float(b_str)
        except ValueError:
            return PluginResult(success=False, error=f"Số không hợp lệ: {a_str} hoặc {b_str}")

        op_func = _OPERATORS.get(op_name)
        if op_func is None:
            return PluginResult(success=False, error=f"Phép tính '{op_name}' không hỗ trợ")

        # Check division by zero
        if op_name in ("div", "mod") and b == 0:
            return PluginResult(success=False, error="Không thể chia cho 0!")

        try:
            result = op_func(a, b)
        except Exception as e:
            return PluginResult(success=False, error=f"Lỗi tính toán: {e}")

        symbol = _OP_SYMBOLS.get(op_name, op_name)
        result_str = _format_number(result)
        a_str_fmt = _format_number(a)
        b_str_fmt = _format_number(b)

        output = f"{a_str_fmt} {symbol} {b_str_fmt} = **{result_str}**"
        return PluginResult(success=True, output=output, data=result)

    def _calc_unary(self, op_name: str, val_str: str) -> PluginResult:
        """Single-operand operation (sqrt, factorial)."""
        try:
            val = float(val_str)
        except ValueError:
            return PluginResult(success=False, error=f"Số không hợp lệ: {val_str}")

        try:
            if op_name == "sqrt":
                if val < 0:
                    return PluginResult(success=False, error="Không thể tính căn bậc 2 của số âm")
                result = math.sqrt(val)
                result_str = _format_number(result)
                val_fmt = _format_number(val)
                output = f"√{val_fmt} = **{result_str}**"

            elif op_name == "fact":
                if val != int(val) or val < 0:
                    return PluginResult(
                        success=False, error="Giai thừa chỉ áp dụng cho số nguyên không âm"
                    )
                n = int(val)
                if n > 100:
                    return PluginResult(success=False, error="Số quá lớn (tối đa 100!)")
                result = math.factorial(n)
                result_str = _format_number(result)
                output = f"{n}! = **{result_str}**"

            else:
                return PluginResult(success=False, error=f"Phép tính '{op_name}' không hỗ trợ")

        except Exception as e:
            return PluginResult(success=False, error=f"Lỗi tính toán: {e}")

        return PluginResult(success=True, output=output, data=result)
