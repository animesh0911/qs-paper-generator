# Agent Handoff

Keep this file lean. Each entry should be skimmable in under 30 seconds: one
sentence for what changed, a short file list, hard boundaries, and immediate
next steps only.

## Update Rules

- Add new entries at the top of the log.
- Always include `Commit`, `Owner`, `Files`, `Boundary`, and `Next`.
- Use `Commit: PENDING` only until the implementation commit exists.
- Do not rewrite old entries except to replace `PENDING` with the final commit.
- To understand an entry, run `git show --stat <commit>`.

## Log

### 2026-05-29 — Shared LiteLLM Gateway

Commit: `db0edda`
Owner: Varad / Codex

Changed: backend LLM calls now go through `ai_services.llm.LiteLLMClient`;
`bank.llm` is only a compatibility wrapper for ingestion.

Files: `backend/ai_services/llm.py`, `backend/bank/llm.py`,
`backend/requirements.txt`, `.env.example`

Boundary: no provider SDK calls in React or feature modules; new editor AI
endpoints should call `ai_services.llm`.

Next: add `/api/ai/chat/` and `/api/ai/review-paper/` with validated schemas;
keep V1 guardrail that AI cannot rewrite sourced question text.
