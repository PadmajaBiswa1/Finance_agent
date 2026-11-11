import re
from decimal import Decimal
from typing import Union, Any, Optional

from src.models.financial_schemas import (
    NormalizedFinancialStatement,
    NormalizedLineItem,
    ExtractedFinancialData,
    ExtractedTable,
    ExtractedRow,
    ErrorObject,
)
from src.tools.currency_utils import parse_indian_decimal

# Canonical Line Item Mapping for Indian SME Financial Statements
CANONICAL_RULES = {
    # P&L Line Items
    "Revenue from Operations": [
        r"revenue\s+from\s+operations",
        r"turnover",
        r"gross\s+sales",
        r"net\s+sales",
        r"gross\s+turnover",
        r"sale\s+of\s+products",
        r"sale\s+of\s+services",
        r"operating\s+revenue",
        r"gross\s+receipts",
    ],
    "Other Income": [
        r"other\s+income",
        r"non-operating\s+income",
        r"interest\s+income",
        r"scrap\s+sales",
        r"discount\s+received",
    ],
    "Cost of Materials Consumed": [
        r"cost\s+of\s+materials\s+consumed",
        r"raw\s+materials?\s+consumed",
        r"cogs",
        r"cost\s+of\s+goods\s+sold",
        r"purchases?\s+of\s+stock-in-trade",
        r"purchase\s+of\s+raw\s+materials?",
        r"direct\s+material\s+cost",
        r"direct\s+costs?",
    ],
    "Changes in Inventories": [
        r"changes?\s+in\s+inventor(y|ies)",
        r"increase/decrease\s+in\s+stock",
        r"stock-in-trade\s+changes?",
    ],
    "Employee Benefit Expenses": [
        r"employee\s+benefits?",
        r"salaries(\s+and|\s*&)?\s+wages",
        r"staff\s+costs?",
        r"wages\s+and\s+salaries",
        r"payroll\s+expenses?",
        r"personnel\s+expenses?",
    ],
    "Finance Costs": [
        r"finance\s+costs?",
        r"interest\s+(expense|paid|on\s+loans?)",
        r"bank\s+charges(\s+and|\s*&)?\s+interest",
        r"interest\s+and\s+bank\s+charges",
        r"borrowing\s+costs?",
    ],
    "Depreciation & Amortization": [
        r"depreciation(\s+and|\s*&)?\s+amorti[zs]ation",
        r"depreciation\s+expenses?",
        r"depreciation",
    ],
    "Other Expenses": [
        r"other\s+expenses?",
        r"administrative\s+expenses?",
        r"operating\s+expenses?",
        r"selling(\s+and|\s*&)?\s+distribution",
        r"manufacturing\s+expenses?",
        r"rent,?\s+rates(\s+and|\s*&)?\s+taxes",
        r"repairs(\s+and|\s*&)?\s+maintenance",
        r"power\s+and\s+fuel",
    ],
    "Profit Before Tax (PBT)": [
        r"profit\s+before\s+tax",
        r"pbt",
        r"earnings\s+before\s+tax",
        r"ebt",
    ],
    "Tax Expense": [
        r"tax\s+expenses?",
        r"income\s+tax",
        r"current\s+tax",
        r"provision\s+for\s+tax",
        r"mat\s+expense",
    ],
    "Profit After Tax (PAT)": [
        r"profit\s+after\s+tax",
        r"pat",
        r"net\s+profit",
        r"net\s+income",
        r"profit\s+for\s+the\s+(period|year)",
    ],

    # Balance Sheet Line Items
    "Total Equity": [
        r"total\s+equity",
        r"shareholders'?\s+funds?",
        r"net\s+worth",
        r"partners?'\s+capital",
        r"proprietor'?s\s+capital",
        r"total\s+capital\s+and\s+reserves",
    ],
    "Share Capital": [
        r"share\s+capital",
        r"equity\s+share\s+capital",
        r"capital\s+account",
    ],
    "Reserves and Surplus": [
        r"reserves(\s+and|\s*&)?\s+surplus",
        r"retained\s+earnings",
    ],
    "Long-Term Borrowings": [
        r"long-term\s+borrowings?",
        r"term\s+loans?",
        r"non-current\s+liabilities?",
        r"secured\s+loans?",
        r"unsecured\s+loans?",
    ],
    "Short-Term Borrowings": [
        r"short-term\s+borrowings?",
        r"working\s+capital\s+loans?",
        r"cash\s+credit",
        r"cc/od\s+limit",
        r"bank\s+overdraft",
    ],
    "Trade Payables": [
        r"trade\s+payables?",
        r"sundry\s+creditors?",
        r"bills\s+payable",
        r"msme\s+payables?",
    ],
    "Other Current Liabilities": [
        r"other\s+current\s+liabilities?",
        r"statutory\s+dues",
        r"gst\s+payable",
        r"tds\s+payable",
        r"provisions?",
    ],
    "Total Current Liabilities": [
        r"total\s+current\s+liabilities?",
        r"current\s+liabilities",
    ],
    "Total Liabilities and Equity": [
        r"total\s+liabilities(\s+and|\s*&)?\s+equity",
        r"total\s+equity\s+and\s+liabilities",
        r"total\s+sources\s+of\s+funds?",
        r"total\s+liabilities",
    ],
    "Property, Plant & Equipment": [
        r"property,?\s+plant(\s+and|\s*&)?\s+equipment",
        r"fixed\s+assets?",
        r"tangible\s+assets?",
        r"gross\s+block",
    ],
    "Non-Current Assets": [
        r"non-current\s+assets?",
        r"long-term\s+investments?",
    ],
    "Inventories": [
        r"inventor(y|ies)",
        r"stock\s+in\s+trade",
        r"closing\s+stock",
        r"raw\s+materials?\s+stock",
        r"finished\s+goods?",
    ],
    "Trade Receivables": [
        r"trade\s+receivables?",
        r"sundry\s+debtors?",
        r"book\s+debts",
        r"bills\s+receivable",
    ],
    "Cash and Cash Equivalents": [
        r"cash(\s+and|\s*&)?\s+cash\s+equivalents?",
        r"cash\s+and\s+bank\s+balances?",
        r"bank\s+balances?",
        r"cash\s+in\s+hand",
    ],
    "Short-Term Loans & Advances": [
        r"short-term\s+loans(\s+and|\s*&)?\s+advances",
        r"other\s+current\s+assets?",
        r"gst\s+input\s+credit",
        r"prepaid\s+expenses?",
        r"advance\s+tax",
    ],
    "Total Current Assets": [
        r"total\s+current\s+assets?",
        r"current\s+assets",
    ],
    "Total Assets": [
        r"total\s+assets?",
        r"total\s+application\s+of\s+funds?",
    ],

    # Cash Flow Line Items
    "Net Cash Flow from Operating Activities": [
        r"net\s+cash\s+(flow\s+)?(from|used\s+in)\s+operating\s+activities",
        r"cash\s+flow\s+from\s+operating\s+activities",
        r"operating\s+cash\s+flow",
        r"cash\s+generated\s+from\s+operations",
        r"cfo",
    ],
    "Net Cash Flow from Investing Activities": [
        r"net\s+cash\s+(flow\s+)?(from|used\s+in)\s+investing\s+activities",
        r"cash\s+flow\s+from\s+investing\s+activities",
        r"investing\s+cash\s+flow",
        r"cash\s+(used\s+in|from)\s+investing\s+activities",
        r"cfi",
    ],
    "Net Cash Flow from Financing Activities": [
        r"net\s+cash\s+(flow\s+)?(from|used\s+in)\s+financing\s+activities",
        r"cash\s+flow\s+from\s+financing\s+activities",
        r"financing\s+cash\s+flow",
        r"cash\s+(used\s+in|from)\s+financing\s+activities",
        r"cff",
    ],
    "Net Increase in Cash": [
        r"net\s+(increase|decrease|change)\s*(in)?\s*cash",
        r"net\s+increase/decrease\s+in\s+cash",
        r"net\s+cash\s+increase",
        r"net\s+change\s+in\s+cash",
    ],
    "Opening Cash Balance": [
        r"opening\s+cash(\s+and\s+cash\s+equivalents)?(\s+balance)?",
        r"cash\s+at\s+the\s+beginning",
        r"opening\s+balance",
    ],
    "Closing Cash Balance": [
        r"closing\s+cash(\s+and\s+cash\s+equivalents)?(\s+balance)?",
        r"cash\s+at\s+the\s+end",
        r"closing\s+balance",
    ],
}

def detect_unit_multiplier(text: str) -> tuple[Decimal, str]:
    """Detects if statements are reported in Lakhs, Crores, or Rupees."""
    lower = text.lower()
    if "lakh" in lower or "lacs" in lower:
        return Decimal("100000"), "Lakhs"
    if "crore" in lower or "cr" in lower:
        return Decimal("10000000"), "Crores"
    if "thousand" in lower:
        return Decimal("1000"), "Thousands"
    if "million" in lower:
        return Decimal("1000000"), "Millions"
    return Decimal("1.0"), "Rupees"

def map_raw_label_to_canonical(label: str) -> Optional[str]:
    """Matches a raw label against canonical rules using regex."""
    clean_label = re.sub(r"[^\w\s&/-]", " ", label).strip().lower()
    for canonical_name, patterns in CANONICAL_RULES.items():
        for pat in patterns:
            if re.search(pat, clean_label):
                return canonical_name
    return None

def normalize_financial_items_tool(
    extracted_data: Union[ExtractedFinancialData, dict],
    statement_type: str = "P&L",
    period: str = "FY 2023-24",
    unit_override: Optional[str] = None
) -> Union[NormalizedFinancialStatement, ErrorObject]:
    """
    ADK Function Tool: Normalizes extracted financial data into canonical Indian SME statement line items.
    Converts numbers into exact Decimals, applies unit multiplier if reported in Lakhs/Crores,
    and preserves file, page/sheet, and row references.
    """
    try:
        if isinstance(extracted_data, dict):
            extracted = ExtractedFinancialData.model_validate(extracted_data)
        elif isinstance(extracted_data, ExtractedFinancialData):
            extracted = extracted_data
        else:
            return ErrorObject(
                error_code="INVALID_ARGUMENT",
                message="extracted_data must be an ExtractedFinancialData object or dict.",
                details={"received_type": type(extracted_data).__name__}
            )

        items: list[NormalizedLineItem] = []
        unmapped_items: list[dict[str, Any]] = []

        multiplier = Decimal("1.0")
        unit_label = "Rupees"

        if unit_override:
            multiplier, unit_label = detect_unit_multiplier(unit_override)

        seen_canonicals: set[str] = set()

        for table in extracted.tables:
            # Check table header or sheet name for Lakhs/Crores indications if not overridden
            if not unit_override:
                header_text = " ".join(table.header) + " " + table.sheet_or_page
                m, u = detect_unit_multiplier(header_text)
                if m != Decimal("1.0"):
                    multiplier, unit_label = m, u

            for row in table.rows:
                raw_label = row.raw_label
                if not raw_label:
                    continue

                canonical = map_raw_label_to_canonical(raw_label)
                
                # Extract the numeric value from the row
                amount_parsed = "unavailable"
                # Search values right to left (financial values usually in later columns)
                for val in reversed(row.values):
                    parsed = parse_indian_decimal(val)
                    if isinstance(parsed, Decimal):
                        # Apply multiplier to convert into absolute INR
                        amount_parsed = parsed * multiplier
                        break

                if canonical:
                    # Avoid duplicate canonical entries by prioritizing the first valid amount
                    if canonical not in seen_canonicals or amount_parsed != "unavailable":
                        items.append(NormalizedLineItem(
                            canonical_name=canonical,
                            raw_label=raw_label,
                            amount=amount_parsed,
                            currency="INR",
                            period=period,
                            source_file=extracted.filename,
                            source_sheet_or_page=table.sheet_or_page,
                            source_row=row.row_number,
                            confidence=0.95
                        ))
                        seen_canonicals.add(canonical)
                else:
                    if amount_parsed != "unavailable":
                        unmapped_items.append({
                            "raw_label": raw_label,
                            "amount": str(amount_parsed),
                            "row": row.row_number,
                            "sheet_or_page": table.sheet_or_page
                        })

        valid_types = ("P&L", "Balance Sheet", "Cash Flow", "Mixed")
        st_type = statement_type if statement_type in valid_types else "Mixed"

        return NormalizedFinancialStatement(
            status="ok",
            statement_type=st_type,
            period=period,
            currency="INR",
            unit_multiplier=multiplier,
            unit_label=unit_label,
            items=items,
            unmapped_items=unmapped_items
        )

    except Exception as exc:
        return ErrorObject(
            error_code="NORMALIZATION_ERROR",
            message=f"Normalization failed: {str(exc)}",
            details={"exception": type(exc).__name__}
        )
