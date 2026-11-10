from decimal import Decimal
from typing import Union

from src.models.financial_schemas import (
    NormalizedFinancialStatement,
    NormalizedLineItem,
    ConsistencyCheckItem,
    ConsistencyCheckResult,
    ErrorObject,
)
from src.tools.calculation_tools import _get_item_value

def check_financial_consistency_tool(
    statement_or_items: Union[NormalizedFinancialStatement, list[NormalizedLineItem], dict, list[dict]],
    period: str = "FY 2023-24"
) -> Union[ConsistencyCheckResult, ErrorObject]:
    """
    ADK Function Tool: Verifies accounting consistency across balance sheet, P&L, and cash flow items.
    Flags balance sheet imbalances, P&L discrepancies, and data quality issues.
    """
    try:
        items: list[NormalizedLineItem] = []
        if isinstance(statement_or_items, NormalizedFinancialStatement):
            items = statement_or_items.items
            period = statement_or_items.period or period
        elif isinstance(statement_or_items, dict):
            if "items" in statement_or_items:
                stmt = NormalizedFinancialStatement.model_validate(statement_or_items)
                items = stmt.items
                period = stmt.period or period
            else:
                items = [NormalizedLineItem.model_validate(statement_or_items)]
        elif isinstance(statement_or_items, list):
            for i in statement_or_items:
                if isinstance(i, NormalizedLineItem):
                    items.append(i)
                elif isinstance(i, dict):
                    items.append(NormalizedLineItem.model_validate(i))

        checks: list[ConsistencyCheckItem] = []
        warnings: list[str] = []

        # 1. Balance Sheet: Total Assets == Total Liabilities and Equity
        tot_assets = _get_item_value(items, "Total Assets")
        tot_liab_eq = _get_item_value(items, "Total Liabilities and Equity")

        if isinstance(tot_assets, Decimal) and isinstance(tot_liab_eq, Decimal):
            diff = abs(tot_assets - tot_liab_eq)
            passed = diff == Decimal("0")
            checks.append(ConsistencyCheckItem(
                check_name="Balance Sheet Equality",
                status="PASSED" if passed else "FAILED",
                left_expression="Total Assets",
                left_value=tot_assets,
                right_expression="Total Liabilities and Equity",
                right_value=tot_liab_eq,
                discrepancy=diff,
                explanation="Total Assets matches Total Liabilities & Equity exactly." if passed
                    else f"Discrepancy of ₹ {diff} between Total Assets and Total Liabilities & Equity."
            ))
            if not passed:
                warnings.append(f"Balance sheet does not balance: Total Assets (₹ {tot_assets}) differs from Total Liabilities & Equity (₹ {tot_liab_eq}) by ₹ {diff}.")
        else:
            checks.append(ConsistencyCheckItem(
                check_name="Balance Sheet Equality",
                status="UNCHECKED",
                left_expression="Total Assets",
                left_value=tot_assets,
                right_expression="Total Liabilities and Equity",
                right_value=tot_liab_eq,
                discrepancy="unavailable",
                explanation="Could not verify balance sheet equality because one or both totals were missing."
            ))

        # 2. Balance Sheet: Total Assets == Current Assets + Non-Current Assets (Fixed Assets)
        ca = _get_item_value(items, "Total Current Assets")
        ppe = _get_item_value(items, "Property, Plant & Equipment")
        nca = _get_item_value(items, "Non-Current Assets")
        fixed_assets = ppe if isinstance(ppe, Decimal) else (nca if isinstance(nca, Decimal) else Decimal("0"))

        if isinstance(tot_assets, Decimal) and isinstance(ca, Decimal) and (isinstance(ppe, Decimal) or isinstance(nca, Decimal)):
            sum_assets = ca + fixed_assets
            diff = abs(tot_assets - sum_assets)
            passed = diff == Decimal("0")
            checks.append(ConsistencyCheckItem(
                check_name="Asset Subcomponents Reconciliation",
                status="PASSED" if passed else "WARNING",
                left_expression="Total Assets",
                left_value=tot_assets,
                right_expression="Current Assets + Non-Current Assets",
                right_value=sum_assets,
                discrepancy=diff,
                explanation="Current Assets + Non-Current Assets reconcile to Total Assets." if passed
                    else f"Minor discrepancy or unclassified asset lines totaling ₹ {diff}."
            ))

        # 3. P&L: PAT == PBT - Tax Expense
        pbt = _get_item_value(items, "Profit Before Tax (PBT)")
        tax = _get_item_value(items, "Tax Expense")
        pat = _get_item_value(items, "Profit After Tax (PAT)")

        if isinstance(pbt, Decimal) and isinstance(tax, Decimal) and isinstance(pat, Decimal):
            expected_pat = pbt - tax
            diff = abs(pat - expected_pat)
            passed = diff == Decimal("0")
            checks.append(ConsistencyCheckItem(
                check_name="P&L Net Profit Reconciliation",
                status="PASSED" if passed else "FAILED",
                left_expression="Reported PAT",
                left_value=pat,
                right_expression="PBT - Tax Expense",
                right_value=expected_pat,
                discrepancy=diff,
                explanation="Reported PAT matches PBT minus Tax Expense." if passed
                    else f"Reported PAT differs from PBT - Tax by ₹ {diff}."
            ))
            if not passed:
                warnings.append(f"P&L inconsistency: Reported PAT (₹ {pat}) does not equal PBT (₹ {pbt}) - Tax (₹ {tax}). Discrepancy: ₹ {diff}.")
        else:
            checks.append(ConsistencyCheckItem(
                check_name="P&L Net Profit Reconciliation",
                status="UNCHECKED",
                left_expression="Reported PAT",
                left_value=pat,
                right_expression="PBT - Tax Expense",
                right_value="unavailable",
                discrepancy="unavailable",
                explanation="P&L tax reconciliation unchecked due to missing lines."
            ))

        # 4. Cash Flow: Net Cash Flow == CFO + CFI + CFF
        cfo = _get_item_value(items, "Net Cash Flow from Operating Activities")
        cfi = _get_item_value(items, "Net Cash Flow from Investing Activities")
        cff = _get_item_value(items, "Net Cash Flow from Financing Activities")
        net_cash = _get_item_value(items, "Net Increase in Cash")

        if isinstance(cfo, Decimal) and isinstance(cfi, Decimal) and isinstance(cff, Decimal) and isinstance(net_cash, Decimal):
            sum_cf = cfo + cfi + cff
            diff = abs(net_cash - sum_cf)
            passed = diff == Decimal("0")
            checks.append(ConsistencyCheckItem(
                check_name="Cash Flow Sum Reconciliation",
                status="PASSED" if passed else "FAILED",
                left_expression="Net Increase in Cash",
                left_value=net_cash,
                right_expression="CFO + CFI + CFF",
                right_value=sum_cf,
                discrepancy=diff,
                explanation="CFO + CFI + CFF matches Net Change in Cash." if passed
                    else f"Discrepancy of ₹ {diff} in cash flow summation."
            ))
        elif any(isinstance(x, Decimal) for x in [cfo, cfi, cff, net_cash]):
            checks.append(ConsistencyCheckItem(
                check_name="Cash Flow Sum Reconciliation",
                status="UNCHECKED",
                left_expression="Net Increase in Cash",
                left_value=net_cash,
                right_expression="CFO + CFI + CFF",
                right_value="unavailable",
                discrepancy="unavailable",
                explanation="One or more cash flow activities not provided."
            ))

        # 5. Cash Flow: Closing Cash == Opening Cash + Net Increase in Cash
        open_cash = _get_item_value(items, "Opening Cash Balance")
        close_cash = _get_item_value(items, "Closing Cash Balance")

        if isinstance(open_cash, Decimal) and isinstance(close_cash, Decimal) and isinstance(net_cash, Decimal):
            expected_close = open_cash + net_cash
            diff = abs(close_cash - expected_close)
            passed = diff == Decimal("0")
            checks.append(ConsistencyCheckItem(
                check_name="Cash Flow Balance Reconciliation",
                status="PASSED" if passed else "FAILED",
                left_expression="Closing Cash",
                left_value=close_cash,
                right_expression="Opening Cash + Net Increase",
                right_value=expected_close,
                discrepancy=diff,
                explanation="Closing cash reconciles with opening cash and net change." if passed
                    else f"Closing cash mismatch of ₹ {diff}."
            ))

        all_passed = not any(c.status == "FAILED" for c in checks)
        failed_count = sum(1 for c in checks if c.status == "FAILED")
        warning_count = sum(1 for c in checks if c.status == "WARNING")

        if failed_count > 0:
            summary = f"{failed_count} consistency check(s) FAILED."
        elif warning_count > 0:
            summary = f"All consistency checks passed with {warning_count} advisory warning(s)."
        else:
            summary = "All verifiable financial consistency checks PASSED."

        return ConsistencyCheckResult(
            status="ok",
            all_passed=all_passed,
            checks=checks,
            summary=summary,
            data_quality_warnings=warnings
        )

    except Exception as exc:
        return ErrorObject(
            error_code="CONSISTENCY_CHECK_ERROR",
            message=f"Consistency check failed: {str(exc)}",
            details={"exception": type(exc).__name__}
        )
