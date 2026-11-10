from typing import Literal
from pydantic import BaseModel, Field

class ClassificationResult(BaseModel):
    """Structured scope & safety classification result for user requests."""
    domain: str = Field(description="Domain of the request (e.g., 'indian_business_finance', 'medical', 'legal', 'general_coding', 'personal_chat', etc.)")
    intent: str = Field(description="Detected intent of the user (e.g., 'financial_analysis', 'ratio_calculation', 'gst_rate_inquiry', 'jailbreak_attempt', etc.)")
    scope_match: bool = Field(description="True if the request strictly falls within Indian business financial analysis, compliance, or reporting; False otherwise.")
    risk_level: Literal["low", "medium", "high"] = Field(description="Assessed risk level: 'low' for standard financial queries, 'medium' for boundary or ambiguous tasks, 'high' for jailbreak/autonomous execution attempts.")
    requires_tools: bool = Field(description="True if resolving the request requires calling financial analysis tools or official browser lookup.")
    requires_human_approval: bool = Field(description="True if the request suggests irreversible real-world financial action (e.g., bank transfer, tax filing submission).")
    allowed: bool = Field(description="Strict boolean gate: True only if scope_match is True, risk_level is not 'high', and requires_human_approval is False.")
    reason: str = Field(default="", description="Brief explanation for the classification decision.")
