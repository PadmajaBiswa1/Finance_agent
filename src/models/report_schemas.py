from typing import Literal, Union, Any, Optional
from pydantic import BaseModel, Field
from src.models.financial_schemas import (
    ProfitMetricsResult,
    FinancialRatiosResult,
    PeriodComparisonResult,
    ConsistencyCheckResult,
    NormalizedLineItem,
)

class FinancialReportSection(BaseModel):
    title: str
    content_markdown: str
    data_table: Optional[list[dict[str, Any]]] = None

class FinancialReportOutput(BaseModel):
    status: Literal["ok", "error"] = "ok"
    report_id: str
    title: str
    business_name: Optional[str] = "Indian SME Enterprise"
    currency: str = "INR (₹)"
    period: str
    generation_timestamp: str
    executive_summary: str
    assumptions: list[str] = Field(default_factory=list)
    formulas_used: dict[str, str] = Field(default_factory=dict)
    source_references: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of sources mapping metrics to file, sheet/page, and row"
    )
    profit_metrics: Optional[ProfitMetricsResult] = None
    financial_ratios: Optional[FinancialRatiosResult] = None
    period_comparison: Optional[PeriodComparisonResult] = None
    consistency_checks: Optional[ConsistencyCheckResult] = None
    line_items: list[NormalizedLineItem] = Field(default_factory=list)
    data_quality_warnings: list[str] = Field(default_factory=list)
    download_url_html: Optional[str] = None
    download_url_markdown: Optional[str] = None
    download_url_json: Optional[str] = None
