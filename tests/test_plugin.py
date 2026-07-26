"""
Unit tests for the Plugin module and CalculatorPlugin.

Tests:
- BasePlugin ABC (cannot instantiate abstract class)
- PluginResult dataclass
- PluginLoader discovery and execution
- CalculatorPlugin: addition, subtraction, multiplication, division, power, sqrt, factorial, modulo
- CalculatorPlugin: error handling (division by zero, invalid input, negative sqrt)
"""

import pytest

from src.plugin import (
    BasePlugin,
    PluginExecutionError,
    PluginLoader,
    PluginResult,
)
from src.plugins.calculator import CalculatorPlugin


# ============================================================
# BasePlugin Tests
# ============================================================


def test_baseplugin_cannot_instantiate():
    """BasePlugin is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BasePlugin()


class TestBasePlugin:
    def test_subclass_must_implement_execute(self):
        """A subclass without execute() should not be instantiable."""
        with pytest.raises(TypeError):
            class IncompletePlugin(BasePlugin):
                name = "test"
            IncompletePlugin()

    def test_subclass_with_execute(self):
        """A proper subclass should instantiate and work."""
        class TestPlugin(BasePlugin):
            name = "test_plugin"
            description = "A test plugin"
            def execute(self, input_str):
                return PluginResult(success=True, output=f"Executed: {input_str}")

        plugin = TestPlugin()
        assert plugin.name == "test_plugin"
        assert plugin.description == "A test plugin"

    def test_get_info(self):
        """get_info should return name and description."""
        class InfoPlugin(BasePlugin):
            name = "info"
            description = "Info provider"
            def execute(self, input_str):
                return PluginResult(success=True, output="ok")

        plugin = InfoPlugin()
        info = plugin.get_info()
        assert info["name"] == "info"
        assert info["description"] == "Info provider"

    def test_repr(self):
        """__repr__ should include class name and plugin name."""
        class ReprPlugin(BasePlugin):
            name = "repr_test"
            description = ""
            def execute(self, input_str):
                return PluginResult(success=True, output="ok")

        plugin = ReprPlugin()
        r = repr(plugin)
        assert "ReprPlugin" in r
        assert "repr_test" in r


# ============================================================
# PluginResult Tests
# ============================================================


class TestPluginResult:
    def test_success_default(self):
        """PluginResult should default to success=True."""
        result = PluginResult()
        assert result.success is True
        assert result.output == ""
        assert result.error == ""

    def test_success_result(self):
        """A successful result should store output."""
        result = PluginResult(success=True, output="42", data=42)
        assert result.output == "42"
        assert result.data == 42

    def test_error_result(self):
        """An error result should store error message."""
        result = PluginResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_repr_success(self):
        """__repr__ for success should show output."""
        result = PluginResult(success=True, output="Hello world")
        r = repr(result)
        assert "success=True" in r
        assert "Hello" in r

    def test_repr_error(self):
        """__repr__ for error should show error message."""
        result = PluginResult(success=False, error="Failed")
        r = repr(result)
        assert "success=False" in r
        assert "Failed" in r


# ============================================================
# PluginLoader Tests
# ============================================================


class TestPluginLoader:
    def test_discover_empty_package(self):
        """Discover on a non-existent package should not crash."""
        loader = PluginLoader(plugin_package="src.nonexistent")
        plugins = loader.discover()
        assert plugins == {}

    def test_discover_calculator(self):
        """Discover should find the CalculatorPlugin."""
        loader = PluginLoader(plugin_package="src.plugins")
        plugins = loader.discover()
        assert "calculator" in plugins
        assert isinstance(plugins["calculator"], CalculatorPlugin)

    def test_get_calculator(self):
        """get() should return the calculator plugin."""
        loader = PluginLoader(plugin_package="src.plugins")
        loader.discover()
        plugin = loader.get("calculator")
        assert plugin is not None
        assert plugin.name == "calculator"

    def test_get_nonexistent(self):
        """get() for non-existent plugin should return None."""
        loader = PluginLoader(plugin_package="src.plugins")
        loader.discover()
        assert loader.get("non_existent") is None

    def test_get_all(self):
        """get_all should return all plugins as a list."""
        loader = PluginLoader(plugin_package="src.plugins")
        loader.discover()
        all_plugins = loader.get_all()
        assert len(all_plugins) >= 1
        assert any(p.name == "calculator" for p in all_plugins)

    def test_list_plugins(self):
        """list_plugins should return metadata dicts."""
        loader = PluginLoader(plugin_package="src.plugins")
        loader.discover()
        plugins = loader.list_plugins()
        assert isinstance(plugins, list)
        assert any(p["name"] == "calculator" for p in plugins)

    def test_execute_success(self):
        """execute() should run the plugin and return PluginResult."""
        loader = PluginLoader(plugin_package="src.plugins")
        loader.discover()
        result = loader.execute("calculator", "2 + 3")
        assert isinstance(result, PluginResult)
        assert result.success is True

    def test_execute_nonexistent_raises(self):
        """execute() on non-existent plugin should raise PluginExecutionError."""
        loader = PluginLoader(plugin_package="src.plugins")
        loader.discover()
        with pytest.raises(PluginExecutionError, match="not found"):
            loader.execute("non_existent", "input")

    def test_repr(self):
        """__repr__ should list loaded plugins."""
        loader = PluginLoader(plugin_package="src.plugins")
        loader.discover()
        r = repr(loader)
        assert "PluginLoader" in r
        assert "calculator" in r


# ============================================================
# CalculatorPlugin Tests
# ============================================================


class TestCalculatorPlugin:
    @pytest.fixture
    def calc(self):
        """Return a CalculatorPlugin instance."""
        return CalculatorPlugin()

    # ── Addition ──
    def test_add_integers(self, calc):
        result = calc.execute("2 + 3")
        assert result.success is True
        assert result.data == 5
        assert "5" in result.output

    def test_add_floats(self, calc):
        result = calc.execute("3.5 + 2.1")
        assert result.success is True
        assert result.data == 5.6

    def test_add_negative(self, calc):
        result = calc.execute("-5 + 3")
        assert result.success is True
        assert result.data == -2

    # ── Subtraction ──
    def test_subtract(self, calc):
        result = calc.execute("10 - 4")
        assert result.success is True
        assert result.data == 6

    def test_subtract_negative_result(self, calc):
        result = calc.execute("3 - 10")
        assert result.success is True
        assert result.data == -7

    # ── Multiplication ──
    def test_multiply(self, calc):
        result = calc.execute("6 * 7")
        assert result.success is True
        assert result.data == 42

    def test_multiply_float(self, calc):
        result = calc.execute("2.5 * 4")
        assert result.success is True
        assert result.data == 10.0

    # ── Division ──
    def test_divide(self, calc):
        result = calc.execute("20 / 4")
        assert result.success is True
        assert result.data == 5.0

    def test_divide_float_result(self, calc):
        result = calc.execute("7 / 2")
        assert result.success is True
        assert result.data == 3.5

    def test_divide_by_zero(self, calc):
        result = calc.execute("5 / 0")
        assert result.success is False
        assert "0" in result.error or "chia" in result.error.lower()

    def test_divide_negative(self, calc):
        result = calc.execute("-10 / 2")
        assert result.success is True
        assert result.data == -5.0

    # ── Power ──
    def test_power(self, calc):
        result = calc.execute("2 ^ 10")
        assert result.success is True
        assert result.data == 1024

    def test_power_float(self, calc):
        result = calc.execute("9 ** 0.5")
        assert result.success is True
        assert result.data == 3.0

    # ── Square Root ──
    def test_sqrt(self, calc):
        result = calc.execute("sqrt 16")
        assert result.success is True
        assert result.data == 4.0

    def test_sqrt_with_parentheses(self, calc):
        result = calc.execute("sqrt(25)")
        assert result.success is True
        assert result.data == 5.0

    def test_sqrt_negative(self, calc):
        result = calc.execute("sqrt -9")
        assert result.success is False
        assert "âm" in result.error.lower()

    # ── Factorial ──
    def test_factorial(self, calc):
        result = calc.execute("5!")
        assert result.success is True
        assert result.data == 120

    def test_factorial_zero(self, calc):
        result = calc.execute("0!")
        assert result.success is True
        assert result.data == 1

    def test_factorial_negative(self, calc):
        result = calc.execute("-3!")
        assert result.success is False  # negative not supported

    # ── Modulo ──
    def test_modulo(self, calc):
        result = calc.execute("10 % 3")
        assert result.success is True
        assert result.data == 1

    def test_modulo_by_zero(self, calc):
        result = calc.execute("5 % 0")
        assert result.success is False

    # ── Error cases ──
    def test_empty_input(self, calc):
        result = calc.execute("")
        assert result.success is False
        assert "nhập" in result.error.lower()

    def test_invalid_expression(self, calc):
        result = calc.execute("hello world")
        assert result.success is False
        assert "không hiểu" in result.error.lower() or "hỗ trợ" in result.error.lower()

    def test_whitespace_input(self, calc):
        result = calc.execute("   ")
        assert result.success is False

    def test_division_by_zero_modulo(self, calc):
        result = calc.execute("0 % 0")
        assert result.success is False

    def test_factorial_too_large(self, calc):
        result = calc.execute("101!")
        assert result.success is False
        assert "lớn" in result.error.lower()
