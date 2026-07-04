# Run The App With Docker

Use Docker for this project. The browser opens the frontend on the host, but the
frontend container proxies API calls to the backend container, and the backend
uses the Postgres/pgvector container.

```text
browser -> http://localhost:5173 -> frontend -> web:8000 -> db:5432
```

## Why Docker Is The Source Of Truth

Do **not** rely on host Python/Node dependencies for normal development checks.
All app/runtime/test dependencies are installed inside containers:

- `db`: `pgvector/pgvector:0.8.2-pg16-bookworm`
  - PostgreSQL 16 with pgvector extension support.
- `web`, `generation-worker`, `ingestion-worker`: built from `backend/Dockerfile`
  - Python `3.12-slim`
  - Installs `backend/requirements.txt` and `backend/requirements-dev.txt`
  - Includes Django, DRF, psycopg, pgvector, LangChain/LangGraph, provider SDKs,
    PyMuPDF, ReportLab, Playwright, pytest, ruff, black, etc.
  - Runs `playwright install --with-deps chromium`, so browser/PDF test deps live
    in the backend image too.
- `frontend`: built from `frontend/Dockerfile`
  - Node `22-slim`
  - pnpm `9.15.4` via corepack
  - Installs all dependencies from `frontend/package.json`
  - The compose volume keeps `/app/node_modules` inside the container, not on the host.

If a command fails on the host because `python`, `black`, `pytest`, `node`, or a
DB host is missing, run it through `docker compose exec ...` instead.

## Start

Stop any host Vite server first if it owns port 5173:

```bash
lsof -nP -iTCP:5173 -sTCP:LISTEN
kill <PID>
```

Start the app stack:

```bash
docker compose up -d --build db web frontend
```

For background AI generation / ingestion processing, also start the workers:

```bash
docker compose up -d --build generation-worker ingestion-worker
```

Check it:

```bash
docker compose ps
```

Expected services:

```text
db                  Up healthy
web                 Up, 0.0.0.0:8000->8000
frontend            Up, 0.0.0.0:5173->5173
generation-worker   Up
ingestion-worker    Up
```

Open:

```text
http://localhost:5173
```

Demo login:

```text
teacher@example.com
teacher123
```

## Load Questions And Answers

The backend auto-runs migrations and seed questions on startup. To load the full
committed bank and generated answers into the Docker DB, run:

```bash
docker compose exec web python manage.py load_questions /content/parsed
docker compose exec web python manage.py load_question_overrides /content/bank-overrides/question_overrides.json
```

`load_questions` is idempotent; duplicates are skipped. `load_question_overrides`
applies committed AI-generated answers and disables diagram-required questions.

Verify the loaded bank:

```bash
docker compose exec web python manage.py shell -c '
from bank.models import Question
print("eligible", Question.objects.filter(parse_quality__in=["clean","partial"]).count())
print("answered eligible", Question.objects.filter(parse_quality__in=["clean","partial"]).exclude(answer="").count())
print("disabled diagrams", Question.objects.filter(review_flags__contains=["disabled_diagram_required"]).count())
'
```

Current expected result:

```text
eligible 344
answered eligible 344
disabled diagrams 34
```

## Backend Commands

Run backend commands inside the `web` container:

```bash
docker compose exec web python manage.py check
docker compose exec web pytest
docker compose exec web ruff check .
docker compose exec web black --check .
```

### Full Backend Test Suite

Use the Docker DB, not host pytest. The backend settings default to `POSTGRES_HOST=db`
inside compose; on the host that name does not resolve.

For the full suite, pin the extractor to the deterministic test path so ambient
OCR config does not route tests through Mistral OCR:

```bash
docker compose exec -T -e EXTRACTION_PIPELINE=gemini-native-pdf web pytest
```

Last known result:

```text
527 passed, 1 warning
```

If you run without that env override and `EXTRACTION_PIPELINE=mistral-ocr-batch`
is present, ingestion tests may call the Mistral OCR path and fail on dummy PDFs.

## Frontend Commands

Run frontend commands inside the `frontend` container:

```bash
docker compose exec frontend npm test
docker compose exec frontend npm run lint
docker compose exec frontend npm run type-check
docker compose exec frontend npm run build
```

The frontend container command runs `pnpm install && pnpm dev --host 0.0.0.0`.
Using `npm ...` for scripts is okay inside the container because dependencies are
already installed in `/app/node_modules`.

## Useful Runtime Commands

Run one generation drain manually:

```bash
docker compose exec web python manage.py drain_generation_batches --limit 1
```

Run one ingestion drain manually:

```bash
docker compose exec web python manage.py drain_ingestion_jobs --limit 1
```

View logs:

```bash
docker compose logs -f web
docker compose logs -f frontend
docker compose logs -f generation-worker
docker compose logs -f ingestion-worker
```

## Stop / Clean Up

Stop the stack:

```bash
docker compose down
```

Remove stopped containers:

```bash
docker container prune -f
```

Remove the Postgres volume too (destructive; wipes local Docker DB):

```bash
docker compose down -v
```
