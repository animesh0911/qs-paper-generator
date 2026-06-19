Title: V: Add AI editor endpoint and async job contracts
Labels: V
GitHub: #31

## What to build

Add the backend API surface for editor AI: typed intent routing, chat, summary, review, editor-edit, refine, and job polling. All model calls go through the shared LiteLLM gateway and return validated, endpoint-specific result shapes.

## Acceptance criteria

- [ ] Add `/api/ai/intent/`, `/api/ai/chat/`, `/api/ai/summarize-paper/`, `/api/ai/review-paper/`, `/api/ai/editor-edit/`, `/api/ai/editor-edit/refine/`, and `/api/ai/jobs/{jobId}/` route contracts.
- [ ] Button-triggered actions can call their endpoint directly without intent classification.
- [ ] Typed text uses the intent endpoint with product context and examples.
- [ ] Async endpoints return a job id and persist V1 job state in a Postgres `AIJob` model drained out-of-request by a cron-run `drain_ai_jobs` management command (no Redis, no Celery) — the same pattern as `IngestionJob` + `drain_ingestion_jobs` (#104). See #107.
- [ ] `GET /api/ai/jobs/{jobId}/` is scoped to the job owner's school: a cross-school job id is a 404 (not 403), so the endpoint never confirms another school's job exists — the same scoping as `ingest_status`. Persisting jobs as queryable rows must not become an IDOR for other schools' paper summaries/reviews/proposals.
- [ ] Only one active AI job/proposal per paper (not just per client session): a new job request is rejected while that paper has a non-terminal (`pending`/`running`) `AIJob` row.
- [ ] All model calls use `ai_services.llm`; no provider SDK or provider key is used by frontend code.
- [ ] Endpoint responses distinguish chat, summary, review, proposal, refused, validation-failed, pending, failed, and completed states without relying on generic UI guessing.

## Blocked by

Blocked by #28.
