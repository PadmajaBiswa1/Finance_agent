import re
from decimal import Decimal, InvalidOperation
from typing import Union

INDIAN_NUMBER_REGEX = re.compile(r"^\s*[-+]?\s*₹?\s*(\d{1,2}(,\d{2})*|\d+)(\.\d+)?\s*$")

def parse_indian_decimal(val: Union[str, int, float, Decimal, None]) -> Union[Decimal, str]:
    """
    Parses a string or number into Python Decimal.
    Supports:
    - Standard numbers: 123456.78
    - Indian grouping: 12,34,567.89
    - Currency symbols: ₹ 50,000
    - Negative accounting notation: (1,50,000) or -1,50,000
    - Returns 'unavailable' if val is None, empty, or unparseable.
    """
    if val is None:
        return "unavailable"
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))

    text = str(val).strip().strip("'\"")
    if not text or text.lower() in ("-", "na", "n/a", "nil", "none", "null", "unavailable", ""):
        return "unavailable"

    # Check for negative accounting brackets, e.g. (1,50,000) or -1,50,000
    is_negative = False
    if text.startswith("(") and text.endswith(")"):
        is_negative = True
        text = text[1:-1].strip()
    elif text.startswith("-"):
        is_negative = True
        text = text[1:].strip()
    elif text.startswith("'-"):
        is_negative = True
        text = text[2:].strip()

    # Strip currency symbols and whitespace
    text = text.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace("INR", "").strip()
    # Strip commas used in grouping
    text = text.replace(",", "").strip()

    try:
        dec = Decimal(text)
        return -dec if is_negative else dec
    except (InvalidOperation, ValueError):
        return "unavailable"

def format_inr(val: Union[Decimal, str, int, float, None], decimals: int = 2) -> str:
    """
    Formats a Decimal number into Indian numbering system: ₹ XX,XX,XXX.YY
    """
    if val is None or val == "unavailable":
        return "unavailable"
    try:
        dec = Decimal(str(val))
    except (InvalidOperation, ValueError):
        return "unavailable"

    is_neg = dec < 0
    dec = abs(dec)
    
    # Quantize to desired decimals
    pattern = "0." + "0" * decimals if decimals > 0 else "0"
    dec_str = f"{dec:.{decimals}f}"
    
    if "." in dec_str:
        integer_part, frac_part = dec_str.split(".")
    else:
        integer_part, frac_part = dec_str, ""

    # Indian grouping: last 3 digits, then groups of 2
    if len(integer_part) > 3:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while remaining:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        formatted_int = ",".join(groups) + "," + last_three
    else:
        formatted_int = integer_part

    res = f"₹ {formatted_int}"
    if frac_part:
        res += f".{frac_part}"
    if is_neg:
        res = f"-{res}"
    return res
