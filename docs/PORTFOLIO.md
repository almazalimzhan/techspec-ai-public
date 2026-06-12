# Portfolio Notes

This note summarizes how to present TechSpec AI in a CV, interview, or project walkthrough.

## One-Minute Pitch

TechSpec AI is a production-style RAG prototype for procurement PDF analysis. It extracts text from technical specification documents, creates embeddings, stores chunk vectors in Qdrant, retrieves relevant context, and uses a LiteLLM-compatible model gateway to generate summaries, structured fields, risk notes, and document-level Q&A in Russian and Kazakh.

The project is packaged as a local Docker Compose service with FastAPI, Qdrant, Prometheus, and Grafana. It includes health and readiness endpoints, Prometheus-style API metrics, a Grafana dashboard, CI checks, dependency audit, and a small API-level RAG evaluation script.

## Visual Demo

The README includes local screenshots for a quick portfolio review:

- frontend system panel: `docs/assets/frontend-system-panel.png`
- Grafana observability dashboard: `docs/assets/grafana-dashboard.png`

## What Makes It More Than A Demo

- It runs as an API service, not only as a notebook.
- Runtime configuration is handled through environment variables.
- The vector store can run as a real Qdrant service in Docker.
- Service health and dependency readiness are observable through `/health` and `/ready`.
- API traffic is measured through `/metrics` and visualized in Grafana.
- Retrieval quality is checked with a repeatable synthetic RAG evaluation.
- CI runs backend tests, frontend audit, and frontend build checks on GitHub.
- Real company data, API keys, runtime databases, and logs are excluded from the public repository.

## Suggested CV Bullet

Built a Dockerized RAG system for procurement PDF analysis using FastAPI, Qdrant, Ollama embeddings, and LiteLLM-compatible generation; added readiness checks, Prometheus metrics, Grafana monitoring, CI, dependency audit, and an API-level RAG evaluation pipeline.

## Russian CV Version

Разработал RAG-сервис для анализа PDF технических спецификаций в закупках: FastAPI, Qdrant, embeddings через Ollama, генерация через LiteLLM-compatible gateway. Добавил Docker Compose, readiness/health checks, Prometheus metrics, Grafana dashboard, CI, dependency audit и небольшой API-level evaluation пайплайн для проверки качества ответов и retrieved context.

## Interview Talking Points

1. **RAG pipeline:** PDF extraction, chunking, embeddings, vector storage, hybrid retrieval, prompt-based generation.
2. **Vector database:** Qdrant is used in Docker for production-style retrieval; FAISS remains as a fallback.
3. **Evaluation:** `scripts/evaluate_rag.py` uploads a synthetic PDF, asks expected questions, and checks answer recall, context recall, pass rate, and latency.
4. **Observability:** the backend exposes `/metrics`; Prometheus scrapes it; Grafana visualizes uptime, request count, errors, request rate, and latency.
5. **Deployment readiness:** Docker Compose starts backend, Qdrant, Prometheus, and Grafana with clear environment configuration.
6. **Security:** only synthetic data is committed; `.env`, real PDFs, logs, runtime databases, and secrets are ignored.

## Why There Is No Public Hosted Demo

The project is connected to a company-related workflow, so the public version is designed for safe local review rather than internet deployment. A public hosted demo could expose endpoints, runtime behavior, or accidental internal context. The repository instead demonstrates deployment readiness through Docker Compose, health checks, monitoring, and documentation.

## Local Demo Checklist

```bash
cp .env.example .env
ollama pull nomic-embed-text
docker compose up -d --build backend
docker compose up -d prometheus grafana
python scripts/evaluate_rag.py
```

Then open:

- frontend: `http://127.0.0.1:8501`
- backend health: `http://127.0.0.1:8000/health`
- backend readiness: `http://127.0.0.1:8000/ready`
- backend metrics: `http://127.0.0.1:8000/metrics`
- Prometheus targets: `http://127.0.0.1:9090/targets`
- Grafana dashboard: `http://127.0.0.1:3001/d/techspec-overview/techspec-ai-observability`

## Honest Limitations

- The public repository uses a synthetic sample PDF, not real production data.
- The evaluation is a lightweight regression check, not a large benchmark.
- Generation quality depends on the configured external model gateway.
- A public deployment is intentionally omitted for data and company-context safety.
