import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Union, Optional, Any
from decimal import Decimal

from src.config import settings
from src.models.financial_schemas import (
    NormalizedFinancialStatement,
    NormalizedLineItem,
    ProfitMetricsResult,
    FinancialRatiosResult,
    PeriodComparisonResult,
    ConsistencyCheckResult,
    ErrorObject,
)
from src.models.report_schemas import FinancialReportOutput
from src.tools.currency_utils import format_inr
from src.tools.calculation_tools import calculate_profit_metrics_tool, calculate_ratios_tool
from src.tools.consistency_tools import check_financial_consistency_tool

def generate_financial_report_tool(
    normalized_statement: Union[NormalizedFinancialStatement, dict],
    profit_metrics: Optional[Union[ProfitMetricsResult, dict]] = None,
    financial_ratios: Optional[Union[FinancialRatiosResult, dict]] = None,
    period_comparison: Optional[Union[PeriodComparisonResult, dict]] = None,
    consistency_checks: Optional[Union[ConsistencyCheckResult, dict]] = None,
    business_name: str = "Indian Small Business Enterprise",
    executive_summary_override: Optional[str] = None
) -> Union[FinancialReportOutput, ErrorObject]:
    """
    ADK Function Tool: Generates an audit-ready, downloadable financial analysis report
    with explicit currency (INR), period, formulas, assumptions, source references (file, page, row),
    data quality warnings, and metrics.
    """
    try:
        if isinstance(normalized_statement, dict):
            stmt = NormalizedFinancialStatement.model_validate(normalized_statement)
        elif isinstance(normalized_statement, NormalizedFinancialStatement):
            stmt = normalized_statement
        else:
            return ErrorObject(
                error_code="INVALID_ARGUMENT",
                message="normalized_statement must be NormalizedFinancialStatement or dict."
            )

        report_id = f"FIN-REP-{uuid.uuid4().hex[:8].upper()}"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        period = stmt.period

        # Auto-compute metrics if not provided
        if profit_metrics is None:
            pm_res = calculate_profit_metrics_tool(stmt.items, period=period)
            pm = pm_res if isinstance(pm_res, ProfitMetricsResult) else None
        elif isinstance(profit_metrics, dict):
            pm = ProfitMetricsResult.model_validate(profit_metrics)
        else:
            pm = profit_metrics

        if financial_ratios is None:
            fr_res = calculate_ratios_tool(stmt.items, profit_metrics=pm, period=period)
            fr = fr_res if isinstance(fr_res, FinancialRatiosResult) else None
        elif isinstance(financial_ratios, dict):
            fr = FinancialRatiosResult.model_validate(financial_ratios)
        else:
            fr = financial_ratios

        if consistency_checks is None:
            cc_res = check_financial_consistency_tool(stmt.items, period=period)
            cc = cc_res if isinstance(cc_res, ConsistencyCheckResult) else None
        elif isinstance(consistency_checks, dict):
            cc = ConsistencyCheckResult.model_validate(consistency_checks)
        else:
            cc = consistency_checks

        pcomp: Optional[PeriodComparisonResult] = None
        if isinstance(period_comparison, dict):
            pcomp = PeriodComparisonResult.model_validate(period_comparison)
        elif isinstance(period_comparison, PeriodComparisonResult):
            pcomp = period_comparison

        # Compile formulas and assumptions
        formulas_used: dict[str, str] = {}
        assumptions: list[str] = [
            "All figures are expressed in Indian National Rupees (INR / ₹).",
            "Arithmetic is computed strictly using Python Decimal without LLM estimations.",
            "Missing line items are designated as 'unavailable' without fictitious guessing."
        ]
        if pm:
            formulas_used.update(pm.formulas_used)
            assumptions.extend(pm.assumptions)
        if fr:
            formulas_used.update(fr.formulas_used)
            assumptions.extend(fr.assumptions)
        if pcomp:
            assumptions.extend(pcomp.assumptions)

        # Deduplicate assumptions
        assumptions = list(dict.fromkeys(assumptions))

        # Compile source references
        source_refs: list[dict[str, Any]] = []
        for item in stmt.items:
            source_refs.append({
                "line_item": item.canonical_name,
                "raw_label": item.raw_label,
                "amount": format_inr(item.amount),
                "source_file": item.source_file,
                "source_sheet_or_page": item.source_sheet_or_page,
                "source_row": item.source_row
            })

        # Data-quality warnings
        warnings: list[str] = []
        if cc:
            warnings.extend(cc.data_quality_warnings)
        if pm and pm.missing_fields:
            warnings.append(f"Missing P&L fields: {', '.join(pm.missing_fields[:5])}")

        # Summary text
        if executive_summary_override:
            exec_summary = executive_summary_override
        else:
            summary_parts = [
                f"Financial Performance Report for {business_name} covering {period}.",
                f"Currency: INR (₹). Statement Type: {stmt.statement_type}."
            ]
            if pm:
                if isinstance(pm.revenue_from_operations, Decimal):
                    summary_parts.append(f"Revenue from Operations: {format_inr(pm.revenue_from_operations)}.")
                if isinstance(pm.pat, Decimal):
                    summary_parts.append(f"Profit After Tax (PAT): {format_inr(pm.pat)}.")
                if isinstance(pm.ebitda, Decimal):
                    summary_parts.append(f"EBITDA: {format_inr(pm.ebitda)}.")
            if fr:
                if fr.current_ratio != "unavailable":
                    summary_parts.append(f"Current Ratio: {fr.current_ratio}.")
                if fr.net_profit_margin_pct != "unavailable":
                    summary_parts.append(f"Net Profit Margin: {fr.net_profit_margin_pct}%.")
            if cc:
                summary_parts.append(f"Accounting Consistency Status: {cc.summary}")
            exec_summary = " ".join(summary_parts)

        # Build Markdown Document
        md_lines = [
            f"# Financial Analyst Report: {business_name}",
            f"**Report ID**: `{report_id}` | **Date Generated**: {now_str}",
            f"**Reporting Period**: {period} | **Currency**: INR (₹)",
            "",
            "## 1. Executive Summary",
            exec_summary,
            "",
            "## 2. Key Profitability Metrics",
            "| Metric | Amount (INR) | Formula |",
            "|---|---|---|"
        ]
        if pm:
            for m_name, m_val in [
                ("Revenue from Operations", pm.revenue_from_operations),
                ("Gross Profit", pm.gross_profit),
                ("Operating Profit", pm.operating_profit),
                ("EBITDA", pm.ebitda),
                ("EBIT", pm.ebit),
                ("EBT (PBT)", pm.ebt),
                ("PAT (Net Profit)", pm.pat)
            ]:
                f_used = pm.formulas_used.get(m_name, "Reported / Derived")
                md_lines.append(f"| {m_name} | {format_inr(m_val)} | {f_used} |")
        else:
            md_lines.append("| No profit metrics computed | - | - |")

        md_lines.extend([
            "",
            "## 3. Financial Ratios & Liquidity",
            "| Ratio / Metric | Value | Target / Benchmark (Indian SME) |",
            "|---|---|---|"
        ])
        if fr:
            for r_name, r_val, bench in [
                ("Current Ratio", fr.current_ratio, "1.33 - 1.50 (Tandon Committee standard)"),
                ("Quick Ratio", fr.quick_ratio, "> 1.0"),
                ("Debt to Equity", fr.debt_to_equity, "< 2.0"),
                ("Gross Margin %", f"{fr.gross_margin_pct}%" if fr.gross_margin_pct != "unavailable" else "unavailable", "Sector dependent"),
                ("EBITDA Margin %", f"{fr.ebitda_margin_pct}%" if fr.ebitda_margin_pct != "unavailable" else "unavailable", "12% - 20%"),
                ("Net Profit Margin %", f"{fr.net_profit_margin_pct}%" if fr.net_profit_margin_pct != "unavailable" else "unavailable", "> 5%"),
                ("Working Capital", format_inr(fr.working_capital), "Positive"),
                ("DSCR", fr.dscr, "> 1.5 for MSME bank lending"),
                ("Return on Equity (ROE) %", f"{fr.return_on_equity_pct}%" if fr.return_on_equity_pct != "unavailable" else "unavailable", "> 15%"),
                ("ROCE %", f"{fr.return_on_capital_employed_pct}%" if fr.return_on_capital_employed_pct != "unavailable" else "unavailable", "> Cost of Debt")
            ]:
                md_lines.append(f"| {r_name} | {r_val} | {bench} |")
        else:
            md_lines.append("| No ratios computed | - | - |")

        if pcomp:
            md_lines.extend([
                "",
                f"## 4. Period Comparison ({pcomp.period_a} vs {pcomp.period_b})",
                "| Metric | Period A | Period B | Variance (₹) | Variance (%) | Direction |",
                "|---|---|---|---|---|---|"
            ])
            for comp in pcomp.comparisons:
                dir_str = "🟢 Favorable" if comp.favorable is True else ("🔴 Unfavorable" if comp.favorable is False else "⚪ Neutral")
                md_lines.append(f"| {comp.metric_name} | {format_inr(comp.period_a_value)} | {format_inr(comp.period_b_value)} | {format_inr(comp.variance_abs)} | {comp.variance_pct}% | {dir_str} |")

        if cc:
            md_lines.extend([
                "",
                "## 5. Accounting Consistency & Balance Checks",
                f"**Overall Consistency Status**: {cc.summary}",
                "",
                "| Check Name | Status | Discrepancy | Details |",
                "|---|---|---|---|"
            ])
            for chk in cc.checks:
                icon = "✅" if chk.status == "PASSED" else ("❌" if chk.status == "FAILED" else "⚠️")
                disc_str = format_inr(chk.discrepancy) if chk.discrepancy != "unavailable" else "N/A"
                md_lines.append(f"| {chk.check_name} | {icon} {chk.status} | {disc_str} | {chk.explanation} |")

        if warnings:
            md_lines.extend([
                "",
                "## 6. Data Quality Warnings",
                *[f"- ⚠️ {w}" for w in warnings]
            ])

        md_lines.extend([
            "",
            "## 7. Assumptions & Methodology",
            *[f"- {a}" for a in assumptions],
            "",
            "## 8. Source References (Audit Trail)",
            "| Canonical Item | Raw File Label | Amount (INR) | Source File | Sheet/Page | Row |",
            "|---|---|---|---|---|---|"
        ])
        for s in source_refs:
            md_lines.append(f"| {s['line_item']} | {s['raw_label']} | {s['amount']} | {s['source_file']} | {s['source_sheet_or_page']} | {s['source_row']} |")

        report_md = "\n".join(md_lines)

        # Build Clean HTML representation
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Financial Report - {report_id}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 900px; margin: 40px auto; padding: 0 20px; }}
    h1 {{ color: #0f172a; border-bottom: 2px solid #0284c7; padding-bottom: 8px; }}
    h2 {{ color: #0369a1; margin-top: 28px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 10px 12px; text-align: left; }}
    th {{ background-color: #f1f5f9; font-weight: 600; }}
    tr:nth-child(even) {{ background-color: #f8fafc; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; font-weight: bold; }}
    .badge-pass {{ background: #dcfce7; color: #166534; }}
    .badge-fail {{ background: #fee2e2; color: #991b1b; }}
    .warning-box {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; margin: 16px 0; }}
    .meta-box {{ background: #e0f2fe; border-left: 4px solid #0284c7; padding: 12px; margin: 16px 0; }}
</style>
</head>
<body>
    <div class="meta-box">
        <strong>Report ID:</strong> {report_id} | <strong>Business:</strong> {business_name} | <strong>Period:</strong> {period} | <strong>Currency:</strong> INR (₹)<br>
        <strong>Generated:</strong> {now_str}
    </div>
    <div style="white-space: pre-wrap; font-family: inherit;">
{report_md}
    </div>
</body>
</html>
"""

        # Save files to reports directory
        md_path = settings.reports_dir / f"{report_id}.md"
        html_path = settings.reports_dir / f"{report_id}.html"
        json_path = settings.reports_dir / f"{report_id}.json"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        output = FinancialReportOutput(
            status="ok",
            report_id=report_id,
            title=f"Financial Analysis Report: {business_name}",
            business_name=business_name,
            currency="INR (₹)",
            period=period,
            generation_timestamp=now_str,
            executive_summary=exec_summary,
            assumptions=assumptions,
            formulas_used=formulas_used,
            source_references=source_refs,
            profit_metrics=pm,
            financial_ratios=fr,
            period_comparison=pcomp,
            consistency_checks=cc,
            line_items=stmt.items,
            data_quality_warnings=warnings,
            download_url_html=f"/reports/{report_id}.html",
            download_url_markdown=f"/reports/{report_id}.md",
            download_url_json=f"/reports/{report_id}.json"
        )

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(output.model_dump_json(indent=2))

        return output

    except Exception as exc:
        return ErrorObject(
            error_code="REPORT_GENERATION_ERROR",
            message=f"Report generation failed: {str(exc)}",
            details={"exception": type(exc).__name__}
        )
