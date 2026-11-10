import re
from typing import Tuple, List
from src.guardrails.redactor import redact_sensitive_info

LEAKAGE_INDICATORS = [
    re.compile(r"CLASSIFIER_PROMPT", re.IGNORECASE),
    re.compile(r"PROMPT_INJECTION", re.IGNORECASE),
    re.compile(r"IN_SCOPE_SIGNALS", re.IGNORECASE),
    re.compile(r"settings\.gemini_api_key", re.IGNORECASE),
    re.compile(r"AQ\.[A-Za-z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"AIza[0-9A-Za-z-_]{35}", re.IGNORECASE),
]

FALSE_COMPLETION_PATTERNS = [
    (re.compile(r"i\s+have\s+(transferred|sent|wired)\s+(the\s+)?(funds?|money|rupees)", re.IGNORECASE), "FALSE_CLAIM_TRANSFER"),
    (re.compile(r"i\s+have\s+(filed|submitted)\s+(your\s+)?(gst|itr|income\s+tax)\s+(return|form)", re.IGNORECASE), "FALSE_CLAIM_FILING"),
    (re.compile(r"i\s+have\s+(paid|debited)\s+(your\s+)?(bill|vendor|account)", re.IGNORECASE), "FALSE_CLAIM_PAYMENT"),
]

def check_output_guard(
    agent_output: str,
    had_tool_execution: bool = False,
    is_refusal: bool = False
) -> Tuple[bool, str, List[str]]:
    """
    Validates and sanitizes agent output:
    1. Blocks system prompt or API key leakage.
    2. Blocks false claims of completed real-world financial actions.
    3. Enforces that financial analyses state currency (INR / ₹) and reporting period.
    4. Redacts any accidental PII or credentials.
    """
    violations = []
    text = agent_output.strip()

    # Redact any PII or secrets first
    sanitized = redact_sensitive_info(text)

    # 1. Leakage check
    for pat in LEAKAGE_INDICATORS:
        if pat.search(sanitized):
            violations.append("SYSTEM_PROMPT_OR_KEY_LEAKAGE")
            return (
                False,
                "Response withheld: internal system information or credential detected.",
                violations
            )

    # 2. False execution check
    for pat, label in FALSE_COMPLETION_PATTERNS:
        if pat.search(sanitized):
            violations.append(label)
            return (
                False,
                "Response modified: The agent cannot execute bank transfers or statutory filings.",
                violations
            )

    # 3. Currency and Period verification for financial responses
    if not is_refusal:
        # Check if output contains large monetary figures or ratio assertions
        has_monetary_numbers = bool(re.search(r"\b\d{4,}\b|\b\d{1,2},\d{2},\d{3}\b", sanitized))
        has_currency_mention = bool(re.search(r"(₹|inr|rs\.?|rupees|lakhs?|crores?)", sanitized, re.IGNORECASE))
        has_period_mention = bool(re.search(r"(fy\s*20\d\d|q[1-4]|period|year|annual|quarter)", sanitized, re.IGNORECASE))

        if has_monetary_numbers and not has_currency_mention:
            # Append standard currency clarification
            sanitized += "\n\n*(Note: All monetary amounts are stated in Indian National Rupees [INR / ₹].)*"

        if has_monetary_numbers and not has_period_mention and not had_tool_execution:
            sanitized += "\n*(Reporting Period: Please refer to the specific financial period analyzed.)*"

    return True, sanitized, violations
