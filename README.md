# Question Paper Generator

CBSE Class 10 Science question paper generator. See [`PLAN.md`](PLAN.md) for the
design and [`PRD.md`](PRD.md) for the product requirements.

## Slice 1 — Walking skeleton

A thin end-to-end path: log in → assemble a paper from seeded questions → view it →
export a PDF. Backend (Django + DRF), frontend (React + Vite + Tailwind +
shadcn/ui), and Postgres, all via Docker Compose.

### Run

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000  (health: `/healthz`, admin: `/admin`)
- Seeded teacher login: **teacher@example.com** / **teacher123**

On first boot the `web` container runs migrations and seeds a demo school, a teacher
account, and a handful of Class 10 Science questions.

### Stack

| Layer | Tech |
|-------|------|
| Frontend | React 19, Vite, TypeScript, Tailwind, shadcn/ui |
| Backend | Django 5, DRF (token auth) |
| Data | PostgreSQL (also backs the Django cache) |
| Packaging | Docker Compose |

Chosen to stay framework-compatible with the Apptension SaaS boilerplate so its
modules can be adopted later. A nullable `school_id` on core tables is the
multi-tenancy seam.
