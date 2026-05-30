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

### 2026-05-30 — Mocked PaperDocumentV1 Frontend Contract

Commit: `9ddedb9`
Owner: Varad / Codex

Changed: issue #20 now has Vitest-backed frontend contract tests,
`mockPaperDocumentV1`, and TypeScript/Zod contract updates.

Files: `frontend/src/mocks/*`, `frontend/src/types/*`,
`frontend/package.json`, `docs/Varad/ralph_loop.md`,
`docs/Varad/scratchboards/issue-20-implementation.md`

Boundary: no normalization, BlockNote rendering, editor UI, or backend
generation changes are included.

Next: implement #21 normalization/runtime validation; backend still needs to
emit top-level `format` and required slot fields for live assemble responses.

### 2026-05-30 — Varad Contract + Upstream Skills

Commit: `c2dd0ee`
Owner: Varad / Codex

Changed: finalized Varad `PaperDocumentV1` backbone for backend/frontend work
and refreshed `.claude/skills` to prioritize upstream engineering skills.

Files: `docs/Varad/v1_contract.md`,
`docs/Varad/scratchboards/issue-20-mocked-paperdocument-v1.md`,
`.claude/skills/*`, `docs/agents/*`, `AGENTS.md`, `CLAUDE.md`

Boundary: this handoff commit intentionally excludes frontend Vitest/mock
implementation files; backend team should build against the documented
contract, including `format`, slot alternates/locks, and slot-level overrides.

Next: backend should emit top-level `format` and align `PaperDocumentBuilder`
with required slot fields before editor normalization work proceeds.

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
