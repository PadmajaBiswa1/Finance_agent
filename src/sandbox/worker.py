import os
import multiprocessing
import traceback
from pathlib import Path
from typing import Union

from src.config import settings
from src.models.financial_schemas import ExtractedFinancialData, ErrorObject, FileValidationResult
from src.sandbox.file_validator import validate_financial_file
from src.sandbox.parser import parse_file_untrusted

def _isolated_parse_target(file_path_str: str, sha256_hash: str, conn):
    """
    Worker function executed in a separate, isolated process.
    - Strips all secrets from the environment
    - No network access (does not import or initialize network sockets)
    - Parses file into pure JSON-serializable dictionaries
    """
    try:
        # Scrub secrets from the child process environment
        for k in list(os.environ.keys()):
            upper_k = k.upper()
            if any(secret_term in upper_k for secret_term in ("KEY", "SECRET", "TOKEN", "AUTH", "PASS", "CRED")):
                del os.environ[k]

        path = Path(file_path_str)
        extracted = parse_file_untrusted(path, sha256_hash)
        conn.send({"status": "ok", "data": extracted.model_dump()})
    except Exception as exc:
        conn.send({
            "status": "error",
            "error_code": "PARSER_PROCESS_ERROR",
            "message": str(exc),
            "details": {"traceback": traceback.format_exc()[:500]}
        })
    finally:
        conn.close()

def run_sandboxed_parser(file_path: Union[str, Path]) -> Union[ExtractedFinancialData, ErrorObject]:
    """
    Orchestrates validation and sandboxed extraction in an isolated child process:
    1. Pre-validates file (magic bytes, size, macro prohibition).
    2. Spawns isolated process with timeout.
    3. Returns parsed structured data or structured ErrorObject.
    """
    path = Path(file_path).resolve()
    val_result = validate_financial_file(path)
    if isinstance(val_result, ErrorObject):
        return val_result
    if not val_result.is_valid:
        return ErrorObject(
            error_code="INVALID_FILE_FORMAT",
            message=f"File validation failed: {'; '.join(val_result.validation_errors)}",
            details={"errors": val_result.validation_errors}
        )

    parent_conn, child_conn = multiprocessing.Pipe()
    process = multiprocessing.Process(
        target=_isolated_parse_target,
        args=(str(path), val_result.sha256_hash, child_conn)
    )

    try:
        process.start()
        # Enforce timeout limit
        timeout = settings.sandbox_timeout_seconds
        process.join(timeout=timeout)

        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
            return ErrorObject(
                error_code="TIMEOUT_EXCEEDED",
                message=f"Sandboxed file parsing timed out after {timeout} seconds.",
                details={"timeout_seconds": timeout, "filename": path.name}
            )

        if process.exitcode != 0:
            return ErrorObject(
                error_code="PROCESS_CRASHED",
                message=f"Sandboxed parsing process crashed with exit code {process.exitcode}.",
                details={"exit_code": process.exitcode}
            )

        if parent_conn.poll():
            msg = parent_conn.recv()
            if msg.get("status") == "ok":
                return ExtractedFinancialData.model_validate(msg["data"])
            else:
                return ErrorObject(
                    error_code=msg.get("error_code", "PARSER_FAILED"),
                    message=msg.get("message", "File parsing failed"),
                    details=msg.get("details", {})
                )
        else:
            return ErrorObject(
                error_code="NO_DATA_FROM_PARSER",
                message="Parser worker exited without returning data."
            )

    except Exception as exc:
        return ErrorObject(
            error_code="SANDBOX_RUNNER_ERROR",
            message=f"Sandbox execution failed: {str(exc)}",
            details={"exception": type(exc).__name__}
        )
    finally:
        parent_conn.close()
