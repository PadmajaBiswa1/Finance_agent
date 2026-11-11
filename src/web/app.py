import os
import shutil
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.agent.financial_agent import agent_instance
from src.agent.telemetry import telemetry_tracker

app = FastAPI(
    title="Indian SME Finance Agent API",
    description="Specialist Business & Finance AI Agent for Indian Small Businesses",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Mount static and reports directories
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/reports", StaticFiles(directory=str(settings.reports_dir)), name="reports")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Finance Agent UI not found</h1>", status_code=404)
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.post("/api/chat")
async def chat_endpoint(
    message: str = Form(...),
    file: Optional[UploadFile] = File(None),
    sample_name: Optional[str] = Form(None),
    second_file: Optional[UploadFile] = File(None),
    official_url: Optional[str] = Form(None),
    generate_report: bool = Form(True),
    business_name: str = Form("Indian SME Enterprise"),
    period: str = Form("FY 2023-24"),
    comparison_period: Optional[str] = Form(None)
):
    saved_file_path: Optional[Path] = None
    saved_second_file_path: Optional[Path] = None

    try:
        # Save primary uploaded file if present
        if file and file.filename:
            safe_filename = Path(file.filename).name
            saved_file_path = settings.uploads_dir / safe_filename
            with open(saved_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        elif sample_name:
            # Fallback to server sample file if user selected a preloaded sample
            safe_sample = Path(sample_name).name
            candidate_sample = settings.data_dir / "samples" / safe_sample
            if candidate_sample.exists():
                saved_file_path = candidate_sample

        # Save secondary uploaded file if present
        if second_file and second_file.filename:
            safe_sec_filename = Path(second_file.filename).name
            saved_second_file_path = settings.uploads_dir / safe_sec_filename
            with open(saved_second_file_path, "wb") as buffer:
                shutil.copyfileobj(second_file.file, buffer)

        result = agent_instance.analyze(
            user_message=message,
            uploaded_file_path=saved_file_path,
            second_file_path=saved_second_file_path,
            official_url=official_url,
            generate_report=generate_report,
            business_name=business_name,
            period=period,
            comparison_period=comparison_period
        )
        return result

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        # Clean up temporary uploads
        if file:
            await file.close()
        if second_file:
            await second_file.close()

@app.get("/api/telemetry")
async def get_telemetry():
    return telemetry_tracker.get_summary()

@app.get("/api/samples")
async def list_sample_files():
    samples = []
    samples_dir = settings.data_dir / "samples"
    if samples_dir.exists():
        for p in samples_dir.glob("*.*"):
            samples.append({
                "filename": p.name,
                "size_bytes": p.stat().st_size,
                "extension": p.suffix
            })
    return {"samples": samples}

@app.get("/api/samples/{filename}")
async def get_sample_file(filename: str):
    safe_name = Path(filename).name
    sample_path = settings.data_dir / "samples" / safe_name
    if not sample_path.exists() or not sample_path.is_file():
        raise HTTPException(status_code=404, detail=f"Sample file '{safe_name}' not found.")
    media_type = "application/pdf" if safe_name.endswith(".pdf") else (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if safe_name.endswith(".xlsx") else "text/csv"
    )
    return FileResponse(path=str(sample_path), filename=safe_name, media_type=media_type)
