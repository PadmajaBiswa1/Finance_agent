import hashlib
import os
import zipfile
from pathlib import Path
from typing import Literal
from src.models.financial_schemas import FileValidationResult, ErrorObject
from src.config import settings

MAGIC_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "xlsx": [b"PK\x03\x04"],  # Standard ZIP signature
}

EXECUTABLE_SIGNATURES = [
    b"MZ",          # Windows PE/EXE
    b"\x7fELF",     # Linux ELF
    b"\xca\xfe\xba\xbe", # Mach-O
    b"#!/bin/",     # Unix script
    b"#!/usr/",
    b"<?php",
    b"<script",
]

def calculate_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def validate_financial_file(file_path: str | Path) -> FileValidationResult | ErrorObject:
    """
    Validates a file for financial analysis:
    - Verifies path exists and is a regular file
    - Enforces size limit (e.g. 10MB)
    - Verifies magic-bytes match declared extension
    - Rejects binary executables and macro-enabled workbooks
    - Computes SHA256
    """
    try:
        path = Path(file_path).resolve()
        if not path.is_file():
            return ErrorObject(
                error_code="FILE_NOT_FOUND",
                message=f"File not found at path: {file_path}",
                details={"file_path": str(file_path)}
            )

        size_bytes = path.stat().st_size
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if size_bytes > max_bytes:
            return ErrorObject(
                error_code="FILE_TOO_LARGE",
                message=f"File size {size_bytes} bytes exceeds maximum allowed {max_bytes} bytes ({settings.max_upload_size_mb} MB)",
                details={"size_bytes": size_bytes, "max_bytes": max_bytes}
            )

        if size_bytes == 0:
            return ErrorObject(
                error_code="EMPTY_FILE",
                message="Uploaded file is empty (0 bytes).",
                details={"filename": path.name}
            )

        # Read first 1024 bytes for magic byte checks
        with open(path, "rb") as f:
            header = f.read(1024)

        # Check for dangerous executable signatures
        for bad_sig in EXECUTABLE_SIGNATURES:
            if header.startswith(bad_sig):
                return ErrorObject(
                    error_code="UNSAFE_FILE_SIGNATURE",
                    message="File header indicates executable or script content, which is strictly prohibited.",
                    details={"matched_signature": str(bad_sig)}
                )

        ext = path.suffix.lower().lstrip(".")
        detected_type: Literal["csv", "xlsx", "pdf", "unknown"] = "unknown"
        validation_errors: list[str] = []

        if ext == "pdf":
            detected_type = "pdf"
            if not any(header.startswith(sig) for sig in MAGIC_SIGNATURES["pdf"]):
                validation_errors.append("Invalid PDF magic bytes: missing %PDF- header.")
        elif ext in ("xlsx", "xls"):
            detected_type = "xlsx"
            if not any(header.startswith(sig) for sig in MAGIC_SIGNATURES["xlsx"]):
                validation_errors.append("Invalid XLSX magic bytes: not a valid PK zip archive.")
            else:
                # Check for macro components (VBA) inside zip
                try:
                    with zipfile.ZipFile(path, 'r') as zf:
                        namelist = zf.namelist()
                        if any("vbaproject.bin" in name.lower() for name in namelist):
                            return ErrorObject(
                                error_code="MACRO_ENABLED_PROHIBITED",
                                message="Workbook contains VBA macros (vbaProject.bin). Macro execution is strictly blocked.",
                                details={"filename": path.name}
                            )
                except zipfile.BadZipFile:
                    validation_errors.append("Corrupted ZIP structure in XLSX file.")
        elif ext == "csv":
            detected_type = "csv"
            # Verify CSV is text and doesn't contain null bytes
            if b"\x00" in header:
                validation_errors.append("CSV file contains binary null bytes.")
            else:
                try:
                    header.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        header.decode("latin-1")
                    except Exception:
                        validation_errors.append("CSV is not valid UTF-8 or Latin-1 text.")
        else:
            return ErrorObject(
                error_code="UNSUPPORTED_FILE_TYPE",
                message=f"Unsupported file extension: .{ext}. Allowed extensions: .csv, .xlsx, .pdf",
                details={"extension": ext}
            )

        sha256 = calculate_sha256(path)
        is_valid = len(validation_errors) == 0

        mime_map = {
            "pdf": "application/pdf",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv",
            "unknown": "application/octet-stream",
        }

        return FileValidationResult(
            status="ok" if is_valid else "error",
            filename=path.name,
            file_type=detected_type,
            file_size_bytes=size_bytes,
            sha256_hash=sha256,
            mime_type=mime_map.get(detected_type, "application/octet-stream"),
            is_valid=is_valid,
            validation_errors=validation_errors
        )

    except Exception as exc:
        return ErrorObject(
            error_code="VALIDATION_SYSTEM_ERROR",
            message=f"Internal validation error: {str(exc)}",
            details={"exception": type(exc).__name__}
        )
