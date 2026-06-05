# Commands

Reference for building, running, and operating the Question Paper Generator
locally. All paths are relative to the repo root unless noted.

The whole stack runs in Docker Compose. Three services:

| service    | image / build      | port  | role                                 |
| ---------- | ------------------ | ----- | ------------------------------------ |
| `db`       | `postgres:16`      | —     | Postgres 16, volume `pgdata`         |
| `web`      | `./backend`        | 8000  | Django + DRF (gunicorn-less dev)     |
| `frontend` | `./frontend`       | 5173  | Vite dev server (React + Tailwind)   |

---

## First-time setup

Nothing to install on the host beyond Docker. Compose has sane defaults baked
in, so `.env` is optional.

```bash
# Optional — copy the template if you want to override any defaults.
cp .env.example .env

# Build images + start everything. The web container will:
#   1. wait for Postgres
#   2. run `migrate` (NOT makemigrations — those are VCS-tracked)
#   3. run `seed_questions` to load the demo bank + teacher account
docker compose up -d --build
```

Seeded demo credentials:

| email                  | password     |
| ---------------------- | ------------ |
| `teacher@example.com`  | `teacher123` |

---

## Daily run

```bash
docker compose up -d              # start (background)
docker compose ps                 # status of all services
docker compose logs -f web        # tail Django logs
docker compose logs -f frontend   # tail Vite logs
docker compose stop               # stop, keep containers
docker compose down               # stop + remove containers (keeps pgdata)
docker compose down -v            # ALSO drop the Postgres volume (full reset)
```

URLs once up:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000/api/>
- Django admin: <http://localhost:8000/admin/> (create a superuser first — see below)

---

## Backend — Django

All `manage.py` commands run inside the `web` container:

```bash
# Open a Django shell (iPython-free, plain REPL)
docker compose exec web python manage.py shell

# Create / re-seed the question bank + demo user (idempotent)
docker compose exec web python manage.py seed_questions

# Apply migrations (entrypoint already does this on boot when RUN_MIGRATIONS=1)
docker compose exec web python manage.py migrate

# Generate NEW migrations after editing models.py — do this on the HOST so the
# files land with your uid, then commit them. Do NOT run it inside the
# container; entrypoint deliberately skips makemigrations to keep the host
# tree clean.
docker compose exec --user "$(id -u):$(id -g)" web \
  python manage.py makemigrations accounts bank papers

# Create a superuser for /admin
docker compose exec -it web python manage.py createsuperuser

# Show URL routes
docker compose exec web python manage.py show_urls 2>/dev/null \
  || docker compose exec web python -c "from config.urls import urlpatterns; \
       import pprint; pprint.pp(urlpatterns)"

# Collect static (only needed if you serve admin without DEBUG)
docker compose exec web python manage.py collectstatic --noinput
```

Django settings come from env vars (`backend/config/settings.py`). Key flags:

| var                          | default (compose)              | notes                              |
| ---------------------------- | ------------------------------ | ---------------------------------- |
| `DJANGO_DEBUG`               | `1`                            | Must be unset for prod-like runs   |
| `DJANGO_SECRET_KEY`          | dev fallback (only when DEBUG) | **Required** when `DEBUG=0`        |
| `DJANGO_ALLOWED_HOSTS`       | auto-seeded in DEBUG           | Required when `DEBUG=0`            |
| `CORS_ALLOW_ALL_ORIGINS`     | follows `DEBUG`                | Lock down via `CORS_ALLOWED_ORIGINS` |
| `RUN_MIGRATIONS`             | `1` on `web`                   | Set `0` to skip migrate+seed       |

---

## Extraction eval / benchmark

How well does `GeminiExtractor` parse a source paper? Measure it instead of
eyeballing. The loop is **extract (paid) → score (free) → benchmark (free)**.

Ground-truth manifests live under `content/eval/*.truth.json` — one per paper,
hand-built from the PDF: `{num, section, qtype, marks, key}` per question, where
`section` is the **mark band** (1→A, 2→B, 3→C, 4→E, 5→D) the importer derives,
not the printed discipline grouping. See `content/eval/31_1_1_Science.truth.json`.

```bash
# 1. Produce an extraction JSON — PAID, ~1 LLM call per page, model from
#    GEMINI_MODEL. Consent-gated (CLAUDE.md Rule 13). One run = one charge.
docker compose run --rm web python manage.py extract_paper \
  /content/science_2026/31_1_1_Science.pdf --out /content/parsed/baseline

# 2. Score one extraction against its manifest — FREE, deterministic, no LLM.
docker compose run --rm web python manage.py score_extraction \
  /content/parsed/baseline/31_1_1_Science.json \
  /content/eval/31_1_1_Science.truth.json
```

`score_extraction` prints `expected / extracted / matched`, then `recall /
precision / section_acc / qtype_acc / structure_usable`, plus the `MISSED` and
`SPURIOUS` lists so a regression names what changed.

### A/B harness — benchmark_extraction

Compare prompt/model variants over **every** manifest in `content/eval` at once.
Each `--arm name=dir` is a directory of `extract_paper` outputs from one variant
(producing them is the paid step above; the benchmark itself never calls an LLM).
For each manifest it looks up `<dir>/<paper>.json` per arm, scores it, and prints
one table; `--record` writes the rows to JSON for regression tracking.

```bash
# Each arm is its own paid extraction run into a distinct --out dir. Vary
# GEMINI_THINKING_BUDGET (-1 dynamic / 0 off / >0 cap) or GEMINI_MODEL per arm.
docker compose run --rm -e GEMINI_THINKING_BUDGET=-1 web python manage.py extract_paper \
  /content/science_2026/31_1_1_Science.pdf --out /content/parsed/thinking_on
docker compose run --rm -e GEMINI_THINKING_BUDGET=0  web python manage.py extract_paper \
  /content/science_2026/31_1_1_Science.pdf --out /content/parsed/thinking_off

# Score both arms into one table and record the numbers (free, no LLM).
docker compose run --rm web python manage.py benchmark_extraction /content/eval \
  --arm thinking_on=/content/parsed/thinking_on \
  --arm thinking_off=/content/parsed/thinking_off \
  --record /content/eval/results/$(date +%F).json
```

To check a later change for regression, re-run the arms, re-record, and diff the
new results JSON against the committed baseline — a dropped `recall` or a paper
that flipped to `— no extraction found —` is the signal.

---

## Teacher PDF upload (live HTTP ingest)

The bank has **two ingestion front doors** (both intentional — see CONTEXT.md
`Ingestor`). The eval/benchmark section above is the *developer* path
(`extract_paper` → committed JSON → `load_questions`). This is the *teacher*
path: upload a PDF over HTTP at runtime, no shell/repo/git.

The upload itself makes **no LLM call** — it persists the PDF and queues an
`IngestionJob` row (`status=pending`), returning `202` immediately. A separate
`drain_ingestion_jobs` command does the extraction out-of-request (in
production it runs on the platform's **cron**; there is no Celery / Redis /
worker daemon). Locally you run the drain by hand.

```bash
# 1. Log in as the seeded teacher to get a token.
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teacher@example.com","password":"teacher123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')

# 2. Upload a PDF — returns 202 + a job id. No extraction happens yet.
#    source_type is optional (one of previous_year_paper / sample_paper /
#    question_bank); it defaults to previous_year_paper.
JOB_ID=$(curl -s -X POST http://localhost:8000/api/bank/ingest/ \
  -H "Authorization: Token $TOKEN" \
  -F "pdf=@content/science_2026/31_1_1_Science.pdf" \
  -F "source_type=previous_year_paper" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')

# 3. See what's queued — FREE, never calls Gemini.
docker compose run --rm web python manage.py drain_ingestion_jobs --dry-run

# 4. Drain the queue — PAID, ~1 LLM call per PDF page, model from GEMINI_MODEL.
#    Consent-gated (CLAUDE.md Rule 13). One run = one charge per pending job.
docker compose run --rm web python manage.py drain_ingestion_jobs

# 5. Poll the job — status flips pending -> running -> done (or failed), with
#    created/skipped counts (or an error message).
curl -s -H "Authorization: Token $TOKEN" \
  http://localhost:8000/api/bank/ingest/$JOB_ID/
```

Drained questions land scoped to the uploading teacher's `school`, `verified=False`
(filtered by the downstream `parse_quality`/`verified` gate — there is no upfront
review step in V1). `--limit N` caps how many pending jobs one drain run
processes. One bad PDF is recorded as `failed` with its error and does not abort
the rest of the run.

> **Production:** schedule `python manage.py drain_ingestion_jobs` on your host's
> cron (Render Cron Job / Railway cron / VPS crontab, e.g. `* * * * *`). The
> ~1-minute pickup latency is irrelevant — extraction takes minutes. No code
> change is needed to deploy it; it is purely scheduler config.

---

## Database — Postgres

```bash
# Open psql in the db container
docker compose exec db psql -U qpg -d qpg

# One-shot query
docker compose exec db psql -U qpg -d qpg -c '\dt'                # list tables
docker compose exec db psql -U qpg -d qpg -c 'SELECT count(*) FROM bank_question;'

# Dump / restore
docker compose exec db pg_dump -U qpg qpg > backup.sql
docker compose exec -T db psql -U qpg -d qpg < backup.sql

# Wipe just the data (keeps schema) — handy mid-development
docker compose exec web python manage.py flush --noinput

# Nuke the whole DB volume and reseed from scratch
docker compose down -v && docker compose up -d
```

Connection details (from `.env.example`):
`postgresql://qpg:qpg@localhost:5432/qpg` if you want a host-side client; from
inside a container the host is `db`.

---

## Cache (Postgres-backed)

The Django cache is `DatabaseCache` — it lives in the Postgres `qpg_cache`
table (created by the `papers.0009_create_cache_table` migration), so no extra
service is needed. The PDF cache (`paper-pdf:{id}`) sits here with a 1-day TTL;
clear it if you ever change `render_paper_pdf` and want to see new output for an
existing paper.

```bash
# Inspect cached keys
docker compose exec db psql -U qpg -d qpg -c "SELECT cache_key, expires FROM qpg_cache;"

# Clear all cached entries (Django API — respects the backend)
docker compose exec web python manage.py shell -c \
  "from django.core.cache import cache; cache.clear()"

# Or drop just the PDF rows directly
docker compose exec db psql -U qpg -d qpg -c \
  "DELETE FROM qpg_cache WHERE cache_key LIKE '%paper-pdf:%';"
```

---

## Frontend — Vite + React

The container runs `pnpm dev --host 0.0.0.0` on 5173 with the source tree
volume-mounted, so edits hot-reload without a rebuild.

```bash
# Add a dependency (inside the container so it lands in the right lockfile)
docker compose exec frontend pnpm add <pkg>
docker compose exec frontend pnpm add -D <dev-pkg>

# Type-check + production build
docker compose exec frontend pnpm build

# Preview the built bundle
docker compose exec frontend pnpm preview --host 0.0.0.0 --port 4173

# Rebuild the image (after editing Dockerfile or lockfile)
docker compose build frontend && docker compose up -d frontend
```

Host-side dev (running `pnpm dev` outside Docker) requires
`VITE_API_PROXY=http://localhost:8000` so the `/api` proxy hits the host
backend instead of the unresolvable `web` service DNS.

---

## End-to-end smoke test (curl)

Confirms the full happy path: login → assemble → PDF.

```bash
# Login (seeded teacher)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teacher@example.com","password":"teacher123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')

# Assemble a paper
PAPER_ID=$(curl -s -X POST http://localhost:8000/api/papers/assemble \
  -H "Authorization: Token $TOKEN" -H "Content-Type: application/json" -d '{}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')

# Download the PDF (writes paper-$PAPER_ID.pdf)
curl -s -H "Authorization: Token $TOKEN" \
  -o "paper-$PAPER_ID.pdf" \
  http://localhost:8000/api/papers/$PAPER_ID/pdf

file "paper-$PAPER_ID.pdf"     # -> PDF document, version 1.4
```

---

## Tests

**Always run the backend suite in Docker, never on the host.** The host
Python may be < 3.10, but the project requires Django ≥ 5.1 (needs py ≥ 3.10),
and pytest-django (`--reuse-db`) needs the Postgres `db` service. A host
`pytest` will fail with `ModuleNotFoundError: No module named 'django'` or a
Django version-resolution error — that is an environment mismatch, not a code
problem.

```bash
# Backend — full suite. `run --rm web` spins up the db dependency (healthcheck
# gated) then tears the one-off container down. pytest config lives in
# backend/pyproject.toml (DJANGO_SETTINGS_MODULE=config.settings, --reuse-db).
docker compose run --rm web pytest

# If the stack is already up, exec into the running web container instead:
docker compose exec web pytest

# Narrow to one app / file / test:
docker compose run --rm web pytest bank/tests/test_ingestor.py
docker compose run --rm web pytest -k segment -q

# Frontend (vitest)
docker compose exec frontend pnpm test
```

Lint/format (also in the `web` image, which has ruff + black from
`requirements-dev.txt`):

```bash
docker compose run --rm web ruff check .
docker compose run --rm web black --check .
```

Manual verification: the curl smoke test above, or the Playwright MCP-driven
browser flow (see `.mcp.json`).

---

## Cleanup / reset

| What                             | Command                                      |
| -------------------------------- | -------------------------------------------- |
| Stop everything                  | `docker compose down`                        |
| Stop + drop the Postgres volume  | `docker compose down -v`                     |
| Clear only the cache             | `docker compose exec web python manage.py shell -c "from django.core.cache import cache; cache.clear()"` |
| Rebuild all images               | `docker compose build --no-cache`            |
| Remove node_modules from image   | `docker compose down && docker volume rm $(docker volume ls -q | grep node_modules)` |
| Wipe Playwright session artifacts | `rm -rf .playwright-mcp/`                   |
