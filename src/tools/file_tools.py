from pathlib import Path
from typing import Union
from src.models.financial_schemas import FileValidationResult, ExtractedFinancialData, ErrorObject
from src.sandbox.file_validator import validate_financial_file as _validate_file
from src.sandbox.worker import run_sandboxed_parser

def validate_financial_file_tool(file_path: str) -> Union[FileValidationResult, ErrorObject]:
    """
    ADK Function Tool: Validates an uploaded financial statement file.
    Performs file size, extension, and magic-byte checks. Rejects executables and macros.
    """
    try:
        if not file_path or not str(file_path).strip():
            return ErrorObject(
                error_code="INVALID_ARGUMENT",
                message="file_path argument cannot be empty.",
                details={"provided_path": file_path}
            )
        return _validate_file(file_path)
    except Exception as exc:
        return ErrorObject(
            error_code="VALIDATION_TOOL_ERROR",
            message=f"Validation tool encountered an unexpected error: {str(exc)}",
            details={"exception": type(exc).__name__}
        )

def extract_financial_data_tool(file_path: str) -> Union[ExtractedFinancialData, ErrorObject]:
    """
    ADK Function Tool: Extracts raw financial tables from CSV, XLSX, or PDF in an isolated process.
    Never executes formulas or macros; treats all cell content as data.
    """
    try:
        if not file_path or not str(file_path).strip():
            return ErrorObject(
                error_code="INVALID_ARGUMENT",
                message="file_path argument cannot be empty.",
                details={"provided_path": file_path}
            )
        return run_sandboxed_parser(file_path)
    except Exception as exc:
        return ErrorObject(
            error_code="EXTRACTION_TOOL_ERROR",
            message=f"Extraction tool encountered an unexpected error: {str(exc)}",
            details={"exception": type(exc).__name__}
        )
