import pytest
from decimal import Decimal
from pathlib import Path
from src.models.financial_schemas import NormalizedLineItem, NormalizedFinancialStatement

@pytest.fixture
def sample_sme_pnl_items() -> list[NormalizedLineItem]:
    """Hand-verified Indian SME P&L line items."""
    return [
        NormalizedLineItem(
            canonical_name="Revenue from Operations",
            raw_label="Revenue from Operations",
            amount=Decimal("25000000.00"),
            currency="INR",
            period="FY 2023-24",
            source_file="sample_sme_pnl_fy24.csv",
            source_sheet_or_page="sample_sme_pnl_fy24",
            source_row=2
        ),
        NormalizedLineItem(
            canonical_name="Other Income",
            raw_label="Other Income",
            amount=Decimal("500000.00"),
            currency="INR",
            period="FY 2023-24",
            source_file="sample_sme_pnl_fy24.csv",
            source_sheet_or_page="sample_sme_pnl_fy24",
            source_row=3
        ),
        NormalizedLineItem(
            canonical_name="Cost of Materials Consumed",
            raw_label="Cost of Materials Consumed",
            amount=Decimal("14000000.00"),
            currency="INR",
            period="FY 2023-24",
            source_file="sample_sme_pnl_fy24.csv",
            source_sheet_or_page="sample_sme_pnl_fy24",
            source_row=5
        ),
        NormalizedLineItem(
            canonical_name="Employee Benefit Expenses",
            raw_label="Employee Benefit Expenses",
            amount=Decimal("3500000.00"),
            currency="INR",
            period="FY 2023-24",
            source_file="sample_sme_pnl_fy24.csv",
            source_sheet_or_page="sample_sme_pnl_fy24",
            source_row=7
        ),
        NormalizedLineItem(
            canonical_name="Finance Costs",
            raw_label="Finance Costs",
            amount=Decimal("800000.00"),
            currency="INR",
            period="FY 2023-24",
            source_file="sample_sme_pnl_fy24.csv",
            source_sheet_or_page="sample_sme_pnl_fy24",
            source_row=8
        ),
        NormalizedLineItem(
            canonical_name="Depreciation & Amortization",
            raw_label="Depreciation & Amortization",
            amount=Decimal("700000.00"),
            currency="INR",
            period="FY 2023-24",
            source_file="sample_sme_pnl_fy24.csv",
            source_sheet_or_page="sample_sme_pnl_fy24",
            source_row=9
        ),
        NormalizedLineItem(
            canonical_name="Other Expenses",
            raw_label="Other Expenses",
            amount=Decimal("2000000.00"),
            currency="INR",
            period="FY 2023-24",
            source_file="sample_sme_pnl_fy24.csv",
            source_sheet_or_page="sample_sme_pnl_fy24",
            source_row=10
        ),
        NormalizedLineItem(
            canonical_name="Profit Before Tax (PBT)",
            raw_label="Profit Before Tax",
            amount=Decimal("4000000.00"),
            currency="INR",
            period="FY 2023-24",
            source_file="sample_sme_pnl_fy24.csv",
            source_sheet_or_page="sample_sme_pnl_fy24",
            source_row=12
        ),
        NormalizedLineItem(
            canonical_name="Tax Expense",
            raw_label="Tax Expense",
            amount=Decimal("1000000.00"),
            currency="INR",
            period="FY 2023-24",
            source_file="sample_sme_pnl_fy24.csv",
            source_sheet_or_page="sample_sme_pnl_fy24",
            source_row=13
        ),
        NormalizedLineItem(
            canonical_name="Profit After Tax (PAT)",
            raw_label="Profit After Tax",
            amount=Decimal("3000000.00"),
            currency="INR",
            period="FY 2023-24",
            source_file="sample_sme_pnl_fy24.csv",
            source_sheet_or_page="sample_sme_pnl_fy24",
            source_row=14
        ),
    ]

@pytest.fixture
def sample_sme_bs_items() -> list[NormalizedLineItem]:
    """Hand-verified Indian SME Balance Sheet line items."""
    return [
        NormalizedLineItem(canonical_name="Total Equity", raw_label="Total Equity", amount=Decimal("8000000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=7),
        NormalizedLineItem(canonical_name="Long-Term Borrowings", raw_label="Term Loan", amount=Decimal("3000000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=9),
        NormalizedLineItem(canonical_name="Short-Term Borrowings", raw_label="Bank Cash Credit", amount=Decimal("1000000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=11),
        NormalizedLineItem(canonical_name="Trade Payables", raw_label="Sundry Creditors", amount=Decimal("2500000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=12),
        NormalizedLineItem(canonical_name="Other Current Liabilities", raw_label="Statutory Dues", amount=Decimal("500000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=13),
        NormalizedLineItem(canonical_name="Total Current Liabilities", raw_label="Total Current Liabilities", amount=Decimal("4000000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=14),
        NormalizedLineItem(canonical_name="Total Liabilities and Equity", raw_label="Total Liabilities and Equity", amount=Decimal("15000000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=15),
        NormalizedLineItem(canonical_name="Property, Plant & Equipment", raw_label="Plant & Machinery", amount=Decimal("8500000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=18),
        NormalizedLineItem(canonical_name="Non-Current Assets", raw_label="Security Deposits", amount=Decimal("500000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=19),
        NormalizedLineItem(canonical_name="Inventories", raw_label="Stock in Trade", amount=Decimal("2500000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=21),
        NormalizedLineItem(canonical_name="Trade Receivables", raw_label="Sundry Debtors", amount=Decimal("2000000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=22),
        NormalizedLineItem(canonical_name="Cash and Cash Equivalents", raw_label="Bank Current A/c", amount=Decimal("1000000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=23),
        NormalizedLineItem(canonical_name="Short-Term Loans & Advances", raw_label="GST Input Credit", amount=Decimal("500000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=24),
        NormalizedLineItem(canonical_name="Total Current Assets", raw_label="Total Current Assets", amount=Decimal("6000000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=25),
        NormalizedLineItem(canonical_name="Total Assets", raw_label="Total Assets", amount=Decimal("15000000.00"), period="FY 2023-24", source_file="bs.xlsx", source_sheet_or_page="BS", source_row=26),
    ]

@pytest.fixture
def sample_sme_prior_year_items() -> list[NormalizedLineItem]:
    """Hand-verified FY 2022-23 line items for comparison."""
    return [
        NormalizedLineItem(canonical_name="Revenue from Operations", raw_label="Sales Turnover", amount=Decimal("20000000.00"), period="FY 2022-23", source_file="fy23.csv", source_sheet_or_page="Sheet1", source_row=2),
        NormalizedLineItem(canonical_name="Cost of Materials Consumed", raw_label="Raw Materials", amount=Decimal("11500000.00"), period="FY 2022-23", source_file="fy23.csv", source_sheet_or_page="Sheet1", source_row=3),
        NormalizedLineItem(canonical_name="Employee Benefit Expenses", raw_label="Salaries", amount=Decimal("3000000.00"), period="FY 2022-23", source_file="fy23.csv", source_sheet_or_page="Sheet1", source_row=4),
        NormalizedLineItem(canonical_name="Other Expenses", raw_label="Other Overhead", amount=Decimal("1800000.00"), period="FY 2022-23", source_file="fy23.csv", source_sheet_or_page="Sheet1", source_row=5),
        NormalizedLineItem(canonical_name="Finance Costs", raw_label="Interest", amount=Decimal("700000.00"), period="FY 2022-23", source_file="fy23.csv", source_sheet_or_page="Sheet1", source_row=6),
        NormalizedLineItem(canonical_name="Depreciation & Amortization", raw_label="Depreciation", amount=Decimal("600000.00"), period="FY 2022-23", source_file="fy23.csv", source_sheet_or_page="Sheet1", source_row=7),
        NormalizedLineItem(canonical_name="Profit After Tax (PAT)", raw_label="Net Profit", amount=Decimal("1950000.00"), period="FY 2022-23", source_file="fy23.csv", source_sheet_or_page="Sheet1", source_row=8),
    ]
