# PRD: AI Editor Integration for BlockNote Paper Editor

Labels: V
GitHub: #30

## Problem Statement

Teachers need AI help while editing a generated question paper, but the AI must
not damage the exam structure or silently rewrite sourced question text. The
paper editor should feel AI-assisted: the teacher can ask questions, request
safe formatting/section changes, summarize the paper, review the paper, and
accept suggested fixes. At the same time, the teacher should never need to see
canonical JSON or understand BlockNote internals.

The project now has a shared LiteLLM backend gateway, but the editor has no
live AI endpoints, no proposal contract, no validation boundary, and no
teacher-confirmed apply flow.

## Solution

Build AI editor integration as a controlled proposal system. Typed chat goes to
a backend intent classifier. Button actions skip classification and call the
specific backend endpoint. Long-running AI requests run as async jobs with
Redis-backed V1 job state. The backend sends the full canonical paper document
plus product guardrails to the model, then returns scoped proposals or read-only
results.

The frontend auto-previews edit proposals, shows a compact two-line summary in
the bottom chat, shows detailed diffs in the right inspector, highlights affected
paper fields, and applies changes only after teacher confirmation. Canonical
paper state changes only through our reducers; BlockNote re-renders from that
state. We do not use `@blocknote/xl-ai` or BlockNote AI server packages, but we
borrow the UX pattern of scoped preview, accept, reject, and refine.

## User Stories

1. As a teacher, I want to ask the editor questions in a bottom chatbox, so that I can understand the current paper and product workflow without leaving the editor.
2. As a teacher, I want off-topic typed requests to be politely rejected, so that the assistant stays paper-focused.
3. As a teacher, I want Review Paper to analyze the full CBSE Class 10 paper, so that I can see coverage, difficulty, format, duplication, marks, and quality concerns.
4. As a teacher, I want Summary to describe the paper separately from Review, so that I can get a fast overview without fixes.
5. As a teacher, I want AI edit requests to auto-preview changes, so that I can inspect the result before applying it.
6. As a teacher, I want AI to change safe paper chrome like title, headers, instructions, section labels, marks, and format settings, so that repetitive formatting work is faster.
7. As a teacher, I do not want AI to rewrite sourced question text, so that question provenance and trust are preserved.
8. As a teacher, I want AI review findings to propose individual fixes, so that I can apply only the fixes I agree with.
9. As a teacher, I want review findings to suggest safe swaps where useful, so that weak questions can be replaced without manual searching.
10. As a teacher, I want one proposal at a time, so that I do not accidentally apply stale AI output.
11. As a teacher, I want Refine to adjust the current proposal, so that I can steer a suggestion without starting from scratch.
12. As a teacher, I want Apply and Dismiss buttons only after a response is ready, so that pending output cannot be applied.
13. As a teacher, I want detailed diffs in the inspector, so that the bottom chat can stay compact.
14. As a frontend developer, I want a stable AI proposal contract, so that chat UI, inspector diffs, paper highlights, and reducers can be implemented independently.
15. As a backend developer, I want all model calls through the LiteLLM gateway, so that provider choice and secrets stay server-side.
16. As a backend developer, I want deterministic validation after model output, so that model reasoning does not become the source of truth for safety.
17. As a product owner, I want BlockNote AI and CopilotKit captured as spikes, so that we can learn from them without committing the MVP to their runtime or license constraints.

## Implementation Decisions

- Do not use `@blocknote/xl-ai` or `@blocknote/xl-ai-server` in production MVP code. They may be studied as UX/architecture inspiration only unless licensing is explicitly resolved.
- Keep BlockNote as the paper editor surface.
- Keep canonical paper JSON as the source of truth. BlockNote JSON is transient view state.
- Send full canonical paper document to editor AI jobs, not raw BlockNote JSON or HTML.
- Use Django backend endpoints and the shared `ai_services.llm` LiteLLM gateway for all model calls.
- Button-triggered actions skip intent classification because the endpoint already defines the expected result shape.
- Typed chat goes through a backend intent classifier with product context and examples.
- Do not define a narrow list of user-visible allowed intents. The classifier should identify whether the request is paper/editor-related and route to chat, summary, review, editor edit, or off-topic refusal.
- Use separate endpoints for typed intent, chat, summary, review, editor edit, refine, and job polling.
- V1 async job state lives in Redis/Celery memory state only. No persisted `AIJob` model in V1.
- Only one active AI job/proposal is allowed per editor session.
- While an AI edit/review job that can propose changes is pending, block structured editor mutations and allow reading/navigation.
- Frontend tracks an in-memory monotonic `documentRevision`. AI requests include `baseRevision`; responses are accepted only when the base revision still matches.
- The model returns scoped proposals, not a full modified paper.
- Canonical state updates only through our reducers.
- Allowed AI edit targets: paper title/header, general instructions, section titles, section instructions, approved format fields, and marks fields.
- Marks edits are allowed, but must recompute totals or surface validation warnings.
- Forbidden AI edits: sourced question stem/options/subparts/passage text, raw question-bank data, section membership, question count, cross-section movement, arbitrary BlockNote JSON, silent apply.
- Answer-key mutation is deferred and out of scope for V1 AI editor integration.
- Review output is read-only until the teacher applies an individual proposed fix.
- Review can propose swaps using `{ type: "swap_question", slotId, fromQuestionId, toQuestionId, reason }`.
- Apply All is out of scope for V1; fixes are applied individually.
- Refine is stateless in V1: resend full paper, base revision, original instruction, current proposal, refinement instruction, and guardrails.
- Refined result replaces the active proposal and auto-previews again.
- Bottom chat result cards stay lean: max two-line summary, affected areas, and action buttons after completion.
- Right inspector owns detailed diffs and validation diagnostics.
- Paper canvas highlights affected fields but does not show diff text inside the printable paper.
- Model-declared guardrail refusal is displayed to the user, but deterministic backend/frontend validation still decides whether Apply is enabled.

## API Contracts

- `POST /api/ai/intent/`: classify typed user text and return a route or off-topic response.
- `POST /api/ai/chat/`: answer paper/editor-focused questions without proposing document changes.
- `POST /api/ai/summarize-paper/`: create a read-only summary job.
- `POST /api/ai/review-paper/`: create a review job with findings and optional individual fix proposals.
- `POST /api/ai/editor-edit/`: create an editor edit proposal job.
- `POST /api/ai/editor-edit/refine/`: refine the active editor edit proposal.
- `GET /api/ai/jobs/{jobId}/`: poll async job state and result.

Editor edit responses should be endpoint-specific:

```json
{
  "status": "proposal",
  "jobId": "ai_job_123",
  "baseRevision": 12,
  "summary": "Updated Section B instructions and total marks.",
  "affected": [
    { "type": "section", "sectionId": "section-b", "label": "Section B" }
  ],
  "patches": [
    {
      "op": "replace",
      "path": "/paper/sections/1/instructions",
      "oldValue": "Answer any four questions.",
      "value": "Answer any five questions."
    }
  ],
  "validation": {
    "blocking": [],
    "warnings": [
      "Total marks changed from 80 to 82."
    ]
  }
}
```

Guardrail refusal responses:

```json
{
  "status": "refused",
  "message": "I cannot rewrite sourced question text.",
  "brokenGuards": ["no_source_question_rewrite"]
}
```

Review finding proposal:

```json
{
  "findingId": "finding_1",
  "severity": "warning",
  "summary": "Section C has two near-duplicate electricity questions.",
  "proposedFix": {
    "type": "swap_question",
    "slotId": "slot_c_03",
    "fromQuestionId": "q_22",
    "toQuestionId": "q_41",
    "reason": "Same marks/type with different topic coverage."
  }
}
```

## Testing Decisions

- Backend tests should verify that every AI endpoint uses `ai_services.llm` and never exposes provider keys to the frontend.
- Classifier tests should cover editor edit, chat, summary, review, refine bypass, and off-topic requests.
- Schema tests should reject malformed model output, unknown patch operations, missing IDs, stale base revisions, oversized output, and forbidden paths.
- Guardrail tests should prove question text, question-bank source data, section membership, question count, and raw BlockNote JSON cannot be changed by AI proposals.
- Reducer tests should prove valid proposals update canonical state and trigger derived validation.
- UI tests should prove pending jobs block structured mutations, completed proposals auto-preview, buttons appear only after completion, and stale proposals cannot apply.
- Review tests should prove individual fix application works and Apply All is absent.
- Diff rendering tests should prove bottom chat stays compact while inspector shows detailed before/after diffs.

## Out of Scope

- Using BlockNote AI packages in production MVP code.
- CopilotKit adoption in production MVP code.
- Direct model mutation of React components.
- Raw BlockNote JSON/HTML editing by the model.
- AI rewrite of sourced question text.
- Answer-key mutation.
- Persisted AI job history.
- Multi-proposal queueing.
- Apply All for review fixes.
- Live question-bank semantic/RAG search beyond precomputed alternatives.

## Further Notes

The best outside inspiration is split: BlockNote AI for the proposal/preview UX,
CopilotKit for human-in-the-loop action rendering, and Puck for schema-first AI
editing. The MVP should borrow those patterns without adopting their runtimes.
