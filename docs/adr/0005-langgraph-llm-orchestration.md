# LangGraph + LangChain as the LLM-workflow orchestration layer

Every multi-step **LLM-judgment workflow** (generation, the generate→verify
loop, the AI editor, bulk question generation, future RAG) is expressed as a
compiled **LangGraph `StateGraph`** — the single workflow idiom — and every model
call goes through a provider-agnostic **LangChain chat model** built by a
`make_chat_model(purpose)` factory in `ai_services.llm`. The deterministic engine
(`TemplateBuilder`, `QuestionPicker`, `PaperBuilder`, `bank.guardrails`,
`MARKS_TO_SECTION`) stays plain Python that graphs *call* — it is not migrated.

This records a design decision taken in a `/grill-with-docs` review; it is
sequenced for implementation (see Consequences), not yet built.

## Why

The project keeps acquiring LLM-judgment surfaces that are genuinely
graph-shaped — they branch on model output, loop with retries, pause for teacher
review, and run as long jobs. The PRD's Slice-8 generate→verify loop
(Reflection + Evaluation patterns), the AI editor (#30–36: Routing + Guardrails +
Human-in-the-Loop), and bulk generation (#141–152: a long, resumable job) all
have all four traits. Hand-rolling state machines, retry loops, and durable
pause/resume for each of these — over and over, by hand — is the cost LangGraph
removes. Its leverage is exactly the four things plain code lacks: model-driven
branching, retry loops, durable HITL pause/resume, and checkpointed long jobs.

Crucially, LangGraph runs **in-process** via `graph.invoke()` — no worker
daemon. That is what makes it compatible with this project's deliberate
no-Celery/no-Redis stance (#105): graphs slot *into* the existing
Postgres-backed, cron-drained job pattern instead of resurrecting a broker. See
ADR-0006 for how the checkpointer and the job ledger divide responsibility.

LangChain chat models (`init_chat_model`) are adopted at the model seam because
provider-agnosticism is a documented project direction, not a hypothesis: we may
run a local model (#134 — evaluate local `chandra-ocr-2` as a Gemini extraction
replacement) or swap Gemini↔Claude (the PLAN.md assumes Claude for gen+verify
while the code uses Gemini). One interface over Gemini/Claude/OpenAI/local, plus
automatic LLM-call observability (tokens, prompts, latency) when traced — which a
graph wrapper around a raw SDK call does **not** give, because the call stays
opaque inside the node. Observability belongs at the model seam every call
already passes through, not in per-call graph wrappers.

## Considered options

- **Migrate the entire repo to LangGraph, deterministic code included** —
  rejected. Putting `QuestionPicker` or `MARKS_TO_SECTION` behind a `StateGraph`
  buys nothing: no nondeterminism, no branching, no human pause. It fails the
  deletion test (delete the graph wrapper and complexity just moves) and violates
  Rules 2/3/5. LangGraph is the orchestration layer over a pure-Python engine, not
  a replacement for it.
- **Wrap every LLM call — including one-shot calls — in a one-node graph for
  uniformity** — rejected. A `StateGraph` around a single `generate_text()` is a
  shallow module (interface ≈ implementation) and does not, by itself, yield
  token-level observability. The consistency goal is met instead by one model
  seam (altitude 1) plus one workflow idiom (altitude 2); single calls stay on
  the seam.
- **Functional API (`@entrypoint`/`@task`) as the workflow idiom** — rejected for
  consistency. It is a second construction idiom on top of the `StateGraph` one;
  the team wants a single pattern. `StateGraph` is the community-standard,
  visualizable idiom and is clearer for the branchy editor/verifier flows.
- **Keep the bespoke `LLMClient` and instrument it by hand** — viable, but it
  forfeits LangChain's provider-swap ergonomics and the local-model integrations
  (#134) for no saving, since the seam is changing adapters anyway (it already did
  once: litellm → Gemini SDK, ADR-0004).

## Consequences

- `ai_services.llm` changes adapter again: the `make_chat_model(purpose) →
  BaseChatModel` factory owns provider/model/key/tracing/retry. `make_llm_client`
  and the `extract`/`generate_text` shape are retired or re-expressed over the
  factory. New deps: `langgraph`, `langchain`, the provider integrations
  (`langchain-google-genai`, etc.). The bespoke `google-genai` path may be kept
  **only** for the native-PDF extraction call until a benchmark proves
  `with_structured_output` parity.
- New home: a `workflows/` package holding one compiled `StateGraph` per LLM
  workflow, all invoked uniformly (`graph.invoke(state, {thread_id})`) against the
  shared checkpointer.
- Graph builders take `make_model=make_chat_model` so tests inject a fake factory
  (LangChain `GenericFakeChatModel`) — no module-level patching, consistent with
  `Ingestor(extractor=stub)` (Rules 9/11).
- Migration is sequenced: (1) swap the model seam, gating extraction behind an
  eval-parity run on the existing benchmark (`benchmark_extraction`,
  `content/eval/`, #99/#103) — a paid run requiring Rule-13 consent; (2)
  re-express extraction as a resumable `StateGraph`. Answer generation
  (`generate_answers`) rides the new seam with no logic change.
- RAG is **deferred**, not designed away: the recorded direction is pgvector +
  an embeddings factory mirroring `make_chat_model`, with simple top-k retrieval
  behind a shared `retrieve` seam.
- Residual risk: extraction quality can shift when leaving Gemini's native
  `response_schema` + `thinking_config`; the benchmark gate is the backstop, and
  `bank.guardrails` (Layer 2) still catches weak structured output from any
  provider.
