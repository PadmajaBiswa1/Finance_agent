from decimal import Decimal
from typing import Literal, Union, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

class ErrorObject(BaseModel):
    """Structured error object returned by all tools on failure, never raw unhandled exceptions."""
    status: Literal["error"] = "error"
    error_code: str = Field(description="Machine-readable error identifier (e.g. 'FILE_NOT_FOUND', 'INVALID_MAGIC_BYTES')")
    message: str = Field(description="Clear human-readable description of what went wrong")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context or diagnostics")

class FileValidationResult(BaseModel):
    status: Literal["ok", "error"] = "ok"
    filename: str
    file_type: Literal["csv", "xlsx", "pdf", "unknown"]
    file_size_bytes: int
    sha256_hash: str
    mime_type: str
    is_valid: bool
    validation_errors: list[str] = Field(default_factory=list)

class ExtractedRow(BaseModel):
    row_number: int
    raw_label: str
    values: list[str] = Field(default_factory=list)
    raw_cells: dict[str, str] = Field(default_factory=dict)

class ExtractedTable(BaseModel):
    sheet_or_page: str
    table_type: str = "financial_table"
    header: list[str] = Field(default_factory=list)
    rows: list[ExtractedRow] = Field(default_factory=list)

class ExtractedFinancialData(BaseModel):
    status: Literal["ok", "error"] = "ok"
    filename: str
    sha256_hash: str
    tables: list[ExtractedTable] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

class NormalizedLineItem(BaseModel):
    canonical_name: str = Field(description="Canonical financial item name (e.g., 'Revenue from Operations')")
    raw_label: str = Field(description="Original line item text from file")
    amount: Union[Decimal, str] = Field(description="Monetary amount in Decimal, or 'unavailable'")
    currency: str = "INR"
    period: str = Field(description="Financial period, e.g. 'FY 2023-24' or 'Q1 FY24'")
    source_file: str
    source_sheet_or_page: str
    source_row: int
    confidence: float = 1.0

    model_config = ConfigDict(arbitrary_types_allowed=True)

class NormalizedFinancialStatement(BaseModel):
    status: Literal["ok", "error"] = "ok"
    statement_type: Literal["P&L", "Balance Sheet", "Cash Flow", "Mixed"]
    period: str
    currency: str = "INR"
    unit_multiplier: Decimal = Decimal("1.0")  # 1.0 for absolute INR, 100000 for Lakhs, 10000000 for Crores
    unit_label: str = "INR"
    items: list[NormalizedLineItem] = Field(default_factory=list)
    unmapped_items: list[dict[str, Any]] = Field(default_factory=list)

class ProfitMetricsResult(BaseModel):
    status: Literal["ok", "error"] = "ok"
    currency: str = "INR"
    period: str
    revenue_from_operations: Union[Decimal, str]
    gross_profit: Union[Decimal, str]
    operating_profit: Union[Decimal, str]
    ebitda: Union[Decimal, str]
    ebit: Union[Decimal, str]
    ebt: Union[Decimal, str]
    pat: Union[Decimal, str]
    formulas_used: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

class FinancialRatiosResult(BaseModel):
    status: Literal["ok", "error"] = "ok"
    currency: str = "INR"
    period: str
    current_ratio: Union[Decimal, str]
    quick_ratio: Union[Decimal, str]
    debt_to_equity: Union[Decimal, str]
    gross_margin_pct: Union[Decimal, str]
    operating_margin_pct: Union[Decimal, str]
    ebitda_margin_pct: Union[Decimal, str]
    net_profit_margin_pct: Union[Decimal, str]
    working_capital: Union[Decimal, str]
    dscr: Union[Decimal, str]
    return_on_equity_pct: Union[Decimal, str]
    return_on_capital_employed_pct: Union[Decimal, str]
    formulas_used: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

class PeriodComparisonItem(BaseModel):
    metric_name: str
    period_a_value: Union[Decimal, str]
    period_b_value: Union[Decimal, str]
    variance_abs: Union[Decimal, str]
    variance_pct: Union[Decimal, str]
    favorable: Optional[bool] = None
    note: str = ""

class PeriodComparisonResult(BaseModel):
    status: Literal["ok", "error"] = "ok"
    period_a: str
    period_b: str
    currency: str = "INR"
    comparisons: list[PeriodComparisonItem] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

class ConsistencyCheckItem(BaseModel):
    check_name: str
    status: Literal["PASSED", "FAILED", "WARNING", "UNCHECKED"]
    left_expression: str
    left_value: Union[Decimal, str]
    right_expression: str
    right_value: Union[Decimal, str]
    discrepancy: Union[Decimal, str]
    explanation: str

class ConsistencyCheckResult(BaseModel):
    status: Literal["ok", "error"] = "ok"
    all_passed: bool
    checks: list[ConsistencyCheckItem] = Field(default_factory=list)
    summary: str
    data_quality_warnings: list[str] = Field(default_factory=list)
