import re
from typing import Any

# PII and Secret Regexes
PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
AADHAAR_REGEX = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
PHONE_REGEX = re.compile(r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
BANK_ACCOUNT_REGEX = re.compile(r"\b\d{9,18}\b")
API_KEY_REGEX = re.compile(r"\b(AIza[0-9A-Za-z-_]{35}|AQ\.[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9\._\-]+)\b")
PASSWORD_REGEX = re.compile(r"(password|secret|token)\s*[:=]\s*['\"]?([^\s'\"]+)['\"]?", re.IGNORECASE)

def redact_sensitive_info(text: Any) -> str:
    """
    Redacts Indian PII (PAN, Aadhaar, Phone, Email, Bank Accounts)
    and secrets (API keys, tokens, passwords) from text and logs.
    """
    if text is None:
        return ""
    s = str(text)

    # Secrets first
    s = API_KEY_REGEX.sub("[REDACTED_SECRET_KEY]", s)
    s = PASSWORD_REGEX.sub(r"\1: [REDACTED_CREDENTIAL]", s)

    # Indian PII
    s = PAN_REGEX.sub("[REDACTED_PAN]", s)
    s = AADHAAR_REGEX.sub("[REDACTED_AADHAAR]", s)
    s = PHONE_REGEX.sub("[REDACTED_PHONE]", s)
    s = EMAIL_REGEX.sub("[REDACTED_EMAIL]", s)
    
    return s
