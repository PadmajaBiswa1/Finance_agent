import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Ensure .env is loaded from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings(BaseModel):
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    fast_model_id: str = Field(default_factory=lambda: os.getenv("FAST_MODEL_ID", "gemini-3.5-flash-lite"))
    strong_model_id: str = Field(default_factory=lambda: os.getenv("STRONG_MODEL_ID", "gemini-3.5-flash"))
    app_host: str = Field(default_factory=lambda: os.getenv("APP_HOST", "127.0.0.1"))
    app_port: int = Field(default_factory=lambda: int(os.getenv("APP_PORT", "8000")))
    max_upload_size_mb: int = Field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")))
    sandbox_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "15")))
    sandbox_memory_limit_mb: int = Field(default_factory=lambda: int(os.getenv("SANDBOX_MEMORY_LIMIT_MB", "256")))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    
    # Allowlisted Indian official domains for browser tool
    official_domains_allowlist: list[str] = [
        "rbi.org.in",
        "incometax.gov.in",
        "gst.gov.in",
        "mca.gov.in",
        "icai.org",
        "sebi.gov.in",
    ]

    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    reports_dir: Path = BASE_DIR / "reports"
    uploads_dir: Path = BASE_DIR / "uploads"

settings = Settings()

# Ensure directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.reports_dir.mkdir(parents=True, exist_ok=True)
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
