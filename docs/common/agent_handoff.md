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

Changed: backend LLM calls now go through `ai_services.llm.LiteLLMClient`.
`bank.ingestor` imports the gateway from `ai_services.llm` directly; the old
`bank.llm` compatibility wrapper has been deleted.

Files: `backend/ai_services/llm.py`, `backend/bank/ingestor.py`,
`backend/requirements.txt`, `.env.example`

Boundary: no provider SDK calls in React or feature modules; new editor AI
endpoints should call `ai_services.llm`.

Next: add `/api/ai/chat/` and `/api/ai/review-paper/` with validated schemas;
keep V1 guardrail that AI cannot rewrite sourced question text.
