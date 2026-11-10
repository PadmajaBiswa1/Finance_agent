# FinanceAgent: Indian SME Specialist AI Financial Analyst

A specialist Business & Finance AI agent built for Indian small and medium enterprises (MSMEs/SMEs) using Python 3.11+, Google GenAI / ADK, and Gemini models.

---

## 🌟 Key Features

1. **Deterministic Decimal Arithmetic**:
   - Zero LLM arithmetic hallucinations. All calculations (EBITDA, Gross Profit, Current Ratio, Quick Ratio, Debt-to-Equity, Working Capital, DSCR, ROCE, variances) are computed in Python using `decimal.Decimal` with standard `ROUND_HALF_UP` rounding.
   - Missing fields return `"unavailable"`, never fictitious guesses.

2. **Process-Isolated File Parsing Sandbox**:
   - Isolated `multiprocessing` worker with no network access and scrubbed secrets.
   - Enforces 10MB size limits, 15-second execution timeouts, and magic-byte checks (`%PDF-`, `PK\x03\x04`).
   - Rejects binary executables and macro-enabled (`.xlsm` / `vbaProject.bin`) workbooks.
   - All cell contents treated strictly as passive data, never instructions.

3. **Two-Tier Scope Enforcement & Guardrails**:
   - Deterministic pre-filter + Fast model classifier (`gemini-3.5-flash-lite`).
   - Fails closed (`allowed: False`) on invalid outputs or errors.
   - Strict scope adherence: handles only business finance; politely refuses medical, legal, entertainment, general coding, personal Hinglish gossip, and jailbreaks.
   - Evaluated across 74 labeled prompts with **100% precision, 100% recall, and zero false accepts**.
   - Input guardrail blocks prompt injection and autonomous action execution (wire transfers, tax filings).
   - Output guardrail prevents system prompt leaks, false execution claims, and redacts Indian PII (PAN, Aadhaar, Phone, Email, Bank Accounts).

4. **Official Statutory Browser Tool**:
   - Read-only tool restricted strictly to Indian official domains (`rbi.org.in`, `incometax.gov.in`, `gst.gov.in`, `mca.gov.in`, `icai.org`, `sebi.gov.in`).
   - Fetches clean text without JavaScript, logins, or forms, caps response size at 500KB, blocks redirects off the allowlist, and tags content as untrusted external.

5. **Token Reduction & Cost Optimization**:
   - Extract-once architecture: parses files once into compact canonical representations.
   - Injects compact structured JSON summaries into the strong reasoning model (`gemini-3.5-flash`), achieving an **86% token reduction** compared to raw context dumping.
   - SHA-256 hash-keyed caching of parsed statements and calculations.

6. **Interactive Web Interface & Audit Reports**:
   - Built with FastAPI, HTML5, CSS3, and modern JavaScript.
   - Visualizes tool execution steps, source citations (file, sheet/page, row), and data-quality warnings.
   - Generates downloadable reports in HTML, Markdown, and JSON.

---

## 🚀 Quickstart & How to Run Locally

### 1. Prerequisites
- Python 3.11+ installed.
- Virtual environment with dependencies installed:
  ```powershell
  cd finance-agent
  uv venv
  .\.venv\Scripts\activate
  uv pip install -e .
  ```

### 2. Configuration (`.env`)
The `.env` file contains your configuration and Gemini models:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
FAST_MODEL_ID=gemini-3.5-flash-lite
STRONG_MODEL_ID=gemini-3.5-flash
APP_HOST=127.0.0.1
APP_PORT=8000
MAX_UPLOAD_SIZE_MB=10
SANDBOX_TIMEOUT_SECONDS=15
```

### 3. Run the Test Suites
Run all unit tests, sandbox security tests, guardrail evaluations, and scope classifier benchmarks:
```powershell
# Run tool unit tests (hand-verified Indian SME fixtures)
.\.venv\Scripts\pytest.exe tests\test_tools.py

# Run sandbox isolation and security tests
.\.venv\Scripts\pytest.exe tests\test_sandbox.py

# Run guardrail, PII redaction, and prompt injection tests
.\.venv\Scripts\pytest.exe tests\test_guardrails.py

# Run scope classifier benchmark (74 prompts, zero false accepts)
.\.venv\Scripts\pytest.exe -s tests\test_classifier_scope.py

# Run 18 end-to-end conversation flows
.\.venv\Scripts\pytest.exe tests\test_end_to_end_agent.py
```

### 4. Start the Application & Web UI
Start the FastAPI server:
```powershell
.\.venv\Scripts\python.exe -m uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser and navigate to:
**http://127.0.0.1:8000**

---

## 📁 Repository Structure
```
finance-agent/
├── .env                       # API key and model IDs
├── PROJECT_RULES.md           # Core architecture & safety rules
├── pyproject.toml             # Dependencies & pytest configuration
├── README.md                  # Documentation and running guide
├── docs/
│   ├── architecture.md        # Detailed system design & Mermaid diagram
│   └── token_cost_report.md   # Before/after token reduction & cost benchmark
├── src/
│   ├── config.py              # Typed settings & domain allowlist
│   ├── prompts.py             # System prompt, workflow, few-shots, refusal text
│   ├── models/                # Pydantic schemas (Classifier, Financial, Reports)
│   ├── sandbox/               # Isolated multiprocessing parser & magic byte checks
│   ├── tools/                 # ADK function tools (Decimal arithmetic, browser)
│   ├── guardrails/            # Input/Output guards, classifier, PII redactor
│   ├── agent/                 # Agent orchestrator, SHA-256 cache, telemetry
│   └── web/                   # FastAPI backend & single-page application
├── data/
│   └── samples/               # Indian SME sample statements (CSV, XLSX, PDF)
└── tests/
    ├── conftest.py            # Hand-verified Indian SME fixtures
    ├── test_tools.py          # Unit tests for all 8 tools + browser
    ├── test_sandbox.py        # Malformed files, macro rejection, timeout tests
    ├── test_guardrails.py     # Injection, PII redaction, action blocking tests
    ├── test_classifier_scope.py # 74-prompt precision/recall benchmark (0 false accepts)
    └── test_end_to_end_agent.py # 18 end-to-end agent conversation evaluations
```
