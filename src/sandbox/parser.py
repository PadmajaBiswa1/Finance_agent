import csv
import re
from pathlib import Path
from typing import Any
import openpyxl
from pypdf import PdfReader

from src.models.financial_schemas import (
    ExtractedFinancialData,
    ExtractedTable,
    ExtractedRow,
    ErrorObject,
)

INJECTION_PATTERNS = [
    re.compile(r"\[/?(inst|sys|system|assistant|user)\]", re.IGNORECASE),
    re.compile(r"<\|im_(start|end)\|>", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(DAN|unconstrained|in\s+developer\s+mode)", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
]

def sanitize_cell_text(text: Any) -> str:
    """
    Sanitizes cell contents:
    1. Converts to string.
    2. Strips leading formula indicators (=, +, -, @) to prevent CSV injection.
    3. Neutralizes prompt-injection patterns so cell text is strictly data, never instructions.
    """
    if text is None:
        return ""
    val = str(text).strip()
    
    # Strip dangerous formula injection prefixes
    if val.startswith(("=", "+", "-", "@")):
        val = "'" + val.lstrip("=+-@")
        
    # Neutralize prompt injection tokens
    for pat in INJECTION_PATTERNS:
        val = pat.sub("[SANITIZED_DATA]", val)
        
    return val

def parse_csv_file(path: Path) -> ExtractedTable:
    """Parses a CSV file safely without formula execution."""
    rows: list[ExtractedRow] = []
    header: list[str] = []
    
    # Try UTF-8 then Latin-1
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=encoding, errors="replace") as f:
                reader = csv.reader(f)
                for idx, row in enumerate(reader, start=1):
                    sanitized_row = [sanitize_cell_text(c) for c in row if c is not None]
                    if not sanitized_row or not any(sanitized_row):
                        continue
                    if not header:
                        header = sanitized_row
                    label = sanitized_row[0] if sanitized_row else ""
                    values = sanitized_row[1:] if len(sanitized_row) > 1 else []
                    cell_dict = {f"col_{i+1}": cell for i, cell in enumerate(sanitized_row)}
                    rows.append(ExtractedRow(
                        row_number=idx,
                        raw_label=label,
                        values=values,
                        raw_cells=cell_dict
                    ))
            break
        except Exception:
            continue
            
    return ExtractedTable(
        sheet_or_page=path.stem,
        table_type="csv_table",
        header=header,
        rows=rows
    )

def parse_xlsx_file(path: Path) -> list[ExtractedTable]:
    """Parses an XLSX file using openpyxl in data_only and read_only mode."""
    tables: list[ExtractedTable] = []
    # data_only=True ensures formulas are never executed, reading only evaluated values
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True, keep_vba=False)
    
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        rows: list[ExtractedRow] = []
        header: list[str] = []
        
        for row_idx, row_cells in enumerate(sheet.iter_rows(values_only=True), start=1):
            if row_cells is None:
                continue
            sanitized = [sanitize_cell_text(cell) for cell in row_cells]
            # Skip empty rows
            if not any(sanitized):
                continue
            if not header:
                header = sanitized
            label = sanitized[0] if sanitized else ""
            values = sanitized[1:] if len(sanitized) > 1 else []
            cell_dict = {f"col_{i+1}": cell for i, cell in enumerate(sanitized)}
            rows.append(ExtractedRow(
                row_number=row_idx,
                raw_label=label,
                values=values,
                raw_cells=cell_dict
            ))
            
        tables.append(ExtractedTable(
            sheet_or_page=sheet_name,
            table_type="xlsx_sheet",
            header=header,
            rows=rows
        ))
        
    wb.close()
    return tables

def parse_pdf_file(path: Path) -> list[ExtractedTable]:
    """Parses text-PDF financial statements using pypdf."""
    tables: list[ExtractedTable] = []
    reader = PdfReader(path)
    
    for page_idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        lines = text.splitlines()
        rows: list[ExtractedRow] = []
        header: list[str] = []
        
        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue
            # Split line on 2 or more spaces or tabs
            parts = re.split(r"\s{2,}|\t+", line)
            parts = [sanitize_cell_text(p) for p in parts if p.strip()]
            if not parts:
                continue
            if not header and len(parts) > 1:
                header = parts
            label = parts[0]
            values = parts[1:] if len(parts) > 1 else []
            cell_dict = {f"col_{i+1}": p for i, p in enumerate(parts)}
            rows.append(ExtractedRow(
                row_number=line_num,
                raw_label=label,
                values=values,
                raw_cells=cell_dict
            ))
            
        tables.append(ExtractedTable(
            sheet_or_page=f"Page {page_idx}",
            table_type="pdf_page_table",
            header=header,
            rows=rows
        ))
        
    return tables

def parse_file_untrusted(file_path: Path, sha256_hash: str) -> ExtractedFinancialData:
    """Parses an untrusted financial file and returns structured tables."""
    ext = file_path.suffix.lower().lstrip(".")
    if ext == "csv":
        tables = [parse_csv_file(file_path)]
    elif ext in ("xlsx", "xls"):
        tables = parse_xlsx_file(file_path)
    elif ext == "pdf":
        tables = parse_pdf_file(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
        
    return ExtractedFinancialData(
        status="ok",
        filename=file_path.name,
        sha256_hash=sha256_hash,
        tables=tables,
        metadata={"table_count": len(tables), "extension": ext}
    )
