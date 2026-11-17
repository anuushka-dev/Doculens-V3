# DocuLens

Live: https://doculens-v3.onrender.com

**Evidence-First PDF Question Answering with Hybrid RAG, Deterministic Citation Verification, and Multi-Provider AI Models**

DocuLens is a fast, browser-based document intelligence application built with **Python 3.12, FastAPI, FAISS, Sentence Transformers, BM25, PyMuPDF, and Modular ES6 JavaScript**. Upload any text-selectable PDF, connect **official, third-party, or custom AI provider API keys** (or optional local Ollama), ask questions in plain English or Hinglish, and get grounded answers linked directly to exact verified quotes and PDF page numbers.

---

## What This Project Does

Traditional LLM PDF chats often hallucinate page numbers or blend outside knowledge into document answers. DocuLens prevents that with a strict multi-stage pipeline:

1. **Isolated PDF Ingestion:** Extracts text page-by-page using PyMuPDF inside an isolated subprocess (up to **20 MiB**, **350 pages**, and **4,000,000 characters**).
2. **Hybrid Retrieval:** Combines **FAISS dense vector search** (`all-MiniLM-L6-v2`) with **BM25 lexical search** via Reciprocal Rank Fusion, plus a **single-pass fast path** for short documents (`<= 5` pages or `<= 8` chunks) and `Low` effort mode.
3. **Structured AI Generation:** Queries your selected AI model with a strict Pydantic JSON schema.
4. **Deterministic Citation Verification:** Checks every returned quote against exact character spans (`start_char:end_char`) in the source PDF pages. If the evidence is insufficient, DocuLens explicitly abstains rather than guessing.

---

## Features

- **14 Supported AI Providers & Dual Custom Gateways (`☰ Models & Keys`):**
  - **Official APIs:** OpenAI, Google Gemini, Anthropic Claude, DeepSeek, Mistral AI, xAI Grok.
  - **Third-Party Aggregators:** Groq Cloud (LPU), OpenRouter (200+ models), Together AI, Fireworks AI, Cerebras.
  - **Custom OpenAI-Compatible & Custom Anthropic-Compatible Slots:** Add both OpenAI-protocol (`/v1/chat/completions`) and Anthropic-protocol (`/v1/messages`) third-party proxies simultaneously (e.g., VNAI Pro, DeepInfra, NVIDIA NIM, SiliconFlow, Z.ai, MiniMax, LiteLLM, vLLM), with automatic URL normalization and built-in quick presets.
  - **Optional Local Fallback:** Ollama (`http://127.0.0.1:11434`).
- **Live Model Auto-Discovery:** Paste an API key (plus Base URL for custom providers) to automatically pull up to **80 live models** from `/models`, or specify an explicit `Model ID` override for proxies that do not expose `/models`.
- **Bottom Composer Controls:** Switch models inline next to your question box with dynamic **company SVG logos** and **4 reasoning/verification effort tiers** (`Low`, `Medium`, `High`, `Max`).
- **Smart Prompt Auto-Repair & Clarification:** Automatically cleans typos, shorthand, and Hinglish queries (plus a manual `✨ Polish` button), resolves **6-turn** follow-up context, and presents clickable clarification suggestions when a question is ambiguous.
- **Interactive Source Inspection:** Click any citation badge to view the exact highlighted passage or inspect the original rendered PDF page (`Prev` / `Next` / `Copy page`) and export transcripts as Markdown.
- **Security & Session Isolation:** Token-scoped in-memory document sessions (`X-Document-Token`, up to `8` concurrent PDFs, `1`-hour TTL), strict CSP (`style-src 'self'`), upload size caps, and masked API key persistence.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend API** | Python 3.12+, FastAPI, Uvicorn (single worker), Pydantic v2 |
| **PDF & Retrieval** | PyMuPDF (`fitz`), FAISS (`faiss-cpu`), Sentence Transformers (`all-MiniLM-L6-v2`), BM25 |
| **LLM Gateway** | Async `httpx` / `httpx2` client supporting OpenAI, Gemini, Anthropic, & Ollama protocols |
| **Frontend** | Zero-build Vanilla ES6 JavaScript modules, CSS3, HTML5 |
| **Tooling & Containers** | `run_doculens.py`, `uv`, Docker (non-root), Docker Compose, Pytest, Node.js test runner |

---

## Prerequisites

- **Python 3.12+** (required for local setup and running `run_doculens.py`)
- **`uv`** *(recommended for creating a clean `./doculens` virtual environment automatically during `setup`)*
- **Docker & Docker Compose** *(optional — required only for `docker` and `compose` modes)*
- **Node.js 20+** *(optional — used by `check` mode for frontend syntax and module tests)*
- **Ollama** *(optional — only needed if running local models offline instead of cloud API keys)*

---

## Setup & How to Run (`run_doculens.py`)

DocuLens includes a single cross-platform control script (**[run_doculens.py](run_doculens.py)**) for Windows, WSL, Linux, and macOS.

### Interactive Menu
Run the script without arguments to choose any mode interactively:

```bash
python run_doculens.py
```

```text
[1] Run Locally              (http://127.0.0.1:8000)
[2] Run with Docker          (Standalone container)
[3] Run with Docker Compose  (API + Ollama stack)
[4] Setup Only               (Prepare .env/venv, start nothing)
[5] Check Everything         (Verify deps, Docker & tests)
[6] Stop Docker / Compose    (Clean stop containers)
```

> **Windows note:** If `python` is not on your `PATH`, use `py -3.12 run_doculens.py <command>`.

### 1. Setup Only (Prepare Environment, Start Nothing)
Creates `.env` from `.env.example`, ensures `data/` exists, cleans any stray Windows `Zone.Identifier` files, installs Python dependencies into `./doculens` via `uv` (if not already present on your Python 3.12 runtime), and stops without launching any service:

```bash
python run_doculens.py setup
```

### 2. Verify Everything (`check`)
Checks required files, Python imports, Docker daemon & `compose.yaml` validity, port `8000` availability, frontend JS syntax/module tests, and Python unit tests:

```bash
python run_doculens.py check          # Fast verification suite
python run_doculens.py check --full   # Run entire pytest suite
```

### 3. Run Locally (`local`)
Prepares configuration/runtime if needed and starts FastAPI on **`http://127.0.0.1:8000`**, automatically opening your browser:

```bash
python run_doculens.py local
python run_doculens.py local --no-browser   # Start server without opening browser
```

### 4. Run with Docker (`docker`)
Builds `doculens-api:0.2.0` from [Dockerfile](Dockerfile) and runs DocuLens in a standalone non-root container (`doculens-app`) with persistent named volumes for HuggingFace embeddings and provider config:

```bash
python run_doculens.py docker         # Build & run in foreground
python run_doculens.py docker -d      # Build & run detached in background
python run_doculens.py stop           # Stop and remove container
```

### 5. Run with Docker Compose (`compose`)
Builds and launches the hardened `api` container together with an internal `ollama` container from [compose.yaml](compose.yaml):

```bash
python run_doculens.py compose        # Build & start stack in foreground
python run_doculens.py compose -d     # Build & start detached in background
python run_doculens.py stop           # Stop Compose stack
```

### Changing the Port
Set `DOCULENS_PORT` before running any launch mode (default `8000`):

```bash
DOCULENS_PORT=8080 python run_doculens.py local
```

---

## Connecting AI Provider API Keys

You do **not** need local GPUs or Ollama to use DocuLens:

1. Open **`http://127.0.0.1:8000`** in your browser.
2. Click **`☰ Models & Keys`** in the top-right header.
3. Choose any **Official**, **Third-Party**, **Custom OpenAI-Compatible**, or **Custom Anthropic-Compatible** provider (or leave on **Auto-Detect**), paste your raw API key (and Base URL if using a custom gateway), then click **`Add Key & Auto-Pull Models`**.
4. Pick your active model and reasoning **Effort** (`Low`, `Medium`, `High`, `Max`) in the bottom composer bar.

You can also pre-configure API keys in `.env` (see [.env.example](.env.example)).

---

## Configuration & Limits (`.env`)

| Variable | Default | Description |
|---|---|---|
| `DOCULENS_PORT` | `8000` | Localhost port for FastAPI |
| `DOCULENS_RETRIEVAL_MODE` | `hybrid` | `hybrid` (FAISS + BM25) or `lexical` (keyword-only offline) |
| `DOCULENS_RETRIEVAL_TOP_K` | `8` | Base chunks retrieved per query |
| `DOCULENS_EVIDENCE_THRESHOLD` | `0.25` | Minimum evidence score threshold |
| `DOCULENS_MAX_UPLOAD_BYTES` | `20971520` | Max PDF file size (`20 MiB`) |
| `DOCULENS_MAX_PDF_PAGES` | `350` | Max PDF page count |
| `DOCULENS_DOCUMENT_TTL_SECONDS` | `3600` | In-memory session lifetime (`1 hour`) |
| `DOCULENS_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Optional local Ollama endpoint |
| `DOCULENS_OLLAMA_MODEL` | `qwen3.5:4b` | Default local Ollama model |

> Keep `--workers 1` when launching Uvicorn manually — uploaded document sessions and retrieval indexes live in single-process memory.

---

## API Overview

Interactive Swagger docs are available at **`http://127.0.0.1:8000/docs`**.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Web workspace UI |
| `GET` | `/health` | Process liveness check (`200 OK`) |
| `GET` | `/ready` | Active AI model / Ollama readiness (`200` or `503`) |
| `GET` | `/api/status` | Active model, limits, and workspace status |
| `GET` | `/api/providers` | Configured providers, pulled models, and effort level |
| `POST` | `/api/providers/key` | Register key + custom Base URL and auto-pull live models |
| `POST` | `/api/providers/select` | Switch active provider, model, and effort |
| `POST` | `/api/documents` | Upload & index a PDF (returns `document_id` + `document_token`) |
| `POST` | `/api/documents/{id}/ask` | Ask a question with verified citations (`X-Document-Token`) |
| `GET` | `/api/documents/{id}/pages/{n}` | Inspect raw extracted text of PDF page `n` |
| `POST` | `/api/prompts/enhance` | Clean/polish rough or Hinglish prompts |

---

## Running Tests Manually

```bash
# Quick integrated check (Python deps, Docker/compose, JS syntax & unit tests)
python run_doculens.py check --full

# Direct test commands
pytest -q
ruff check .
npm run check
node --test tests/web/modules.test.cjs
```

*(Note: `npm test` runs `tests/web/workspace.test.cjs`, which requires `jsdom` via `npm ci --ignore-scripts`.)*

---

## Troubleshooting

- **First run downloads embeddings:** `hybrid` mode downloads `sentence-transformers/all-MiniLM-L6-v2` on first document upload. For instant offline keyword search, set `DOCULENS_RETRIEVAL_MODE=lexical` in `.env`.
- **Custom 3rd-party gateway returns `404` on `/models`:** Expand **Custom 3rd-Party Base URL / Proxy**, enter an explicit `Model ID`, and submit again — DocuLens connects directly without requiring `/models`.
- **Port `8000` already in use:** Stop the existing process or run `DOCULENS_PORT=8080 python run_doculens.py local`.
- **Scanned / image-only PDFs:** DocuLens requires selectable text; run OCR on scanned PDFs before uploading.
