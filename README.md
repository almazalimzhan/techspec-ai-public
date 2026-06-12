# TechSpec AI: Procurement PDF Analyzer

[![CI](https://github.com/almazalimzhan/techspec-ai-public/actions/workflows/ci.yml/badge.svg)](https://github.com/almazalimzhan/techspec-ai-public/actions/workflows/ci.yml)

TechSpec AI is a portfolio prototype for analyzing technical specification PDFs from procurement workflows. It combines PDF text extraction, embeddings, semantic retrieval, and LLM prompts to produce summaries, structured JSON fields, risk notes, and document-level Q&A in Russian and Kazakh.

## Business Problem

Procurement and sales teams often review long technical specification documents under time pressure. Key information such as service scope, deadlines, payment terms, customer identifiers, technical constraints, and supplier risks can be scattered across many pages. Manual review is slow and error-prone.

## Objective

The objective of this project is to demonstrate a practical RAG-style document analysis workflow:

- extract text from procurement PDF documents
- split the text into searchable chunks
- build a vector index for semantic retrieval
- retrieve relevant context for each task
- use LLM prompts to generate summaries, JSON fields, risk analysis, and answers to user questions

## Dataset Description

This public portfolio version uses synthetic sample data only. Real procurement PDFs, usage logs, and local runtime databases are excluded from the repository.

Synthetic sample files are available in `data/sample/`, including `sample_tech_spec_ru.pdf`. To regenerate the demo PDF after installing dependencies, run:

```bash
python scripts/generate_sample_pdf.py
```

## Methodology

1. PDF pages are extracted with PyMuPDF.
2. Text is cleaned and split into overlapping chunks.
3. Embeddings are generated with local Ollama `nomic-embed-text`.
4. Docker runtime stores chunk vectors in Qdrant; FAISS remains available as an in-process fallback.
5. Dense retrieval is combined with keyword scoring for procurement-specific questions.
6. Prompt templates guide LiteLLM-compatible text-generation models to produce task-specific outputs.
7. Runtime sessions are stored in SQLite by default so FastAPI requests can share document state.
8. A small API-level RAG evaluation checks whether answers and retrieved context contain expected facts from the synthetic document.

## Repository Structure

```text
.
├── README.md
├── data/
│   ├── README.md
│   └── sample/
├── docs/
│   └── DEPLOYMENT.md
├── frontend/
│   └── src/
├── scripts/
│   ├── evaluate_rag.py
│   └── generate_sample_pdf.py
├── tests/
├── Dockerfile              # backend container image
├── docker-compose.yml      # local backend runtime
├── app.py                  # optional Streamlit UI
├── main.py                 # FastAPI backend
├── metrics.py              # Prometheus-style API metrics
├── monitoring/             # Prometheus and Grafana provisioning
├── qdrant_store.py         # optional Qdrant vector-store integration
├── telegram_bot.py         # optional Telegram bot
├── services.py             # document analysis workflow
├── pdf_utils.py            # PDF extraction and chunking
├── embeddings.py           # embedding and FAISS index helpers
├── retrieval.py            # retrieval logic
├── llm_clients.py          # LiteLLM / Ollama client wrapper
├── requirements.txt
├── requirements-mlflow.txt # optional experiment tracking dependencies
├── .env.example
└── LICENSE
```

## How To Run

For a more detailed deployment walkthrough, see `docs/DEPLOYMENT.md`.

### 1. Docker Backend

Create a local `.env` file from the template and fill in your LiteLLM-compatible gateway key:

```bash
cp .env.example .env
```

Text generation uses `LLM_PROVIDER=litellm` by default. Russian responses use `LLM_MODEL=gemma3-27b-32bit`, while Kazakh responses use `ALEM_MODEL=astanahub/alemllm`.

Embeddings still use local Ollama with `nomic-embed-text`. Install and start Ollama on the host machine, then pull only the embedding model:

```bash
ollama pull nomic-embed-text
```

Build and run the FastAPI backend:

```bash
docker compose up --build backend
```

The container listens on `http://127.0.0.1:8000`. The compose file starts Qdrant, passes LiteLLM settings from `.env`, and points the backend to host Ollama only for embeddings through `OLLAMA_HOST=http://host.docker.internal:11434`.

Health and observability checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/metrics
curl http://127.0.0.1:8000/eval/latest
```

Optional monitoring stack:

```bash
docker compose up -d prometheus grafana
```

- Prometheus: `http://127.0.0.1:9090`
- Grafana dashboard: `http://127.0.0.1:3001/d/techspec-overview/techspec-ai-observability`

### 2. Local Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`, fill in the LiteLLM-compatible gateway key, then start Ollama and pull the local embedding model:

```bash
cp .env.example .env
ollama pull nomic-embed-text
```

Run the FastAPI server:

```bash
uvicorn main:app --reload --port 8000
```

Health checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/metrics
curl http://127.0.0.1:8000/eval/latest
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://127.0.0.1:8501` and proxies API requests to `http://127.0.0.1:8000`.
It includes a system panel for backend readiness, dependency status, API metrics, and the latest RAG evaluation report.

### 4. Optional Interfaces

Streamlit:

```bash
streamlit run app.py
```

Telegram bot:

```bash
python telegram_bot.py
```

The Telegram bot requires `TELEGRAM_BOT_TOKEN` in `.env`.

### 5. RAG Evaluation

After the backend is running, evaluate the full upload-and-question-answering path on the synthetic PDF:

```bash
python scripts/evaluate_rag.py
```

The script uploads `data/sample/sample_tech_spec_ru.pdf`, asks a small set of procurement questions, and reports:

- `answer_recall`: share of expected facts found in the generated answer
- `context_recall`: share of expected facts found in retrieved context
- `pass_rate`: share of evaluation cases above the configured thresholds
- `avg_latency_seconds`: average API latency for answer generation

Optional MLflow tracking:

```bash
pip install -r requirements-mlflow.txt
python scripts/evaluate_rag.py --mlflow-tracking-uri .runtime/mlruns --mlflow-experiment techspec-rag-eval
mlflow ui --backend-store-uri .runtime/mlruns
```

## Key Results / Expected Outputs

The app does not report supervised model performance metrics because this project is a document-analysis prototype, not a supervised ML benchmark. Expected outputs are:

- concise technical specification summary
- JSON with extracted fields such as customer BIN, budget, deadline, payment terms, subject, and lots
- supplier-facing risk notes
- answers to user questions with retrieved context
- Qdrant-backed vector retrieval in Docker with FAISS fallback
- Prometheus-style API metrics for uptime, request counts, statuses, and latency sums
- Prometheus and Grafana local monitoring dashboard
- RAG evaluation report with answer recall, context recall, pass rate, and latency
- frontend system panel for readiness, metrics, and latest evaluation status

## Business Interpretation

This workflow can help analysts and tender managers quickly triage procurement documents, identify critical requirements, and prepare follow-up questions. It is best viewed as an assistant for first-pass review; final procurement decisions still require human validation.

## Limitations

- The quality of outputs depends on PDF text extraction quality and the configured LLM.
- The default Docker setup uses Qdrant for vector retrieval, a LiteLLM-compatible gateway for text generation, and local Ollama for embeddings.
- Kazakh generation currently uses a LiteLLM-compatible path and may require an external model gateway configured through `.env`.
- Docker, API metrics, and a small synthetic RAG evaluation are included for local production-style demos, but no cloud deployment or large external benchmark is included.
- Synthetic sample data may not cover all edge cases found in real procurement documents.

## Tech Stack

Python, FastAPI, Docker, Qdrant, Prometheus, Grafana, Streamlit, React, Vite, PyMuPDF, FAISS, NumPy, Ollama, LiteLLM-compatible APIs, SQLite, optional MLflow tracking, python-telegram-bot, unittest.

## Privacy And Data Note

This repository is prepared for public portfolio use. It excludes real client/company data, API keys, Telegram tokens, usage logs, runtime databases, local caches, and original procurement PDFs. Use `.env.example` for configuration and keep real secrets in a local `.env` file that is never committed.

If an old version of this project was already pushed publicly with real documents or secrets, delete that repository or rewrite its history before republishing, and rotate any exposed tokens.

## Verification

GitHub Actions runs the backend test suite, frontend dependency audit, and frontend production build on every push to `main` and on pull requests. The frontend audit fails on high or critical npm vulnerabilities.

Backend smoke tests:

```bash
python -m unittest discover -s tests -v
```

Frontend production build:

```bash
cd frontend
npm audit --audit-level=high
npm run build
```

RAG evaluation against a running backend:

```bash
python scripts/evaluate_rag.py
```

The latest report is written to `.runtime/rag_eval_latest.json` and can be read by the frontend through `/eval/latest`.
