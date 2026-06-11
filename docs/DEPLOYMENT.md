# Deployment Runbook

This note explains how to run TechSpec AI as a local production-style service and how to verify that each runtime layer is working.

## Runtime Architecture

```text
User / frontend
    -> FastAPI backend in Docker
    -> SQLite runtime session store
    -> Qdrant vector database in Docker
    -> FAISS in-process fallback
    -> Ollama on the host for nomic-embed-text embeddings
    -> LiteLLM-compatible gateway for text generation
```

The current split is intentional:

- `LiteLLM` handles text generation for summaries, JSON extraction, risk analysis, and Q&A.
- `Ollama` is used only for local embeddings through `nomic-embed-text`.
- `Qdrant` stores document chunk vectors for Docker-based retrieval.
- `FAISS` remains available as a local fallback if Qdrant is disabled or unavailable.
- `Docker Compose` runs the backend with stable environment variables, ports, volumes, and health checks.
- `/metrics` exposes Prometheus-style API metrics for local monitoring demos.

## Environment Files

Use two different files:

```text
.env.example  safe template committed to git
.env          local secrets and runtime config, ignored by git
```

Create the local file:

```bash
cp .env.example .env
```

Then set the private value in `.env`:

```text
LITELLM_API_KEY=your_private_key_here
```

Do not put real secrets in `.env.example`.

## Required Local Services

Start Ollama on the host machine. The backend container reaches it through Docker Desktop's host alias:

```text
http://host.docker.internal:11434
```

Pull the embedding model:

```bash
ollama pull nomic-embed-text
```

Check Ollama from the host:

```bash
ollama list
```

## Docker Startup

Build and start the backend. Docker Compose also starts Qdrant because the backend depends on it:

```bash
docker compose up -d --build backend
```

Check container status:

```bash
docker compose ps
```

Expected result:

```text
techspec-ai-qdrant    Up ...
techspec-ai-backend   Up ... (healthy)   0.0.0.0:8000->8000/tcp
```

Qdrant is exposed on `http://127.0.0.1:6333` for local inspection:

```bash
curl http://127.0.0.1:6333/collections
```

View logs:

```bash
docker compose logs backend --tail=80
```

Stop the service:

```bash
docker compose down
```

## Health, Readiness, and Metrics

Health means the FastAPI process is alive:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok","session_backend":"sqlite"}
```

Readiness means required dependencies are available:

```bash
curl http://127.0.0.1:8000/ready
```

Expected:

```json
{
  "status": "ok",
  "session_backend": "sqlite",
  "auth_enabled": false,
  "llm_provider": "litellm",
  "vector_backend": "qdrant",
  "embeddings": "ok",
  "llm": "ok",
  "qdrant": "ok"
}
```

Metrics show request counts, statuses, and latency sums:

```bash
curl http://127.0.0.1:8000/metrics
```

Example:

```text
techspec_http_requests_total{method="POST",path="/upload",status="200"} 1
techspec_http_request_latency_seconds_sum{method="POST",path="/summary",status="200"} 16.270936
```

The latest RAG evaluation report is available after `scripts/evaluate_rag.py` has been run:

```bash
curl http://127.0.0.1:8000/eval/latest
```

## End-to-End Smoke Test

Upload the demo PDF:

```bash
curl -s -X POST http://127.0.0.1:8000/upload \
  -F 'language=Русский' \
  -F 'file=@data/sample/sample_tech_spec_ru.pdf'
```

Save the returned `session_id`, then call:

```bash
curl -s -X POST http://127.0.0.1:8000/summary \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"SESSION_ID","customer_bin":"123456789012","language":"Русский"}'
```

```bash
curl -s -X POST http://127.0.0.1:8000/json-fields \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"SESSION_ID","customer_bin":"123456789012","language":"Русский"}'
```

```bash
curl -s -X POST http://127.0.0.1:8000/risks \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"SESSION_ID","customer_bin":"123456789012","language":"Русский"}'
```

```bash
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"SESSION_ID","question":"Какие условия оплаты и срок подключения?","customer_bin":"123456789012","language":"Русский"}'
```

If these endpoints return `200`, the full path works:

```text
PDF upload -> text extraction -> chunking -> embeddings -> Qdrant upsert -> session store -> retrieval -> LiteLLM generation
```

## RAG Evaluation

Run the API-level evaluation after the backend is healthy:

```bash
python scripts/evaluate_rag.py
```

The script uploads the synthetic demo PDF, asks several procurement-specific questions through `/ask`, and checks whether expected facts appear in both the generated answer and retrieved context.

Example result:

```text
Summary
- cases: 4
- passed: 4
- pass_rate: 1.00
- avg_answer_recall: 0.92
- avg_context_recall: 1.00
- avg_latency_seconds: 1.99
```

Use this as a small regression check when changing retrieval logic, prompts, vector storage, or model configuration. It is not a large benchmark; it is a fast sanity check that the main RAG path still retrieves and answers from the document.

To save a machine-readable report:

```bash
python scripts/evaluate_rag.py --output rag_eval_report.json
```

Without `--output`, the script writes the latest local report to `.runtime/rag_eval_latest.json`, which is what `/eval/latest` reads.

## Optional MLflow Tracking

Install the optional experiment-tracking dependency:

```bash
pip install -r requirements-mlflow.txt
```

Run the same evaluation and log metrics to a local MLflow file store:

```bash
python scripts/evaluate_rag.py \
  --mlflow-tracking-uri .runtime/mlruns \
  --mlflow-experiment techspec-rag-eval
```

Open the local MLflow UI:

```bash
mlflow ui --backend-store-uri .runtime/mlruns
```

The eval run logs overall metrics such as `pass_rate`, `avg_answer_recall`, `avg_context_recall`, and `avg_latency_seconds`. It also logs per-case metrics, for example `case_payment_terms_answer_recall`, and stores `rag_eval_report.json` as an artifact.

## Container Tests

Run the test suite inside the same image used by Docker Compose:

```bash
docker compose exec backend python -m unittest discover -s tests -v
```

Expected:

```text
Ran 22 tests
OK
```

## Continuous Integration

GitHub Actions runs two checks on pushes to `main` and on pull requests:

- `backend-tests`: installs Python dependencies and runs `python -m unittest discover -s tests -v`
- `frontend-build`: installs frontend dependencies with `npm ci`, runs `npm audit --audit-level=high`, and runs `npm run build`

The workflow file is `.github/workflows/ci.yml`.

Dependabot checks for dependency updates weekly:

- Python requirements in `/`
- npm dependencies in `/frontend`
- GitHub Actions versions in `.github/workflows`

The Dependabot config is `.github/dependabot.yml`.

## Common Failures

`/ready` returns `LiteLLM bad status: 401`

Cause: `LITELLM_API_KEY` is missing or invalid inside the container.

Fix:

```bash
cp .env.example .env
# add LITELLM_API_KEY to .env
docker compose up -d --force-recreate backend
```

Check without printing the key:

```bash
docker exec techspec-ai-backend python -c "import os; print(len(os.getenv('LITELLM_API_KEY') or ''))"
```

`/ready` says embeddings cannot connect to Ollama

Cause: Ollama is not running on the host, or `nomic-embed-text` is missing.

Fix:

```bash
ollama serve
ollama pull nomic-embed-text
docker compose up -d --force-recreate backend
```

`/ready` says Qdrant is unavailable

Cause: the Qdrant container is not running or the backend has the wrong `QDRANT_URL`.

Fix:

```bash
docker compose up -d qdrant
docker compose up -d --force-recreate backend
curl http://127.0.0.1:6333/collections
```

`docker compose ps` is healthy but host `curl` fails

Cause: local sandbox or port access issue.

Check from inside the container:

```bash
docker exec techspec-ai-backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

## Security Notes

- Never commit `.env`.
- Keep real API keys out of `.env.example`, README files, screenshots, and logs.
- Rotate any key that was ever pushed to a public repository.
- The public demo uses synthetic data only.
- CI blocks high and critical frontend dependency vulnerabilities with `npm audit --audit-level=high`.

## What This Demonstrates

This deployment setup demonstrates skills that are relevant for production ML and LLM engineering:

- Dockerized FastAPI service
- environment-based configuration
- readiness checks for external dependencies
- Prometheus-style metrics
- Qdrant vector database integration
- FAISS fallback retrieval
- local model dependency for embeddings
- external LLM gateway integration
- end-to-end API smoke testing
- small RAG evaluation with answer recall, context recall, pass rate, and latency
- GitHub Actions CI for backend tests and frontend build
- Dependabot updates for Python, npm, and GitHub Actions dependencies
