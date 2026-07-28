"""
Currency & Unit Converter Plugin — chuyển đổi tiền tệ và đơn vị đo lường (Feature 29).

Sử dụng tỷ giá hối đoái hardcode (cập nhật định kỳ) cho tiền tệ,
và công thức chuyển đổi chuẩn cho các đơn vị đo lường.

Usage:
    "100 USD to VND"
    "50 EUR to GBP"
    "1 inch to cm"
    "100 độ F sang độ C"
    "5 kg to lbs"
    "đổi 100 đô la sang việt nam đồng"
"""

import re
from typing import Optional, Union

from src.plugin import BasePlugin, PluginResult


# ============================================================
# Exchange Rates (hardcoded, approximate)
# ============================================================
# Base: USD

EXCHANGE_RATES: dict[str, float] = {
    "USD": 1.0,
    "VND": 25450.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 153.0,
    "CNY": 7.25,
    "KRW": 1380.0,
    "SGD": 1.35,
    "MYR": 4.70,
    "THB": 36.5,
    "AUD": 1.54,
    "CAD": 1.37,
    "CHF": 0.90,
    "INR": 83.5,
    "RUB": 92.0,
    "BRL": 5.15,
    "ZAR": 18.5,
    "PHP": 57.0,
    "IDR": 16200.0,
    "HKD": 7.82,
    "TWD": 32.5,
    "NZD": 1.67,
    "SEK": 10.8,
    "NOK": 11.0,
    "DKK": 6.9,
    "PLN": 4.05,
    "TRY": 33.0,
    "SAR": 3.75,
    "AED": 3.67,
    "MXN": 18.5,
}

CURRENCY_NAMES: dict[str, str] = {
    "USD": "Đô la Mỹ",
    "VND": "Việt Nam Đồng",
    "EUR": "Euro",
    "GBP": "Bảng Anh",
    "JPY": "Yên Nhật",
    "CNY": "Nhân dân tệ",
    "KRW": "Won Hàn Quốc",
    "SGD": "Đô la Singapore",
    "MYR": "Ringgit Malaysia",
    "THB": "Baht Thái Lan",
    "AUD": "Đô la Úc",
    "CAD": "Đô la Canada",
    "CHF": "Franc Thụy Sĩ",
    "INR": "Rupee Ấn Độ",
    "RUB": "Ruble Nga",
    "BRL": "Real Brazil",
    "ZAR": "Rand Nam Phi",
    "PHP": "Peso Philippines",
    "IDR": "Rupiah Indonesia",
    "HKD": "Đô la Hồng Kông",
    "TWD": "Đô la Đài Loan",
    "NZD": "Đô la New Zealand",
    "SEK": "Krona Thụy Điển",
    "NOK": "Krone Na Uy",
    "DKK": "Krone Đan Mạch",
    "PLN": "Zloty Ba Lan",
    "TRY": "Lira Thổ Nhĩ Kỳ",
    "SAR": "Riyal Ả Rập",
    "AED": "Dirham UAE",
    "MXN": "Peso Mexico",
}

# Aliases for common names
CURRENCY_ALIASES: dict[str, str] = {
    "đô la": "USD",
    "đô": "USD",
    "usd": "USD",
    "dollar": "USD",
    "việt nam đồng": "VND",
    "vnd": "VND",
    "đồng": "VND",
    "eur": "EUR",
    "euro": "EUR",
    "bảng anh": "GBP",
    "gbp": "GBP",
    "pound": "GBP",
    "yên nhật": "JPY",
    "jpy": "JPY",
    "yen": "JPY",
    "nhân dân tệ": "CNY",
    "cny": "CNY",
    "yuan": "CNY",
    "won": "KRW",
    "krw": "KRW",
}


# ============================================================
# Unit Conversions
# ============================================================

UNIT_CONVERSIONS: dict[str, dict] = {
    # Length
    "inch_to_cm": {"factor": 2.54, "from": "inch", "to": "cm", "category": "Chiều dài"},
    "cm_to_inch": {"factor": 0.3937, "from": "cm", "to": "inch", "category": "Chiều dài"},
    "foot_to_m": {"factor": 0.3048, "from": "foot", "to": "m", "category": "Chiều dài"},
    "m_to_foot": {"factor": 3.28084, "from": "m", "to": "foot", "category": "Chiều dài"},
    "yard_to_m": {"factor": 0.9144, "from": "yard", "to": "m", "category": "Chiều dài"},
    "km_to_mile": {"factor": 0.621371, "from": "km", "to": "mile", "category": "Chiều dài"},
    "mile_to_km": {"factor": 1.60934, "from": "mile", "to": "km", "category": "Chiều dài"},
    # Weight
    "kg_to_lb": {"factor": 2.20462, "from": "kg", "to": "lb", "category": "Khối lượng"},
    "lb_to_kg": {"factor": 0.453592, "from": "lb", "to": "kg", "category": "Khối lượng"},
    "g_to_oz": {"factor": 0.035274, "from": "g", "to": "oz", "category": "Khối lượng"},
    "oz_to_g": {"factor": 28.3495, "from": "oz", "to": "g", "category": "Khối lượng"},
    # Temperature
    "c_to_f": {"formula": "c * 9/5 + 32", "from": "°C", "to": "°F", "category": "Nhiệt độ"},
    "f_to_c": {"formula": "(f - 32) * 5/9", "from": "°F", "to": "°C", "category": "Nhiệt độ"},
    # Volume
    "l_to_gal": {"factor": 0.264172, "from": "L", "to": "gal", "category": "Thể tích"},
    "gal_to_l": {"factor": 3.78541, "from": "gal", "to": "L", "category": "Thể tích"},
    "ml_to_floz": {"factor": 0.033814, "from": "mL", "to": "fl oz", "category": "Thể tích"},
    # Area
    "sqm_to_sqft": {"factor": 10.7639, "from": "m²", "to": "ft²", "category": "Diện tích"},
    "ha_to_acre": {"factor": 2.47105, "from": "ha", "to": "acre", "category": "Diện tích"},
}


def _is_currency_query(text: str) -> bool:
    """Detect currency conversion patterns."""
    lowered = text.lower().strip()
    patterns = [
        r"\d+\s*(?:usd|vnd|eur|gbp|jpy|cny|krw|sgd|thb|aud|cad|chf|inr)\s+(?:to|to|sang|->)\s+",
        r"\d+\s*(?:đô|đô la|bảng anh|euro|yên|won)\s+(?:to|sang|->)\s+",
        r"(?:đổi|convert|change|quy đổi|chuyển)\s+",
        r"(?:bao nhiêu|how much)\s+.+\s+(?:to|sang|in|bằng)",
    ]
    for pattern in patterns:
        if re.search(pattern, lowered):
            return True
    # Check for currency code patterns
    currency_codes = r"\b(USD|VND|EUR|GBP|JPY|CNY|KRW|SGD|THB|AUD|CAD|CHF|INR)\b"
    if re.search(r"\d+\s+" + currency_codes, lowered, re.IGNORECASE):
        return True
    return False


def _is_unit_query(text: str) -> bool:
    """Detect unit conversion patterns."""
    lowered = text.lower().strip()
    patterns = [
        r"\d+\s*(?:inch|cm|mm|m|km|mile|foot|yard|kg|g|lb|oz|°[cf]|l|ml|gal|ha|m²)\s+(?:to|sang|->|in)\s+",
        r"(?:đổi|convert|change|chuyển)\s+\d+",
        r"\d+\s*(?:độ|degree)\s+[cf]\s+(?:sang|to)\s+",
    ]
    for pattern in patterns:
        if re.search(pattern, lowered):
            return True
    return False


def _parse_currency_input(text: str) -> Optional[dict]:
    """Parse currency conversion input: '100 USD to VND' => {amount, from, to}"""
    lowered = text.lower().strip()
    
    # Pattern: [amount] [from_currency] to [to_currency]
    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*([a-zàáãạảăắằặẵấầẫẩđéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ]+)\s+(?:to|sang|->|in|thành|ra)\s+([a-zàáãạảăắằặẵấầẫẩđéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ]+)",
        lowered,
    )
    
    if match:
        amount_str = match.group(1).replace(",", ".")
        amount = float(amount_str)
        from_curr = match.group(2).strip()
        to_curr = match.group(3).strip()
        
        # Resolve aliases
        from_code = CURRENCY_ALIASES.get(from_curr, from_curr.upper())
        to_code = CURRENCY_ALIASES.get(to_curr, to_curr.upper())
        
        if from_code in EXCHANGE_RATES and to_code in EXCHANGE_RATES:
            return {"amount": amount, "from": from_code, "to": to_code, "type": "currency"}
    
    return None


def _parse_unit_input(text: str) -> Optional[dict]:
    """Parse unit conversion input."""
    lowered = text.lower().strip()
    
    for key, info in UNIT_CONVERSIONS.items():
        from_unit = info["from"].lower()
        to_unit = info["to"].lower()
        
        # Pattern: [amount] [from_unit] to [to_unit]
        match = re.search(
            rf"(\d+(?:[.,]\d+)?)\s*{re.escape(from_unit)}\s+(?:to|sang|->|in|thành|ra)\s+{re.escape(to_unit)}",
            lowered,
        )
        if match:
            amount = float(match.group(1).replace(",", "."))
            return {"amount": amount, "key": key, "info": info, "type": "unit"}
        
        # Pattern for temperature: [amount] degree C to F
        if "°" in from_unit:
            match = re.search(
                rf"(\d+(?:[.,]\d+)?)\s*(?:độ|degree|°)?\s*{re.escape(from_unit.replace('°', ''))}\s+(?:sang|to)\s+{re.escape(to_unit.replace('°', ''))}",
                lowered,
            )
            if match:
                amount = float(match.group(1).replace(",", "."))
                return {"amount": amount, "key": key, "info": info, "type": "unit"}
    
    return None


def _convert_currency(amount: float, from_curr: str, to_curr: str) -> float:
    """Convert between currencies using hardcoded rates."""
    usd_amount = amount / EXCHANGE_RATES[from_curr]
    result = usd_amount * EXCHANGE_RATES[to_curr]
    return result


def _convert_unit(amount: float, info: dict) -> float:
    """Convert between units."""
    if "factor" in info:
        return amount * info["factor"]
    elif "formula" in info:
        formula = info["formula"]
        if "c * 9/5 + 32" in formula:
            return amount * 9/5 + 32
        elif "(f - 32) * 5/9" in formula:
            return (amount - 32) * 5/9
    return amount


def _format_number(n: float) -> str:
    """Format a number nicely."""
    if n == int(n):
        return f"{int(n):,}".replace(",", ".")
    if n < 0.01:
        return f"{n:.6f}"
    if n < 1:
        return f"{n:.4f}"
    if n < 100:
        return f"{n:.2f}"
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class CurrencyConverterPlugin(BasePlugin):
    """
    Chuyển đổi tiền tệ và đơn vị đo lường.
    
    Hỗ trợ 30+ loại tiền tệ (tỷ giá hardcode) và các đơn vị:
    chiều dài, khối lượng, nhiệt độ, thể tích, diện tích.
    
    Examples:
        "100 USD to VND"
        "50 EUR to GBP"
        "1 inch to cm"
        "100 độ F sang độ C"
        "5 kg to lbs"
        "đổi 100 đô la sang việt nam đồng"
    """
    
    name = "converter"
    description = "Chuyển đổi tiền tệ (30+ loại) và đơn vị đo lường"
    
    def execute(self, input_str: str) -> PluginResult:
        """Parse input and perform conversion."""
        text = input_str.strip()
        
        if not text:
            return PluginResult(
                success=False,
                error="Vui lòng nhập phép chuyển đổi. Ví dụ: 100 USD to VND",
            )
        
        # Try currency first
        if _is_currency_query(text):
            parsed = _parse_currency_input(text)
            if parsed:
                amount = parsed["amount"]
                from_c = parsed["from"]
                to_c = parsed["to"]
                result = _convert_currency(amount, from_c, to_c)
                
                from_name = CURRENCY_NAMES.get(from_c, from_c)
                to_name = CURRENCY_NAMES.get(to_c, to_c)
                
                output = (
                    f"## 💱 Chuyển đổi tiền tệ\n\n"
                    f"| | Giá trị |\n"
                    f"|---|---|\n"
                    f"| {from_name} ({from_c}) | **{_format_number(amount)}** |\n"
                    f"| {to_name} ({to_c}) | **{_format_number(result)}** |\n"
                    f"| Tỷ giá | 1 {from_c} = {_format_number(result/amount)} {to_c} |\n\n"
                    f"---\n"
                    f"*💡 Tỷ giá tham khảo, cập nhật định kỳ*"
                )
                
                return PluginResult(
                    success=True,
                    output=output,
                    data={
                        "type": "currency",
                        "from": from_c,
                        "to": to_c,
                        "amount": amount,
                        "result": result,
                    },
                )
            else:
                return PluginResult(
                    success=False,
                    error="Không thể phân tích yêu cầu chuyển đổi tiền tệ. "
                          "Ví dụ: 100 USD to VND",
                )
        
        # Try unit conversion
        if _is_unit_query(text):
            parsed = _parse_unit_input(text)
            if parsed:
                info = parsed["info"]
                amount = parsed["amount"]
                result = _convert_unit(amount, info)
                
                output = (
                    f"## 📐 Chuyển đổi đơn vị\n\n"
                    f"| | Giá trị |\n"
                    f"|---|---|\n"
                    f"| {info['from']} | **{_format_number(amount)}** |\n"
                    f"| {info['to']} | **{_format_number(result)}** |\n"
                    f"| Loại | {info['category']} |\n"
                )
                
                return PluginResult(
                    success=True,
                    output=output,
                    data={
                        "type": "unit",
                        "category": info["category"],
                        "from_unit": info["from"],
                        "to_unit": info["to"],
                        "amount": amount,
                        "result": result,
                    },
                )
            else:
                return PluginResult(
                    success=False,
                    error="Không thể phân tích yêu cầu chuyển đổi đơn vị. "
                          "Ví dụ: 1 inch to cm",
                )
        
        # Not a conversion query
        return PluginResult(
            success=False,
            error=(
                "Vui lòng nhập phép chuyển đổi.\n\n"
                "**Ví dụ tiền tệ:**\n"
                "  • `100 USD to VND`\n"
                "  • `50 EUR sang GBP`\n"
                "  • `đổi 100 đô la sang việt nam đồng`\n\n"
                "**Ví dụ đơn vị:**\n"
                "  • `1 inch to cm`\n"
                "  • `100 độ F sang độ C`\n"
                "  • `5 kg to lbs`"
            ),
        )
