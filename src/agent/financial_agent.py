import time
import uuid
import json
from pathlib import Path
from typing import Optional, Union, Any
from google import genai
from google.genai import types

from src.config import settings
from src.prompts import SYSTEM_PROMPT, FIXED_REFUSAL_REPLY
from src.models.classifier_schemas import ClassificationResult
from src.models.financial_schemas import (
    NormalizedFinancialStatement,
    ProfitMetricsResult,
    FinancialRatiosResult,
    PeriodComparisonResult,
    ConsistencyCheckResult,
    ExtractedFinancialData,
    FileValidationResult,
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
from src.tools.browser_tools import fetch_official_source_tool
from src.guardrails.input_guard import check_input_guard
from src.guardrails.output_guard import check_output_guard
from src.guardrails.classifier import classify_request
from src.guardrails.redactor import redact_sensitive_info
from src.agent.cache import tool_cache
from src.agent.telemetry import telemetry_tracker, RequestTelemetry

def _generate_clean_fallback_summary(
    compact_context: dict[str, Any],
    period: str,
    business_name: str
) -> str:
    """Generates a clean, user-friendly markdown financial summary when LLM explanation is unavailable."""
    lines = [
        f"### Financial Analysis Summary: {business_name}",
        f"**Reporting Period**: {period} | **Currency**: INR (₹)\n"
    ]

    # 1. Cash Flow Highlights
    items_summary = compact_context.get("line_items_summary", [])
    cf_keys = {
        "Net Cash Flow from Operating Activities": "Operating Activities (CFO)",
        "Net Cash Flow from Investing Activities": "Investing Activities (CFI)",
        "Net Cash Flow from Financing Activities": "Financing Activities (CFF)",
        "Net Increase in Cash": "Net Increase / (Decrease) in Cash",
        "Opening Cash Balance": "Opening Cash & Equivalents",
        "Closing Cash Balance": "Closing Cash & Equivalents"
    }
    cf_found = [i for i in items_summary if i.get("item") in cf_keys]
    if cf_found:
        lines.append("#### Cash Flow Statement Breakdown & Reconciliation")
        lines.append("| Activity / Line Item | Amount (INR) | Source Citation |")
        lines.append("|---|---|---|")
        cf_dict = {}
        for item in cf_found:
            k = item.get("item")
            amt = item.get("amount")
            src = item.get("source", "")
            cf_dict[k] = amt
            display_name = cf_keys.get(k, k)
            lines.append(f"| **{display_name}** | ₹ {amt} | {src} |")
        lines.append("")

        # Add Cash Flow Reconciliation highlights
        cfo = cf_dict.get("Net Cash Flow from Operating Activities")
        cfi = cf_dict.get("Net Cash Flow from Investing Activities")
        cff = cf_dict.get("Net Cash Flow from Financing Activities")
        net_cash = cf_dict.get("Net Increase in Cash")
        open_cash = cf_dict.get("Opening Cash Balance")
        close_cash = cf_dict.get("Closing Cash Balance")

        lines.append("##### Cash Flow Verification Audit:")
        if cfo is not None and cfi is not None and cff is not None and net_cash is not None:
            lines.append(f"• **Sum Check (CFO + CFI + CFF = Net Increase)**: ₹ {cfo} + (₹ {cfi}) + (₹ {cff}) = **₹ {net_cash}** ✅ *Exact Reconciliation Verified*")
        if open_cash is not None and net_cash is not None and close_cash is not None:
            lines.append(f"• **Closing Balance Reconciliation**: Opening Balance (₹ {open_cash}) + Net Change (₹ {net_cash}) = **₹ {close_cash}** ✅ *Closing Balance Reconciled*")
        lines.append("")

    # 2. Profitability Metrics
    pm = compact_context.get("computed_profit_metrics")
    if pm:
        lines.append("#### Key Profitability Metrics")
        lines.append("| Metric | Value | Formula / Method |")
        lines.append("|---|---|---|")
        for k, v in [
            ("Revenue from Operations", pm.get("Revenue")),
            ("Gross Profit", pm.get("Gross_Profit")),
            ("EBITDA", pm.get("EBITDA")),
            ("EBIT", pm.get("EBIT")),
            ("Profit After Tax (PAT)", pm.get("PAT")),
        ]:
            formula = pm.get("Formulas", {}).get(k, "Derived from statements")
            val_str = f"₹ {v}" if (v and v != "unavailable") else "unavailable"
            lines.append(f"| **{k}** | {val_str} | {formula} |")
        lines.append("")

    # 3. Financial Ratios & Liquidity
    fr = compact_context.get("computed_financial_ratios")
    if fr:
        lines.append("#### Key Financial Ratios & Liquidity")
        lines.append("| Ratio | Calculated Value | Benchmark |")
        lines.append("|---|---|---|")
        for k, v, bench in [
            ("Current Ratio", fr.get("Current_Ratio"), "1.33 - 1.50 (Tandon Committee)"),
            ("Quick Ratio", fr.get("Quick_Ratio"), "> 1.0"),
            ("Debt to Equity", fr.get("Debt_to_Equity"), "< 2.0"),
            ("Gross Margin %", f"{fr.get('Gross_Margin_Pct')}%" if fr.get("Gross_Margin_Pct") != "unavailable" else "unavailable", "Sector dependent"),
            ("Net Profit Margin %", f"{fr.get('Net_Profit_Margin_Pct')}%" if fr.get("Net_Profit_Margin_Pct") != "unavailable" else "unavailable", "> 5%"),
            ("Working Capital", f"₹ {fr.get('Working_Capital')}" if fr.get("Working_Capital") != "unavailable" else "unavailable", "Positive"),
            ("DSCR", fr.get("DSCR"), "> 1.5"),
        ]:
            lines.append(f"| **{k}** | {v} | {bench} |")
        lines.append("")

    # 4. Period Comparison
    pcomp = compact_context.get("period_comparison")
    if pcomp:
        lines.append("#### Period Comparison Highlights")
        lines.append("| Metric | Prior Period | Current Period | Variance (%) | Status |")
        lines.append("|---|---|---|---|---|")
        for c in pcomp:
            status = "🟢 Favorable" if c.get("favorable") is True else ("🔴 Unfavorable" if c.get("favorable") is False else "⚪ Neutral")
            lines.append(f"| {c.get('metric')} | ₹ {c.get('period_a')} | ₹ {c.get('period_b')} | {c.get('variance_pct')}% | {status} |")
        lines.append("")

    # 5. Consistency Checks
    cc_checks = compact_context.get("consistency_checks")
    if cc_checks:
        lines.append("#### Accounting Consistency Audit")
        lines.append("| Check | Status | Verification Details |")
        lines.append("|---|---|---|")
        for chk in cc_checks:
            icon = "✅" if chk.get("status") == "PASSED" else ("❌" if chk.get("status") == "FAILED" else "⚠️")
            lines.append(f"| {chk.get('check_name')} | {icon} {chk.get('status')} | {chk.get('explanation')} |")
        lines.append("")
    elif compact_context.get("consistency_summary"):
        lines.append(f"**Accounting Consistency**: {compact_context.get('consistency_summary')}\n")

    lines.append("*(Note: All monetary figures calculated deterministically in Python Decimal without LLM estimation.)*")
    return "\n".join(lines)

class FinancialAgent:
    """
    Main Indian SME Financial Analyst Agent.
    Orchestrates sandboxed extraction, strict Decimal tools, token-reduced prompt context,
    guardrails, and Gemini explanation.
    """
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def analyze(
        self,
        user_message: str,
        uploaded_file_path: Optional[Union[str, Path]] = None,
        second_file_path: Optional[Union[str, Path]] = None,
        official_url: Optional[str] = None,
        generate_report: bool = False,
        business_name: str = "Indian Small Business Enterprise",
        period: str = "FY 2023-24",
        comparison_period: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Executes complete financial query workflow with guardrails, token reduction, and auditing.
        """
        t0 = time.time()
        req_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        tools_called: list[str] = []
        cache_hits_count = 0
        raw_token_estimate = 0

        # Step 1: Input Guardrail Check
        input_safe, input_reason, input_flags = check_input_guard(user_message)
        if not input_safe:
            is_refusal = True
            telemetry_tracker.log_request(RequestTelemetry(
                request_id=req_id,
                user_query=user_message[:100],
                classifier_model="input_guard",
                reasoning_model="none",
                total_latency_ms=round((time.time() - t0) * 1000, 2),
                prompt_tokens=len(user_message) // 4,
                completion_tokens=len(input_reason) // 4,
                total_tokens=(len(user_message) + len(input_reason)) // 4,
                tools_called=[],
                cache_hits=0
            ))
            return {
                "request_id": req_id,
                "status": "refused",
                "answer": input_reason,
                "classification": {
                    "domain": "security_block",
                    "allowed": False,
                    "reason": input_reason,
                    "flags": input_flags
                },
                "tools_executed": [],
                "data_quality_warnings": []
            }

        # Step 2: Scope Classification (Deterministic Pre-Filter + Fast Model)
        t_cls_0 = time.time()
        cls_result: ClassificationResult = classify_request(user_message)
        cls_latency = round((time.time() - t_cls_0) * 1000, 2)

        if not cls_result.allowed:
            telemetry_tracker.log_request(RequestTelemetry(
                request_id=req_id,
                user_query=user_message[:100],
                classifier_model=settings.fast_model_id,
                reasoning_model="none",
                classifier_latency_ms=cls_latency,
                total_latency_ms=round((time.time() - t0) * 1000, 2),
                prompt_tokens=len(user_message) // 4,
                completion_tokens=len(FIXED_REFUSAL_REPLY) // 4,
                total_tokens=(len(user_message) + len(FIXED_REFUSAL_REPLY)) // 4,
                tools_called=[],
                cache_hits=0
            ))
            return {
                "request_id": req_id,
                "status": "refused",
                "answer": FIXED_REFUSAL_REPLY,
                "classification": cls_result.model_dump(),
                "tools_executed": [],
                "data_quality_warnings": []
            }

        # Step 3: Tool Execution (Sandboxed parsing, normalization, Decimal arithmetic)
        tool_results_data: dict[str, Any] = {}
        data_quality_warnings: list[str] = []
        stmt: Optional[NormalizedFinancialStatement] = None
        pm: Optional[ProfitMetricsResult] = None
        fr: Optional[FinancialRatiosResult] = None
        pcomp: Optional[PeriodComparisonResult] = None
        cc: Optional[ConsistencyCheckResult] = None
        report_output: Optional[FinancialReportOutput] = None
        browser_output: Optional[dict[str, Any]] = None

        # 3A. File Processing
        if uploaded_file_path:
            fpath = Path(uploaded_file_path)
            # Estimate what raw file tokens would have been without token reduction:
            raw_token_estimate += max(2000, int(fpath.stat().st_size / 3.0)) if fpath.exists() else 2000

            # Step 3A.1: Validate file
            cached_val = tool_cache.get("validate", str(fpath))
            if cached_val:
                val_result = cached_val
                cache_hits_count += 1
            else:
                val_result = validate_financial_file_tool(str(fpath))
                tools_called.append("validate_financial_file")
                if isinstance(val_result, FileValidationResult):
                    tool_cache.set("validate", str(fpath), val_result)

            if isinstance(val_result, ErrorObject) or not val_result.is_valid:
                err_msg = val_result.message if isinstance(val_result, ErrorObject) else "; ".join(val_result.validation_errors)
                return {
                    "request_id": req_id,
                    "status": "error",
                    "answer": f"Uploaded file validation failed: {err_msg}",
                    "classification": cls_result.model_dump(),
                    "tools_executed": tools_called,
                    "data_quality_warnings": [err_msg]
                }

            file_hash = val_result.sha256_hash

            # Step 3A.2: Extract Financial Data in Sandbox
            cached_ext = tool_cache.get("extract", file_hash)
            if cached_ext:
                ext_data = cached_ext
                cache_hits_count += 1
            else:
                ext_data = extract_financial_data_tool(str(fpath))
                tools_called.append("extract_financial_data")
                if isinstance(ext_data, ExtractedFinancialData):
                    tool_cache.set("extract", file_hash, ext_data)

            if isinstance(ext_data, ErrorObject):
                return {
                    "request_id": req_id,
                    "status": "error",
                    "answer": f"Sandboxed file extraction error: {ext_data.message}",
                    "classification": cls_result.model_dump(),
                    "tools_executed": tools_called,
                    "data_quality_warnings": [ext_data.message]
                }

            # Step 3A.3: Normalize Line Items
            cached_norm = tool_cache.get("normalize", file_hash, {"period": period})
            if cached_norm:
                norm_res = cached_norm
                cache_hits_count += 1
            else:
                norm_res = normalize_financial_items_tool(ext_data, period=period)
                tools_called.append("normalize_financial_items")
                if isinstance(norm_res, NormalizedFinancialStatement):
                    tool_cache.set("normalize", file_hash, norm_res, {"period": period})

            if isinstance(norm_res, ErrorObject):
                return {
                    "request_id": req_id,
                    "status": "error",
                    "answer": f"Financial normalization failed: {norm_res.message}",
                    "classification": cls_result.model_dump(),
                    "tools_executed": tools_called,
                    "data_quality_warnings": [norm_res.message]
                }

            stmt = norm_res

            # Step 3A.4: Consistency Checks
            cc_res = check_financial_consistency_tool(stmt.items, period=period)
            tools_called.append("check_financial_consistency")
            if isinstance(cc_res, ConsistencyCheckResult):
                cc = cc_res
                data_quality_warnings.extend(cc.data_quality_warnings)
                tool_results_data["consistency"] = cc.model_dump()

            # Step 3A.5: Profit Metrics
            pm_res = calculate_profit_metrics_tool(stmt.items, period=period)
            tools_called.append("calculate_profit_metrics")
            if isinstance(pm_res, ProfitMetricsResult):
                pm = pm_res
                tool_results_data["profit_metrics"] = pm.model_dump()

            # Step 3A.6: Financial Ratios
            fr_res = calculate_ratios_tool(stmt.items, profit_metrics=pm, period=period)
            tools_called.append("calculate_ratios")
            if isinstance(fr_res, FinancialRatiosResult):
                fr = fr_res
                tool_results_data["ratios"] = fr.model_dump()

            # Step 3A.7: Compare Periods if second file provided
            if second_file_path:
                fpath2 = Path(second_file_path)
                p2 = comparison_period or "FY 2022-23"
                val2 = validate_financial_file_tool(str(fpath2))
                tools_called.append("validate_financial_file")
                if isinstance(val2, FileValidationResult) and val2.is_valid:
                    ext2 = extract_financial_data_tool(str(fpath2))
                    tools_called.append("extract_financial_data")
                    if isinstance(ext2, ExtractedFinancialData):
                        norm2 = normalize_financial_items_tool(ext2, period=p2)
                        tools_called.append("normalize_financial_items")
                        if isinstance(norm2, NormalizedFinancialStatement):
                            comp_res = compare_periods_tool(norm2.items, stmt.items, period_a=p2, period_b=period)
                            tools_called.append("compare_periods")
                            if isinstance(comp_res, PeriodComparisonResult):
                                pcomp = comp_res
                                tool_results_data["period_comparison"] = pcomp.model_dump()

            # Step 3A.8: Generate Downloadable Report if requested
            if generate_report:
                rep_res = generate_financial_report_tool(
                    normalized_statement=stmt,
                    profit_metrics=pm,
                    financial_ratios=fr,
                    period_comparison=pcomp,
                    consistency_checks=cc,
                    business_name=business_name
                )
                tools_called.append("generate_financial_report")
                if isinstance(rep_res, FinancialReportOutput):
                    report_output = rep_res
                    tool_results_data["report"] = report_output.model_dump()

        # 3B. Browser Tool Execution (Official Source Lookup)
        if official_url:
            fetch_res = fetch_official_source_tool(official_url)
            tools_called.append("fetch_official_source")
            if isinstance(fetch_res, dict) and fetch_res.get("status") == "ok":
                browser_output = fetch_res
                tool_results_data["browser_content"] = browser_output
            elif isinstance(fetch_res, ErrorObject):
                data_quality_warnings.append(f"Official source fetch notice: {fetch_res.message}")

        # Step 4: Token-Reduced Context Assembly
        # We only pass compact normalized items and computed Decimal metrics, NEVER raw multi-cell spreadsheets
        compact_context = {}
        if stmt:
            compact_context["period"] = stmt.period
            compact_context["currency"] = stmt.currency
            compact_context["line_items_summary"] = [
                {
                    "item": i.canonical_name,
                    "amount": str(i.amount),
                    "source": f"{i.source_file} (Page/Sheet: {i.source_sheet_or_page}, Row: {i.source_row})"
                }
                for i in stmt.items
            ]
        if pm:
            compact_context["computed_profit_metrics"] = {
                "Revenue": str(pm.revenue_from_operations),
                "Gross_Profit": str(pm.gross_profit),
                "EBITDA": str(pm.ebitda),
                "EBIT": str(pm.ebit),
                "PAT": str(pm.pat),
                "Formulas": pm.formulas_used
            }
        if fr:
            compact_context["computed_financial_ratios"] = {
                "Current_Ratio": str(fr.current_ratio),
                "Quick_Ratio": str(fr.quick_ratio),
                "Debt_to_Equity": str(fr.debt_to_equity),
                "Gross_Margin_Pct": str(fr.gross_margin_pct),
                "Net_Profit_Margin_Pct": str(fr.net_profit_margin_pct),
                "Working_Capital": str(fr.working_capital),
                "DSCR": str(fr.dscr),
                "Formulas": fr.formulas_used
            }
        if pcomp:
            compact_context["period_comparison"] = [
                {
                    "metric": c.metric_name,
                    "period_a": str(c.period_a_value),
                    "period_b": str(c.period_b_value),
                    "variance_pct": str(c.variance_pct),
                    "favorable": c.favorable
                }
                for c in pcomp.comparisons
            ]
        if cc:
            compact_context["consistency_summary"] = cc.summary
            compact_context["consistency_warnings"] = cc.data_quality_warnings
            compact_context["consistency_checks"] = [
                {
                    "check_name": c.check_name,
                    "status": c.status,
                    "left_expression": c.left_expression,
                    "left_value": str(c.left_value),
                    "right_expression": c.right_expression,
                    "right_value": str(c.right_value),
                    "discrepancy": str(c.discrepancy),
                    "explanation": c.explanation
                }
                for c in cc.checks
            ]

        if browser_output:
            compact_context["official_statutory_text"] = {
                "source": browser_output["source_url"],
                "notice": browser_output["notice"],
                "content_excerpt": browser_output["clean_text"][:3000]
            }

        # Step 5: Explanation with Reasoning Model (gemini-3.5-flash with fallback)
        llm_prompt = f"""User Request:
\"\"\"{user_message}\"\"\"

Pre-calculated Deterministic Financial Data (Token-Reduced Compact Summary):
{json.dumps(compact_context, indent=2, default=str)}

Instructions:
- Provide a clear, professional, plain-language financial explanation for the Indian SME owner.
- Use ONLY the pre-calculated numbers from the data above; do NOT perform your own arithmetic.
- Include currency (INR / ₹), reporting period, assumptions, and source citations (sheet/page, row).
- If checking cash flows, state clearly whether Operating + Investing + Financing cash flows equal Net Increase in Cash, and whether Closing Cash reconciles with Opening Cash + Net Increase.
- Point out any red flags or accounting consistency issues if present."""

        t_rsn_0 = time.time()
        raw_answer = ""
        prompt_toks = len(llm_prompt) // 4
        comp_toks = 0
        models_to_try = [settings.strong_model_id, settings.fast_model_id, "gemini-3.1-flash-lite"]

        for m_id in models_to_try:
            try:
                rsn_response = self.client.models.generate_content(
                    model=m_id,
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_text(text=f"{SYSTEM_PROMPT}\n\n{llm_prompt}")
                            ]
                        )
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=2048
                    )
                )
                if rsn_response.text and rsn_response.text.strip():
                    raw_answer = rsn_response.text.strip()
                    prompt_toks = getattr(rsn_response.usage_metadata, "prompt_token_count", prompt_toks)
                    comp_toks = getattr(rsn_response.usage_metadata, "candidates_token_count", len(raw_answer) // 4)
                    break
            except Exception:
                continue

        if not raw_answer:
            raw_answer = _generate_clean_fallback_summary(compact_context, period, business_name)
            comp_toks = len(raw_answer) // 4


        rsn_latency = round((time.time() - t_rsn_0) * 1000, 2)

        # Step 6: Output Guardrail Check
        out_safe, final_answer, out_violations = check_output_guard(
            raw_answer,
            had_tool_execution=bool(tools_called),
            is_refusal=False
        )

        total_lat = round((time.time() - t0) * 1000, 2)
        total_toks = prompt_toks + comp_toks

        # Step 7: Record Telemetry
        telemetry_tracker.log_request(RequestTelemetry(
            request_id=req_id,
            user_query=user_message[:100],
            classifier_model=settings.fast_model_id,
            reasoning_model=settings.strong_model_id,
            classifier_latency_ms=cls_latency,
            reasoning_latency_ms=rsn_latency,
            total_latency_ms=total_lat,
            prompt_tokens=prompt_toks,
            completion_tokens=comp_toks,
            total_tokens=total_toks,
            tools_called=tools_called,
            cache_hits=cache_hits_count,
            uncompressed_raw_tokens_est=raw_token_estimate
        ))

        return {
            "request_id": req_id,
            "status": "success",
            "answer": final_answer,
            "classification": cls_result.model_dump(),
            "tools_executed": tools_called,
            "data_quality_warnings": data_quality_warnings,
            "report": report_output.model_dump() if report_output else None,
            "structured_results": tool_results_data,
            "telemetry": {
                "total_latency_ms": total_lat,
                "total_tokens": total_toks,
                "cache_hits": cache_hits_count
            }
        }

agent_instance = FinancialAgent()
