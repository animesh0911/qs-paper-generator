# Run the App with Docker

Docker Compose is the supported way to run this project. Do not rely on host
Python/Node dependencies for normal app runtime or tests.

## Required services

| Service | Purpose |
|---|---|
| `db` | PostgreSQL 16 + pgvector. Required by backend. |
| `web` | Django API, migrations, management commands. |
| `frontend` | Vite frontend at `http://localhost:5173`. |
| `generation-worker` | Background AI Q&A generation batches. |
| `ingestion-worker` | Background paper ingestion jobs. |
| `answer-generation-worker` | Optional upload-answer generation jobs. |

Request path:

```text
browser -> localhost:5173 -> frontend -> web:8000 -> db:5432
```

## Start everything

If a host Vite process already owns port `5173`, stop it first:

```bash
lsof -nP -iTCP:5173 -sTCP:LISTEN
kill <PID>
```

Start the full app stack:

```bash
docker compose up -d db web frontend generation-worker ingestion-worker answer-generation-worker
```

Use `--build` only after Dockerfile or dependency changes:

```bash
docker compose up -d --build db web frontend generation-worker ingestion-worker answer-generation-worker
```

Check status:

```bash
docker compose ps
```

Expected running services:

```text
db                         Up healthy
web                        Up, 0.0.0.0:8000->8000
frontend                   Up, 0.0.0.0:5173->5173
generation-worker          Up
ingestion-worker           Up
answer-generation-worker   Up
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

## Seed a fresh database

The backend container runs migrations and base seed data on startup. For a fresh
DB, run these idempotent commands after the stack is up.

### 1. Seed textbook corpus for AI Q&A

```bash
docker compose exec web python manage.py seed_textbook_corpus
```

This populates `TextbookDocument`, `TextbookElement`, `ChapterMapNode`, and
`RetrievalChunk` rows used by grounded AI Q&A topic retrieval.

Currently supported corpus artifacts:

| Chapter | Slug | Artifact |
|---|---|---|
| 4 | `carbon-and-its-compounds` | `content/ncert/jesc104/jesc104.json` |
| 10 | `human-eye-and-the-colourful-world` | `content/ncert/jesc110/jesc110.json` |

Chapter 10 is seeded only if `content/ncert/jesc110/jesc110.json` is present in
the container, or mounted at `/content/ncert/jesc110/jesc110.json`. Do **not** run
Mistral OCR during deploy; OCR is an offline/manual artifact-generation step.
A fresh deploy should only run `seed_textbook_corpus` against reviewed artifacts.

### 2. Load committed question bank and answer overrides

```bash
docker compose exec web python manage.py load_questions /content/parsed
docker compose exec web python manage.py load_question_overrides /content/bank-overrides/question_overrides.json
```

Both commands are idempotent.

## Common commands

Backend checks/tests:

```bash
docker compose exec web python manage.py check
docker compose exec web pytest
docker compose exec web ruff check .
docker compose exec web black --check .
```

Full backend test suite should pin the deterministic extractor path:

```bash
docker compose exec -T -e EXTRACTION_PIPELINE=gemini-native-pdf web pytest
```

Frontend checks/tests:

```bash
docker compose exec frontend npm test
docker compose exec frontend npm run lint
docker compose exec frontend npm run type-check
docker compose exec frontend npm run build
```

Drain one queued job manually:

```bash
docker compose exec web python manage.py drain_generation_batches --limit 1
docker compose exec web python manage.py drain_ingestion_jobs --limit 1
docker compose exec web python manage.py drain_answer_generation_jobs --limit 1
```

Logs:

```bash
docker compose logs -f web
docker compose logs -f frontend
docker compose logs -f generation-worker
docker compose logs -f ingestion-worker
docker compose logs -f answer-generation-worker
```

## Stop / reset

Stop containers:

```bash
docker compose down
```

Destroy the local Postgres volume too, wiping the local DB:

```bash
docker compose down -v
```
