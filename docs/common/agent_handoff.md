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

### 2026-06-06 — Schema-Aware Question Edit Overlay

Commit: PENDING
Owner: Varad / Codex

Changed: issue #112 adds a focused QPG BlockNote overlay, round-trip conversion
for current Question types, safe read-only handling for future types, and
paper-local full-content overrides for collection edits.

Files: `frontend/src/lib/question-editing.ts`,
`frontend/src/lib/question-blocknote-schema.tsx`,
`frontend/src/components/editor/question-edit-overlay.component.tsx`,
`frontend/src/lib/paper-document.ts`, `backend/papers/pdf.py`

Boundary: this issue does not remove existing inline paper-canvas editing or add
instruction/answer overlays; those remain #120 and #113.

Next: implement #113 after its answer-document dependencies, then #120 should
make focused actions the only V1 manual-edit entry points.

### 2026-05-30 — Backend PaperDocumentV1 Assemble Gap

Commit: PENDING
Owner: Backend / Animesh

Changed: frontend issue #21 now validates and normalizes `PaperDocumentV1`,
but live backend assemble responses still need backend-owned V1 alignment in
GitHub issue #38.

Files: `backend/papers/document.py`, `backend/papers/tests/test_builder.py`

Boundary: no backend code is changed in the frontend #21 branch; do not carry
unverified backend edits in Varad/frontend work.

Next: for #38, backend should emit top-level `format` and always-present
`alternateQuestionIds` (`[]` when empty) from `/api/papers/assemble`, with
backend pytest coverage.

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

Changed: backend LLM calls now go through `ai_services.llm.LiteLLMClient`.
`bank.ingestor` imports the gateway from `ai_services.llm` directly; the old
`bank.llm` compatibility wrapper has been deleted.

Files: `backend/ai_services/llm.py`, `backend/bank/ingestor.py`,
`backend/requirements.txt`, `.env.example`

Boundary: no provider SDK calls in React or feature modules; new editor AI
endpoints should call `ai_services.llm`.

Next: add `/api/ai/chat/` and `/api/ai/review-paper/` with validated schemas;
keep V1 guardrail that AI cannot rewrite sourced question text.
