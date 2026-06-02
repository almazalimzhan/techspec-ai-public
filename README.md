# TechSpec AI: Procurement PDF Analyzer

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
3. Embeddings are generated with Ollama and indexed with FAISS.
4. Dense retrieval is combined with keyword scoring for procurement-specific questions.
5. Prompt templates guide the LLM to produce task-specific outputs.
6. Runtime sessions are stored in SQLite by default so FastAPI requests can share document state.

## Repository Structure

```text
.
├── README.md
├── data/
│   ├── README.md
│   └── sample/
├── frontend/
│   └── src/
├── scripts/
│   └── generate_sample_pdf.py
├── tests/
├── app.py                  # optional Streamlit UI
├── main.py                 # FastAPI backend
├── telegram_bot.py         # optional Telegram bot
├── services.py             # document analysis workflow
├── pdf_utils.py            # PDF extraction and chunking
├── embeddings.py           # embedding and FAISS index helpers
├── retrieval.py            # retrieval logic
├── llm_clients.py          # Ollama / LiteLLM client wrapper
├── requirements.txt
├── .env.example
└── LICENSE
```

## How To Run

### 1. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Install and start Ollama, then pull the local models used by default:

```bash
ollama pull qwen3:8b
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
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://127.0.0.1:8501` and proxies API requests to `http://127.0.0.1:8000`.

### 3. Optional Interfaces

Streamlit:

```bash
streamlit run app.py
```

Telegram bot:

```bash
python telegram_bot.py
```

The Telegram bot requires `TELEGRAM_BOT_TOKEN` in `.env`.

## Key Results / Expected Outputs

The app does not report model performance metrics because this project is a document-analysis prototype, not a supervised ML benchmark. Expected outputs are:

- concise technical specification summary
- JSON with extracted fields such as customer BIN, budget, deadline, payment terms, subject, and lots
- supplier-facing risk notes
- answers to user questions with retrieved context

## Business Interpretation

This workflow can help analysts and tender managers quickly triage procurement documents, identify critical requirements, and prepare follow-up questions. It is best viewed as an assistant for first-pass review; final procurement decisions still require human validation.

## Limitations

- The quality of outputs depends on PDF text extraction quality and the configured LLM.
- The default setup requires local Ollama models.
- Kazakh generation currently uses a LiteLLM-compatible path and may require an external model gateway configured through `.env`.
- No production deployment, monitoring, or formal evaluation benchmark is included.
- Synthetic sample data may not cover all edge cases found in real procurement documents.

## Tech Stack

Python, FastAPI, Streamlit, React, Vite, PyMuPDF, FAISS, NumPy, Ollama, LiteLLM-compatible APIs, SQLite, python-telegram-bot, unittest.

## Privacy And Data Note

This repository is prepared for public portfolio use. It excludes real client/company data, API keys, Telegram tokens, usage logs, runtime databases, local caches, and original procurement PDFs. Use `.env.example` for configuration and keep real secrets in a local `.env` file that is never committed.

If an old version of this project was already pushed publicly with real documents or secrets, delete that repository or rewrite its history before republishing, and rotate any exposed tokens.

## Verification

Backend smoke tests:

```bash
python -m unittest discover -s tests -v
```

Frontend production build:

```bash
cd frontend
npm run build
```
