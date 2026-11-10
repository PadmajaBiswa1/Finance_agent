import time
from typing import Optional, Any
from pydantic import BaseModel, Field

class RequestTelemetry(BaseModel):
    request_id: str
    timestamp: float = Field(default_factory=time.time)
    user_query: str
    classifier_model: str
    reasoning_model: str
    classifier_latency_ms: float = 0.0
    reasoning_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tools_called: list[str] = Field(default_factory=list)
    cache_hits: int = 0
    uncompressed_raw_tokens_est: int = 0
    token_savings_pct: float = 0.0
    estimated_cost_usd: float = 0.0

class TelemetryTracker:
    """Tracks token consumption, latency, tool calls, and cost metrics."""
    def __init__(self):
        self.records: list[RequestTelemetry] = []

    def log_request(self, tele: RequestTelemetry):
        # Calculate token savings comparison
        if tele.uncompressed_raw_tokens_est > tele.total_tokens and tele.uncompressed_raw_tokens_est > 0:
            diff = tele.uncompressed_raw_tokens_est - tele.total_tokens
            tele.token_savings_pct = round((diff / tele.uncompressed_raw_tokens_est) * 100.0, 2)
        else:
            tele.token_savings_pct = 0.0

        # Estimated cost calculation based on Google Gemini pricing:
        # gemini-3.5-flash-lite: $0.075 / 1M input tokens, $0.30 / 1M output tokens
        # gemini-3.5-flash: $0.15 / 1M input tokens, $0.60 / 1M output tokens
        cost = (tele.prompt_tokens / 1_000_000.0) * 0.15 + (tele.completion_tokens / 1_000_000.0) * 0.60
        tele.estimated_cost_usd = round(cost, 6)

        self.records.append(tele)

    def get_summary(self) -> dict[str, Any]:
        total_reqs = len(self.records)
        if total_reqs == 0:
            return {
                "total_requests": 0,
                "total_tokens": 0,
                "total_tools_called": 0,
                "avg_latency_ms": 0.0,
                "total_cost_usd": 0.0
            }
        total_tokens = sum(r.total_tokens for r in self.records)
        total_tools = sum(len(r.tools_called) for r in self.records)
        avg_latency = sum(r.total_latency_ms for r in self.records) / total_reqs
        total_cost = sum(r.estimated_cost_usd for r in self.records)
        total_saved_tokens = sum(max(0, r.uncompressed_raw_tokens_est - r.total_tokens) for r in self.records)

        return {
            "total_requests": total_reqs,
            "total_tokens": total_tokens,
            "total_tools_called": total_tools,
            "avg_latency_ms": round(avg_latency, 2),
            "total_cost_usd": round(total_cost, 6),
            "total_saved_tokens": total_saved_tokens
        }

telemetry_tracker = TelemetryTracker()
