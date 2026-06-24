# How To Run Backend And Frontend

Lean runbook for running the full local stack and the checks that catch missing
seed data, stale auth, and frontend/backend drift.

## Start The App

```bash
docker compose up --build
```

This starts:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Postgres with pgvector
- Generation worker: drains queued Q&A generation batches

On startup the backend must run:

```bash
python manage.py migrate --noinput
python manage.py seed_questions
python manage.py seed_textbook_corpus
```

Use the seeded login:

```text
teacher@example.com
teacher123
```

## Re-Run Seeds Manually

Use this after changing seed/import code or when a running DB is missing demo
data.

```bash
docker compose exec web python manage.py seed_questions
docker compose exec web python manage.py seed_textbook_corpus
```

## Configure LLM Calls

Copy the example env file when running real Q&A generation:

```bash
cp .env.example .env
```

For Gemini:

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash
```

For OpenRouter just for Q&A generation:

```bash
LLM_QUESTION_GENERATION_PROVIDER=openrouter
LLM_QUESTION_GENERATION_MODEL=google/gemini-3.5-flash
OPENROUTER_API_KEY=...
```

Restart after changing env:

```bash
docker compose up -d --build web generation-worker frontend
```

Confirm the worker sees the intended configuration:

```bash
docker compose exec generation-worker sh -lc 'env | sort | grep -E "^(LLM|GEMINI|OPENAI|OPENROUTER|DEEPSEEK|ANTHROPIC)_"'
```

## Backend Checks

Check queued Q&A generation batches without making model calls:

```bash
docker compose exec web python manage.py drain_generation_batches --dry-run
```

Drain one queued batch manually:

```bash
docker compose exec web python manage.py drain_generation_batches --limit 1
```

Run all backend tests:

```bash
docker compose exec web pytest
```

Run the corpus/topic tests only:

```bash
docker compose exec web pytest corpus/tests/test_textbook.py corpus/tests/test_chapter_map.py
```

Run Django system checks:

```bash
docker compose exec web python manage.py check
```

## Frontend Checks

Run from the host:

```bash
cd frontend
npm test
npm run lint
npm run type-check
```

## End-To-End Smoke Checks

Get a fresh token:

```bash
TOKEN=$(
  curl -sS -X POST http://localhost:5173/api/auth/login \
    -H 'Content-Type: application/json' \
    --data '{"email":"teacher@example.com","password":"teacher123"}' \
  | node -e "let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>console.log(JSON.parse(s).token))"
)
```

Verify paper setup data:

```bash
curl -sS http://localhost:5173/api/papers/formats \
  -H "Authorization: Token $TOKEN"

curl -sS http://localhost:5173/api/bank/chapters/ \
  -H "Authorization: Token $TOKEN"
```

Verify Chapter 4 topic metadata:

```bash
curl -sS http://localhost:5173/api/corpus/chapters/carbon-and-its-compounds/topics/ \
  -H "Authorization: Token $TOKEN" \
  | node -e "let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{const j=JSON.parse(s); console.log({document: j.document?.id ?? null, topicCount: j.topics.length, firstTopic: j.topics[0]?.title ?? null}); if (!j.document || j.topics.length === 0) process.exit(1);})"
```

Verify invalid tokens are rejected:

```bash
curl -i http://localhost:5173/api/papers/formats \
  -H 'Authorization: Token invalid-token'
```

Expected: `401 Unauthorized` with `{"detail":"Invalid token."}`.

## Before Calling It Done

Run this minimum suite:

```bash
docker compose exec web python manage.py check
docker compose exec web pytest
cd frontend && npm test && npm run lint && npm run type-check
```

Then run the Chapter 4 topic smoke check above. It must report a non-null
`document` and `topicCount > 0`.
