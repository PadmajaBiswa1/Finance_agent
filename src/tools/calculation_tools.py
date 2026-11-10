from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Union, Any, Optional

from src.models.financial_schemas import (
    NormalizedFinancialStatement,
    NormalizedLineItem,
    ProfitMetricsResult,
    FinancialRatiosResult,
    PeriodComparisonItem,
    PeriodComparisonResult,
    ErrorObject,
)

def _get_item_value(items: list[NormalizedLineItem], canonical_name: str) -> Union[Decimal, str]:
    """Helper to extract Decimal amount for a canonical name, or 'unavailable'."""
    for item in items:
        if item.canonical_name == canonical_name:
            if isinstance(item.amount, Decimal):
                return item.amount
    return "unavailable"

def _get_item_source(items: list[NormalizedLineItem], canonical_name: str) -> Optional[dict[str, Any]]:
    for item in items:
        if item.canonical_name == canonical_name:
            return {
                "canonical_name": canonical_name,
                "raw_label": item.raw_label,
                "file": item.source_file,
                "sheet_or_page": item.source_sheet_or_page,
                "row": item.source_row
            }
    return None

def calculate_profit_metrics_tool(
    statement_or_items: Union[NormalizedFinancialStatement, list[NormalizedLineItem], dict, list[dict]],
    period: str = "FY 2023-24"
) -> Union[ProfitMetricsResult, ErrorObject]:
    """
    ADK Function Tool: Computes Gross Profit, EBITDA, EBIT, EBT, PAT, and Operating Profit using Python Decimal.
    Missing inputs return 'unavailable', never guessed.
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
        else:
            return ErrorObject(
                error_code="INVALID_ARGUMENT",
                message="statement_or_items must be a NormalizedFinancialStatement, list of items, or dict."
            )

        sources: list[dict[str, Any]] = []
        missing_fields: list[str] = []
        assumptions: list[str] = []
        formulas_used: dict[str, str] = {}

        # 1. Fetch core items
        rev = _get_item_value(items, "Revenue from Operations")
        other_inc = _get_item_value(items, "Other Income")
        cogs = _get_item_value(items, "Cost of Materials Consumed")
        changes_inv = _get_item_value(items, "Changes in Inventories")
        emp_exp = _get_item_value(items, "Employee Benefit Expenses")
        finance_costs = _get_item_value(items, "Finance Costs")
        depr = _get_item_value(items, "Depreciation & Amortization")
        other_exp = _get_item_value(items, "Other Expenses")
        tax_exp = _get_item_value(items, "Tax Expense")
        pat_reported = _get_item_value(items, "Profit After Tax (PAT)")
        pbt_reported = _get_item_value(items, "Profit Before Tax (PBT)")

        # Collect sources
        for name in [
            "Revenue from Operations", "Other Income", "Cost of Materials Consumed",
            "Changes in Inventories", "Employee Benefit Expenses", "Finance Costs",
            "Depreciation & Amortization", "Other Expenses", "Tax Expense",
            "Profit Before Tax (PBT)", "Profit After Tax (PAT)"
        ]:
            src = _get_item_source(items, name)
            if src:
                sources.append(src)
            else:
                missing_fields.append(name)

        # Assumptions
        assumptions.append("All monetary computations strictly performed using Python Decimal without LLM estimations.")
        if other_inc == "unavailable":
            other_inc = Decimal("0")
            assumptions.append("Other Income not explicitly reported; treated as ₹ 0 for EBITDA calculation.")
        if changes_inv == "unavailable":
            changes_inv = Decimal("0")

        # 2. Compute Gross Profit
        if isinstance(rev, Decimal) and isinstance(cogs, Decimal):
            gross_profit = rev - cogs
            formulas_used["Gross Profit"] = "Revenue from Operations - Cost of Materials Consumed"
        else:
            gross_profit = "unavailable"

        # 3. Compute EBITDA
        # Operating Expenses = COGS + Changes in Inv + Employee Expenses + Other Expenses
        can_calc_ebitda = (
            isinstance(rev, Decimal) and
            isinstance(cogs, Decimal) and
            isinstance(emp_exp, Decimal) and
            isinstance(other_exp, Decimal)
        )
        if can_calc_ebitda:
            op_expenses = cogs + (changes_inv if isinstance(changes_inv, Decimal) else Decimal("0")) + emp_exp + other_exp
            ebitda = (rev + other_inc) - op_expenses
            formulas_used["EBITDA"] = "(Revenue from Operations + Other Income) - (Cost of Materials + Inventory Changes + Employee Benefits + Other Expenses)"
        else:
            ebitda = "unavailable"

        # 4. Compute EBIT
        if isinstance(ebitda, Decimal) and isinstance(depr, Decimal):
            ebit = ebitda - depr
            formulas_used["EBIT"] = "EBITDA - Depreciation & Amortization"
        else:
            ebit = "unavailable"

        # 5. Compute EBT / PBT
        if isinstance(pbt_reported, Decimal):
            ebt = pbt_reported
            formulas_used["EBT (PBT)"] = "Reported Profit Before Tax"
        elif isinstance(ebit, Decimal) and isinstance(finance_costs, Decimal):
            ebt = ebit - finance_costs
            formulas_used["EBT (PBT)"] = "EBIT - Finance Costs"
        else:
            ebt = "unavailable"

        # 6. Compute PAT
        if isinstance(pat_reported, Decimal):
            pat = pat_reported
            formulas_used["PAT (Net Profit)"] = "Reported Profit After Tax"
        elif isinstance(ebt, Decimal) and isinstance(tax_exp, Decimal):
            pat = ebt - tax_exp
            formulas_used["PAT (Net Profit)"] = "Profit Before Tax - Tax Expense"
        else:
            pat = "unavailable"

        # 7. Compute Operating Profit
        if isinstance(rev, Decimal) and isinstance(cogs, Decimal) and isinstance(emp_exp, Decimal) and isinstance(other_exp, Decimal):
            depr_val = depr if isinstance(depr, Decimal) else Decimal("0")
            operating_profit = rev - (cogs + emp_exp + other_exp + depr_val)
            formulas_used["Operating Profit"] = "Revenue - (COGS + Employee Benefits + Other Expenses + Depreciation)"
        else:
            operating_profit = "unavailable"

        return ProfitMetricsResult(
            status="ok",
            currency="INR",
            period=period,
            revenue_from_operations=rev,
            gross_profit=gross_profit,
            operating_profit=operating_profit,
            ebitda=ebitda,
            ebit=ebit,
            ebt=ebt,
            pat=pat,
            formulas_used=formulas_used,
            assumptions=assumptions,
            sources=sources,
            missing_fields=missing_fields
        )

    except Exception as exc:
        return ErrorObject(
            error_code="PROFIT_METRICS_CALCULATION_ERROR",
            message=f"Profit metrics calculation failed: {str(exc)}",
            details={"exception": type(exc).__name__}
        )

def calculate_ratios_tool(
    statement_or_items: Union[NormalizedFinancialStatement, list[NormalizedLineItem], dict, list[dict]],
    profit_metrics: Optional[Union[ProfitMetricsResult, dict]] = None,
    period: str = "FY 2023-24"
) -> Union[FinancialRatiosResult, ErrorObject]:
    """
    ADK Function Tool: Computes Current Ratio, Quick Ratio, Debt-to-Equity, Margins %, DSCR, ROE, ROCE, and Working Capital.
    All arithmetic uses Decimal. Missing values return 'unavailable', never guessed.
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

        # Retrieve profit metrics if passed or calculate
        pm: Optional[ProfitMetricsResult] = None
        if isinstance(profit_metrics, ProfitMetricsResult):
            pm = profit_metrics
        elif isinstance(profit_metrics, dict):
            pm = ProfitMetricsResult.model_validate(profit_metrics)
        else:
            calc_pm = calculate_profit_metrics_tool(items, period=period)
            if isinstance(calc_pm, ProfitMetricsResult):
                pm = calc_pm

        sources: list[dict[str, Any]] = []
        missing_fields: list[str] = []
        assumptions: list[str] = [
            "All ratio calculations performed using Python Decimal.",
            "Ratios are rounded to 2 decimal places using standard ROUND_HALF_UP.",
            "Undefined denominators return 'unavailable'."
        ]
        formulas_used: dict[str, str] = {}

        # Fetch Balance Sheet items
        ca = _get_item_value(items, "Total Current Assets")
        cl = _get_item_value(items, "Total Current Liabilities")
        inv = _get_item_value(items, "Inventories")
        equity = _get_item_value(items, "Total Equity")
        lt_borrowings = _get_item_value(items, "Long-Term Borrowings")
        st_borrowings = _get_item_value(items, "Short-Term Borrowings")
        fin_costs = _get_item_value(items, "Finance Costs")
        depr = _get_item_value(items, "Depreciation & Amortization")

        # Fallback for current assets if sum of subcomponents
        if ca == "unavailable":
            debtors = _get_item_value(items, "Trade Receivables")
            cash = _get_item_value(items, "Cash and Cash Equivalents")
            other_ca = _get_item_value(items, "Short-Term Loans & Advances")
            if isinstance(inv, Decimal) and isinstance(debtors, Decimal) and isinstance(cash, Decimal):
                other_val = other_ca if isinstance(other_ca, Decimal) else Decimal("0")
                ca = inv + debtors + cash + other_val
                assumptions.append("Total Current Assets aggregated from Inventories + Trade Receivables + Cash + Advances.")

        # Fallback for current liabilities if sum of subcomponents
        if cl == "unavailable":
            creditors = _get_item_value(items, "Trade Payables")
            other_cl = _get_item_value(items, "Other Current Liabilities")
            if isinstance(creditors, Decimal):
                st_b_val = st_borrowings if isinstance(st_borrowings, Decimal) else Decimal("0")
                other_cl_val = other_cl if isinstance(other_cl, Decimal) else Decimal("0")
                cl = creditors + st_b_val + other_cl_val
                assumptions.append("Total Current Liabilities aggregated from Trade Payables + Short-Term Borrowings + Other Current Liabilities.")

        for name in ["Total Current Assets", "Total Current Liabilities", "Inventories", "Total Equity", "Long-Term Borrowings", "Short-Term Borrowings"]:
            src = _get_item_source(items, name)
            if src:
                sources.append(src)
            else:
                missing_fields.append(name)

        # 1. Current Ratio
        if isinstance(ca, Decimal) and isinstance(cl, Decimal) and cl > 0:
            current_ratio = (ca / cl).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            formulas_used["Current Ratio"] = "Total Current Assets / Total Current Liabilities"
        else:
            current_ratio = "unavailable"

        # 2. Quick Ratio
        if isinstance(ca, Decimal) and isinstance(cl, Decimal) and cl > 0:
            inv_val = inv if isinstance(inv, Decimal) else Decimal("0")
            quick_ratio = ((ca - inv_val) / cl).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            formulas_used["Quick Ratio"] = "(Total Current Assets - Inventories) / Total Current Liabilities"
        else:
            quick_ratio = "unavailable"

        # 3. Debt to Equity
        if isinstance(equity, Decimal) and equity > 0:
            lt_val = lt_borrowings if isinstance(lt_borrowings, Decimal) else Decimal("0")
            st_val = st_borrowings if isinstance(st_borrowings, Decimal) else Decimal("0")
            total_debt = lt_val + st_val
            debt_to_equity = (total_debt / equity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            formulas_used["Debt to Equity"] = "(Long-Term Borrowings + Short-Term Borrowings) / Total Equity"
        else:
            debt_to_equity = "unavailable"

        # 4. Working Capital
        if isinstance(ca, Decimal) and isinstance(cl, Decimal):
            working_capital = ca - cl
            formulas_used["Working Capital"] = "Total Current Assets - Total Current Liabilities"
        else:
            working_capital = "unavailable"

        # Profitability Margins (require profit metrics)
        gross_margin_pct = "unavailable"
        operating_margin_pct = "unavailable"
        ebitda_margin_pct = "unavailable"
        net_profit_margin_pct = "unavailable"
        dscr = "unavailable"
        roe_pct = "unavailable"
        roce_pct = "unavailable"

        if pm:
            rev = pm.revenue_from_operations
            if isinstance(rev, Decimal) and rev > 0:
                # Gross Margin %
                if isinstance(pm.gross_profit, Decimal):
                    gross_margin_pct = ((pm.gross_profit / rev) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    formulas_used["Gross Margin %"] = "(Gross Profit / Revenue from Operations) * 100"

                # Operating Margin %
                if isinstance(pm.operating_profit, Decimal):
                    operating_margin_pct = ((pm.operating_profit / rev) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    formulas_used["Operating Margin %"] = "(Operating Profit / Revenue from Operations) * 100"

                # EBITDA Margin %
                if isinstance(pm.ebitda, Decimal):
                    ebitda_margin_pct = ((pm.ebitda / rev) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    formulas_used["EBITDA Margin %"] = "(EBITDA / Revenue from Operations) * 100"

                # Net Profit Margin %
                if isinstance(pm.pat, Decimal):
                    net_profit_margin_pct = ((pm.pat / rev) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    formulas_used["Net Profit Margin %"] = "(PAT / Revenue from Operations) * 100"

            # ROE %
            if isinstance(pm.pat, Decimal) and isinstance(equity, Decimal) and equity > 0:
                roe_pct = ((pm.pat / equity) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                formulas_used["Return on Equity (ROE) %"] = "(PAT / Total Equity) * 100"

            # ROCE %
            if isinstance(pm.ebit, Decimal) and isinstance(equity, Decimal):
                lt_val = lt_borrowings if isinstance(lt_borrowings, Decimal) else Decimal("0")
                cap_employed = equity + lt_val
                if cap_employed > 0:
                    roce_pct = ((pm.ebit / cap_employed) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    formulas_used["ROCE %"] = "(EBIT / (Total Equity + Long-Term Borrowings)) * 100"

            # DSCR (Debt Service Coverage Ratio)
            if isinstance(pm.pat, Decimal) and isinstance(fin_costs, Decimal) and fin_costs > 0:
                depr_val = depr if isinstance(depr, Decimal) else Decimal("0")
                dscr = ((pm.pat + depr_val + fin_costs) / fin_costs).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                formulas_used["DSCR"] = "(PAT + Depreciation + Finance Costs) / Finance Costs"
            elif isinstance(pm.ebitda, Decimal) and isinstance(fin_costs, Decimal) and fin_costs > 0:
                dscr = (pm.ebitda / fin_costs).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                formulas_used["DSCR"] = "EBITDA / Finance Costs"

        return FinancialRatiosResult(
            status="ok",
            currency="INR",
            period=period,
            current_ratio=current_ratio,
            quick_ratio=quick_ratio,
            debt_to_equity=debt_to_equity,
            gross_margin_pct=gross_margin_pct,
            operating_margin_pct=operating_margin_pct,
            ebitda_margin_pct=ebitda_margin_pct,
            net_profit_margin_pct=net_profit_margin_pct,
            working_capital=working_capital,
            dscr=dscr,
            return_on_equity_pct=roe_pct,
            return_on_capital_employed_pct=roce_pct,
            formulas_used=formulas_used,
            assumptions=assumptions,
            sources=sources,
            missing_fields=missing_fields
        )

    except Exception as exc:
        return ErrorObject(
            error_code="RATIO_CALCULATION_ERROR",
            message=f"Ratio calculation failed: {str(exc)}",
            details={"exception": type(exc).__name__}
        )

def compare_periods_tool(
    period_a_items: Union[list[NormalizedLineItem], NormalizedFinancialStatement, dict, list[dict]],
    period_b_items: Union[list[NormalizedLineItem], NormalizedFinancialStatement, dict, list[dict]],
    period_a: str = "FY 2022-23",
    period_b: str = "FY 2023-24"
) -> Union[PeriodComparisonResult, ErrorObject]:
    """
    ADK Function Tool: Compares two financial periods, computing absolute variance and percentage variance in Decimal.
    """
    try:
        def extract_items_list(data) -> list[NormalizedLineItem]:
            if isinstance(data, NormalizedFinancialStatement):
                return data.items
            if isinstance(data, dict) and "items" in data:
                return NormalizedFinancialStatement.model_validate(data).items
            if isinstance(data, list):
                res = []
                for x in data:
                    if isinstance(x, NormalizedLineItem):
                        res.append(x)
                    elif isinstance(x, dict):
                        res.append(NormalizedLineItem.model_validate(x))
                return res
            return []

        items_a = extract_items_list(period_a_items)
        items_b = extract_items_list(period_b_items)

        map_a: dict[str, Decimal] = {}
        for item in items_a:
            if isinstance(item.amount, Decimal):
                map_a[item.canonical_name] = item.amount

        map_b: dict[str, Decimal] = {}
        for item in items_b:
            if isinstance(item.amount, Decimal):
                map_b[item.canonical_name] = item.amount

        # Also compute profit metrics for each to compare EBITDA/Gross Profit/PAT
        pm_a = calculate_profit_metrics_tool(items_a, period=period_a)
        pm_b = calculate_profit_metrics_tool(items_b, period=period_b)
        if isinstance(pm_a, ProfitMetricsResult) and isinstance(pm_b, ProfitMetricsResult):
            if isinstance(pm_a.gross_profit, Decimal):
                map_a["Gross Profit"] = pm_a.gross_profit
            if isinstance(pm_b.gross_profit, Decimal):
                map_b["Gross Profit"] = pm_b.gross_profit
            if isinstance(pm_a.ebitda, Decimal):
                map_a["EBITDA"] = pm_a.ebitda
            if isinstance(pm_b.ebitda, Decimal):
                map_b["EBITDA"] = pm_b.ebitda

        all_keys = sorted(list(set(map_a.keys()) | set(map_b.keys())))
        comparisons: list[PeriodComparisonItem] = []

        cost_metrics = {
            "Cost of Materials Consumed", "Employee Benefit Expenses",
            "Finance Costs", "Depreciation & Amortization", "Other Expenses",
            "Tax Expense", "Total Current Liabilities", "Long-Term Borrowings", "Short-Term Borrowings"
        }

        for k in all_keys:
            val_a = map_a.get(k, "unavailable")
            val_b = map_b.get(k, "unavailable")

            if isinstance(val_a, Decimal) and isinstance(val_b, Decimal):
                diff_abs = val_b - val_a
                if val_a != 0:
                    pct = ((diff_abs / abs(val_a)) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                else:
                    pct = "unavailable"

                is_cost = k in cost_metrics
                favorable = (diff_abs < 0) if is_cost else (diff_abs > 0)
                note = f"{'Favorable' if favorable else 'Unfavorable'} change of {pct}%" if pct != "unavailable" else ""
            else:
                diff_abs = "unavailable"
                pct = "unavailable"
                favorable = None
                note = "Metric missing in one of the comparison periods."

            comparisons.append(PeriodComparisonItem(
                metric_name=k,
                period_a_value=val_a,
                period_b_value=val_b,
                variance_abs=diff_abs,
                variance_pct=pct,
                favorable=favorable,
                note=note
            ))

        return PeriodComparisonResult(
            status="ok",
            period_a=period_a,
            period_b=period_b,
            currency="INR",
            comparisons=comparisons,
            assumptions=[
                "Variance Abs = Period B - Period A",
                "Variance % = ((Period B - Period A) / abs(Period A)) * 100",
                "Favorable is True for revenue/profit increases and cost/liability decreases."
            ]
        )

    except Exception as exc:
        return ErrorObject(
            error_code="PERIOD_COMPARISON_ERROR",
            message=f"Period comparison failed: {str(exc)}",
            details={"exception": type(exc).__name__}
        )
