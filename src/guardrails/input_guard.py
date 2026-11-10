import re
from typing import Tuple, List

MAX_INPUT_LENGTH = 8000

INJECTION_PATTERNS = [
    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE), "PROMPT_INJECTION_IGNORE_INSTRUCTIONS"),
    (re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE), "PROMPT_INJECTION_DISREGARD_INSTRUCTIONS"),
    (re.compile(r"you\s+are\s+now\s+(in\s+)?(DAN|developer|jailbreak|unrestricted|god)\s+mode", re.IGNORECASE), "PROMPT_INJECTION_JAILBREAK_MODE"),
    (re.compile(r"act\s+as\s+(an?\s+)?(unrestricted|unfiltered|jailbroken|DAN|evil)\s+ai", re.IGNORECASE), "PROMPT_INJECTION_ROLEPLAY"),
    (re.compile(r"repeat\s+(everything|the\s+text)\s+(above|from\s+the\s+beginning)", re.IGNORECASE), "SYSTEM_PROMPT_EXTRACTION"),
    (re.compile(r"print\s+(your\s+)?(initial|system|base)\s+(prompt|instructions)", re.IGNORECASE), "SYSTEM_PROMPT_EXTRACTION"),
    (re.compile(r"(reveal|show|display|leak)\s+(your\s+)?(system\s+prompt|secret\s+key|api\s+key)", re.IGNORECASE), "SYSTEM_PROMPT_EXTRACTION"),
    (re.compile(r"<\|im_(start|end)\|>", re.IGNORECASE), "DELIMITER_INJECTION"),
    (re.compile(r"\[/?(inst|system|sys|assistant)\]", re.IGNORECASE), "DELIMITER_INJECTION"),
]

AUTONOMOUS_ACTION_PATTERNS = [
    (re.compile(r"(transfer|send|wire)\s+(rs\.?|inr|₹)?\s*[\d,]+\s*(rupees)?\s+to", re.IGNORECASE), "AUTONOMOUS_TRANSFER"),
    (re.compile(r"(file|submit)\s+.*?\b(gst|gstr|itr|income\s+tax|tds)\b.*?\b(return|portal|form|filing)\b", re.IGNORECASE), "AUTONOMOUS_FILING"),
    (re.compile(r"(pay|disburse)\s+(vendor\s+)?(salary|vendor|tax|bill)", re.IGNORECASE), "AUTONOMOUS_PAYMENT"),
    (re.compile(r"(execute|authorize)\s+(a\s+)?(payment|bank\s+transfer|transaction)", re.IGNORECASE), "AUTONOMOUS_PAYMENT"),
]

def check_input_guard(user_text: str) -> Tuple[bool, str, List[str]]:
    """
    Validates user input against length limits, prompt-injection attempts,
    system-prompt extraction queries, and autonomous action execution.
    Returns (is_safe, reason, flags).
    """
    if not user_text or not user_text.strip():
        return False, "Input cannot be empty.", ["EMPTY_INPUT"]

    if len(user_text) > MAX_INPUT_LENGTH:
        return False, f"Input length exceeds maximum allowed limit of {MAX_INPUT_LENGTH} characters.", ["LENGTH_EXCEEDED"]

    flags = []

    # Check for autonomous execution attempts (strictly forbidden)
    for pat, flag in AUTONOMOUS_ACTION_PATTERNS:
        if pat.search(user_text):
            flags.append(flag)
            return (
                False,
                "I cannot execute real-world financial transactions, bank transfers, or statutory filings. I am an analytical advisory agent.",
                flags
            )

    # Check for prompt injection and system prompt extraction
    for pat, flag in INJECTION_PATTERNS:
        if pat.search(user_text):
            flags.append(flag)
            return (
                False,
                "The request contains unsafe prompt-injection or unauthorized system extraction instructions.",
                flags
            )

    return True, "Input passed validation.", []
