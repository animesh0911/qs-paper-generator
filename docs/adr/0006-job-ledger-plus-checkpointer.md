# Two-layer durability: job ledger + LangGraph checkpointer over the cron-drain

Asynchronous LLM workflows persist across **two** layers, with distinct
responsibilities. The **job ledger** — a Postgres model (`IngestionJob` today,
`GenerationBatch` planned in #143) — owns queryable lifecycle: `status`, `school`,
owner, timestamps, result counts, the poll endpoint the frontend hits, and a
`thread_id` pointer. LangGraph's **`PostgresSaver` checkpointer** owns in-flight
execution state and human-in-the-loop pause/resume, keyed by that `thread_id`.
The existing **cron-drain** management command (`drain_ingestion_jobs` and its
successors) loads a pending ledger row and runs or resumes the graph **in-process**
— `graph.invoke(state, {thread_id})`.

This records a design decision taken in a `/grill-with-docs` review; implementation
is sequenced with ADR-0005.

## Why

LangGraph arrives with its own persistence (the checkpointer), and this project
already has a deliberate async model: Postgres-backed job rows drained by cron,
chosen specifically to avoid Celery/Redis (#105, #107). The two must be
reconciled rather than duplicated.

They sit at different altitudes, so neither subsumes the other. The ledger is a
**business** record — what the API lists, scopes by `school`, and reports
status from; it must stay a plain, indexable table the poll endpoints already
read. The checkpointer is an **execution** record — the engine-internal snapshot
that makes a long job resumable after a crash and lets a graph pause for teacher
review and resume from a separate process. Collapsing them would force the API to
read checkpointer internals to answer "what's the status of my job?", and would
rewire shipped endpoints for no gain.

The decisive enabler is ADR-0005's in-process execution: because a graph resumes
with a plain `graph.invoke()`, the cron-drain can own resumption with no broker
and no worker daemon. The checkpointer's cross-process pause/resume is precisely
what teacher-review HITL (AI editor #30–36, bulk-gen review #145/#147) needs: the
graph interrupts, its state persists under `thread_id`, the ledger row flips to
"awaiting review", and a later request resumes the same thread.

## Considered options

- **Checkpointer as the job store** (thread = job, thin index only) — rejected.
  It re-tools the shipped `IngestionJob` and poll endpoints around thread state
  and makes status a projection out of checkpointer internals. Churn on working
  code for fewer tables we don't need fewer of.
- **Job models only, `MemorySaver` in-process** — rejected. Zero new persistence,
  but no cross-process resume and no durable HITL pause: the editor and bulk-gen
  review flows could not pause-and-wait, which is the main reason to adopt
  LangGraph here at all.

## Consequences

- Async-workflow ledger models gain a `thread_id` field pointing at the graph
  thread; status vocabulary grows an "awaiting human input" state for HITL
  workflows.
- The cron-drain command becomes the single place that invokes/resumes graphs.
  Non-HITL graphs run to completion in one drain pass; HITL graphs interrupt,
  persist, and resume on a later pass or request.
- `PostgresSaver` needs its checkpoint tables migrated into the same Postgres
  (one `.setup()` call / migration). No new datastore — consistent with #105.
- Reading job status stays a plain ledger query; the API and frontend poll path
  are untouched in shape.
