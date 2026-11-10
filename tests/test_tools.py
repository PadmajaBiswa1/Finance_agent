import pytest
from decimal import Decimal
from pathlib import Path

from src.models.financial_schemas import (
    FileValidationResult,
    ExtractedFinancialData,
    NormalizedFinancialStatement,
    ProfitMetricsResult,
    FinancialRatiosResult,
    PeriodComparisonResult,
    ConsistencyCheckResult,
    NormalizedLineItem,
    ErrorObject,
)
from src.models.report_schemas import FinancialReportOutput
from src.tools.file_tools import validate_financial_file_tool, extract_financial_data_tool
from src.tools.normalize_tools import normalize_financial_items_tool
from src.tools.calculation_tools import (
    calculate_profit_metrics_tool,
    calculate_ratios_tool,
    compare_periods_tool,
)
from src.tools.consistency_tools import check_financial_consistency_tool
from src.tools.report_tools import generate_financial_report_tool
from src.tools.browser_tools import fetch_official_source_tool, is_domain_allowed
from src.tools.currency_utils import parse_indian_decimal, format_inr
from src.config import settings

def test_indian_currency_utils():
    """Verify Indian numbering, grouping, and accounting brackets."""
    assert parse_indian_decimal("2,50,00,000.00") == Decimal("25000000.00")
    assert parse_indian_decimal("₹ 15,450.50") == Decimal("15450.50")
    assert parse_indian_decimal("(50,000)") == Decimal("-50000")
    assert parse_indian_decimal("-1,25,000") == Decimal("-125000")
    assert parse_indian_decimal("N/A") == "unavailable"
    assert parse_indian_decimal("") == "unavailable"

    assert format_inr(Decimal("25000000.00")) == "₹ 2,50,00,000.00"
    assert format_inr(Decimal("-50000.00")) == "-₹ 50,000.00"
    assert format_inr("unavailable") == "unavailable"

def test_validate_financial_file_success():
    pnl_path = settings.data_dir / "samples" / "sample_sme_pnl_fy24.csv"
    res = validate_financial_file_tool(str(pnl_path))
    assert isinstance(res, FileValidationResult)
    assert res.is_valid is True
    assert res.file_type == "csv"
    assert len(res.sha256_hash) == 64

def test_validate_financial_file_nonexistent():
    res = validate_financial_file_tool("nonexistent_statement.xlsx")
    assert isinstance(res, ErrorObject)
    assert res.error_code == "FILE_NOT_FOUND"

def test_extract_financial_data_csv():
    pnl_path = settings.data_dir / "samples" / "sample_sme_pnl_fy24.csv"
    res = extract_financial_data_tool(str(pnl_path))
    assert isinstance(res, ExtractedFinancialData)
    assert res.status == "ok"
    assert len(res.tables) >= 1
    rows = res.tables[0].rows
    assert len(rows) > 5

def test_extract_financial_data_xlsx():
    bs_path = settings.data_dir / "samples" / "sample_sme_balancesheet_fy24.xlsx"
    res = extract_financial_data_tool(str(bs_path))
    assert isinstance(res, ExtractedFinancialData)
    assert res.status == "ok"
    assert len(res.tables) >= 1

def test_normalize_financial_items():
    pnl_path = settings.data_dir / "samples" / "sample_sme_pnl_fy24.csv"
    ext_res = extract_financial_data_tool(str(pnl_path))
    assert isinstance(ext_res, ExtractedFinancialData)

    norm_res = normalize_financial_items_tool(ext_res, statement_type="P&L", period="FY 2023-24")
    assert isinstance(norm_res, NormalizedFinancialStatement)
    assert norm_res.status == "ok"
    canonical_names = [i.canonical_name for i in norm_res.items]
    assert "Revenue from Operations" in canonical_names
    assert "Cost of Materials Consumed" in canonical_names
    assert "Employee Benefit Expenses" in canonical_names

def test_calculate_profit_metrics_hand_verified(sample_sme_pnl_items):
    res = calculate_profit_metrics_tool(sample_sme_pnl_items, period="FY 2023-24")
    assert isinstance(res, ProfitMetricsResult)
    assert res.status == "ok"
    # Gross Profit = 25000000 - 14000000 = 11000000
    assert res.gross_profit == Decimal("11000000.00")
    # Operating Expenses (excl depr) = 14000000 + 3500000 + 2000000 = 19500000
    # EBITDA = (25000000 + 500000) - 19500000 = 6000000
    assert res.ebitda == Decimal("6000000.00")
    # EBIT = 6000000 - 700000 = 5300000
    assert res.ebit == Decimal("5300000.00")
    # Reported PBT = 4000000
    assert res.ebt == Decimal("4000000.00")
    # Reported PAT = 3000000
    assert res.pat == Decimal("3000000.00")

def test_calculate_profit_metrics_missing_revenue():
    incomplete_items = [
        NormalizedLineItem(canonical_name="Employee Benefit Expenses", raw_label="Salaries", amount=Decimal("500000"), period="FY24", source_file="a.csv", source_sheet_or_page="p1", source_row=1)
    ]
    res = calculate_profit_metrics_tool(incomplete_items)
    assert isinstance(res, ProfitMetricsResult)
    assert res.gross_profit == "unavailable"
    assert res.ebitda == "unavailable"
    assert "Revenue from Operations" in res.missing_fields

def test_calculate_ratios_hand_verified(sample_sme_bs_items, sample_sme_pnl_items):
    pm = calculate_profit_metrics_tool(sample_sme_pnl_items)
    res = calculate_ratios_tool(sample_sme_bs_items, profit_metrics=pm, period="FY 2023-24")
    assert isinstance(res, FinancialRatiosResult)
    assert res.status == "ok"

    # Current Ratio = 6000000 / 4000000 = 1.50
    assert res.current_ratio == Decimal("1.50")
    # Quick Ratio = (6000000 - 2500000) / 4000000 = 3500000 / 4000000 = 0.88
    assert res.quick_ratio == Decimal("0.88")
    # Debt to Equity = (3000000 + 1000000) / 8000000 = 0.50
    assert res.debt_to_equity == Decimal("0.50")
    # Working Capital = 6000000 - 4000000 = 2000000
    assert res.working_capital == Decimal("2000000.00")
    # Gross Margin % = (11000000 / 25000000) * 100 = 44.00%
    assert res.gross_margin_pct == Decimal("44.00")
    # Net Profit Margin % = (3000000 / 25000000) * 100 = 12.00%
    assert res.net_profit_margin_pct == Decimal("12.00")

def test_compare_periods_hand_verified(sample_sme_pnl_items, sample_sme_prior_year_items):
    res = compare_periods_tool(
        period_a_items=sample_sme_prior_year_items,
        period_b_items=sample_sme_pnl_items,
        period_a="FY 2022-23",
        period_b="FY 2023-24"
    )
    assert isinstance(res, PeriodComparisonResult)
    assert res.status == "ok"

    rev_comp = next((c for c in res.comparisons if c.metric_name == "Revenue from Operations"), None)
    assert rev_comp is not None
    # 25,000,000 - 20,000,000 = +5,000,000 (+25.00%)
    assert rev_comp.variance_abs == Decimal("5000000.00")
    assert rev_comp.variance_pct == Decimal("25.00")
    assert rev_comp.favorable is True

def test_check_financial_consistency_passed(sample_sme_bs_items, sample_sme_pnl_items):
    all_items = sample_sme_bs_items + sample_sme_pnl_items
    res = check_financial_consistency_tool(all_items, period="FY 2023-24")
    assert isinstance(res, ConsistencyCheckResult)
    assert res.status == "ok"
    assert res.all_passed is True
    # Balance sheet equality check must be PASSED
    bs_check = next(c for c in res.checks if c.check_name == "Balance Sheet Equality")
    assert bs_check.status == "PASSED"
    assert bs_check.discrepancy == Decimal("0")

def test_check_financial_consistency_failed_imbalance(sample_sme_bs_items):
    # Alter Total Assets to create intentional ₹ 10 Lakh imbalance
    corrupted_items = []
    for item in sample_sme_bs_items:
        if item.canonical_name == "Total Assets":
            corrupted_items.append(NormalizedLineItem(
                canonical_name="Total Assets",
                raw_label="Total Assets",
                amount=Decimal("16000000.00"),  # 1.6 Cr instead of 1.5 Cr
                period="FY 2023-24",
                source_file="bs.xlsx",
                source_sheet_or_page="BS",
                source_row=26
            ))
        else:
            corrupted_items.append(item)

    res = check_financial_consistency_tool(corrupted_items, period="FY 2023-24")
    assert isinstance(res, ConsistencyCheckResult)
    assert res.all_passed is False
    bs_check = next(c for c in res.checks if c.check_name == "Balance Sheet Equality")
    assert bs_check.status == "FAILED"
    assert bs_check.discrepancy == Decimal("1000000.00")
    assert len(res.data_quality_warnings) > 0

def test_generate_financial_report(sample_sme_pnl_items, sample_sme_bs_items):
    stmt = NormalizedFinancialStatement(
        status="ok",
        statement_type="Mixed",
        period="FY 2023-24",
        currency="INR",
        unit_multiplier=Decimal("1.0"),
        unit_label="Rupees",
        items=sample_sme_pnl_items + sample_sme_bs_items
    )
    res = generate_financial_report_tool(stmt, business_name="Bharat Precision Auto Pvt Ltd")
    assert isinstance(res, FinancialReportOutput)
    assert res.status == "ok"
    assert res.currency == "INR (₹)"
    assert res.period == "FY 2023-24"
    assert len(res.source_references) > 0
    assert res.download_url_html.startswith("/reports/")

    # Check files exist on disk
    html_file = settings.reports_dir / f"{res.report_id}.html"
    md_file = settings.reports_dir / f"{res.report_id}.md"
    json_file = settings.reports_dir / f"{res.report_id}.json"
    assert html_file.exists()
    assert md_file.exists()
    assert json_file.exists()

def test_browser_allowlist_domain_filtering():
    assert is_domain_allowed("https://rbi.org.in/scripts/BS_CircularIndexDisplay.aspx") is True
    assert is_domain_allowed("https://www.gst.gov.in/newsandupdates") is True
    assert is_domain_allowed("https://incometax.gov.in/iec/foportal") is True
    assert is_domain_allowed("https://mca.gov.in") is True
    assert is_domain_allowed("https://icai.org") is True
    assert is_domain_allowed("https://sebi.gov.in") is True

    # Disallowed domains
    assert is_domain_allowed("https://google.com") is False
    assert is_domain_allowed("https://attacker.evil.com/rbi.org.in") is False
    assert is_domain_allowed("https://facebook.com") is False

def test_fetch_official_source_disallowed_domain():
    res = fetch_official_source_tool("https://wikipedia.org/wiki/Finance")
    assert isinstance(res, ErrorObject)
    assert res.error_code == "DOMAIN_NOT_ALLOWED"
