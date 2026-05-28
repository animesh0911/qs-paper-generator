# Commands

Reference for building, running, and operating the Question Paper Generator
locally. All paths are relative to the repo root unless noted.

The whole stack runs in Docker Compose. Five services:

| service    | image / build      | port  | role                                 |
| ---------- | ------------------ | ----- | ------------------------------------ |
| `db`       | `postgres:16`      | —     | Postgres 16, volume `pgdata`         |
| `redis`    | `redis:7`          | —     | Celery broker + Django cache backend |
| `web`      | `./backend`        | 8000  | Django + DRF (gunicorn-less dev)     |
| `worker`   | `./backend`        | —     | Celery worker                        |
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
docker compose logs -f worker     # tail Celery logs
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

## Redis (cache + Celery broker)

```bash
# Open redis-cli
docker compose exec redis redis-cli

# One-shot commands
docker compose exec redis redis-cli PING                    # -> PONG
docker compose exec redis redis-cli KEYS '*'                # list all keys
docker compose exec redis redis-cli KEYS 'paper-pdf:*'      # cached PDFs
docker compose exec redis redis-cli FLUSHDB                 # drop all keys
```

The PDF cache (`paper-pdf:{id}`) lives here with a 1-day TTL; flush it if you
ever change `render_paper_pdf` and want to see new output for an existing
paper.

---

## Celery

The worker container starts automatically with the stack. It's currently
idle — `assemble_paper` and PDF rendering still run synchronously inside the
request handler. The plumbing is in place for future slices to offload work.

```bash
# Tail worker logs
docker compose logs -f worker

# Restart just the worker (after editing tasks)
docker compose restart worker

# Fire the built-in debug task from a Django shell
docker compose exec web python manage.py shell -c \
  "from config.celery import debug_task; debug_task.delay()"

# Run a task synchronously (skips the broker) — useful in tests
docker compose exec -e CELERY_TASK_ALWAYS_EAGER=1 web python manage.py shell
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

There is no test suite yet (Slice 1 walking skeleton). The intended layout:

```bash
# Backend (pytest is not installed yet; add to requirements when adding tests)
docker compose exec web pytest

# Frontend (vitest is not installed yet)
docker compose exec frontend pnpm test
```

Manual verification meanwhile: the curl smoke test above, or the Playwright
MCP-driven browser flow (see `.mcp.json`).

---

## Cleanup / reset

| What                             | Command                                      |
| -------------------------------- | -------------------------------------------- |
| Stop everything                  | `docker compose down`                        |
| Stop + drop the Postgres volume  | `docker compose down -v`                     |
| Drop only the Redis cache        | `docker compose exec redis redis-cli FLUSHDB` |
| Rebuild all images               | `docker compose build --no-cache`            |
| Remove node_modules from image   | `docker compose down && docker volume rm $(docker volume ls -q | grep node_modules)` |
| Wipe Playwright session artifacts | `rm -rf .playwright-mcp/`                   |
