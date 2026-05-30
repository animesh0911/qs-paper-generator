Title: V: Add AI editor endpoint and async job contracts
Labels: V
GitHub: #31

## What to build

Add the backend API surface for editor AI: typed intent routing, chat, summary, review, editor-edit, refine, and job polling. All model calls go through the shared LiteLLM gateway and return validated, endpoint-specific result shapes.

## Acceptance criteria

- [ ] Add `/api/ai/intent/`, `/api/ai/chat/`, `/api/ai/summarize-paper/`, `/api/ai/review-paper/`, `/api/ai/editor-edit/`, `/api/ai/editor-edit/refine/`, and `/api/ai/jobs/{jobId}/` route contracts.
- [ ] Button-triggered actions can call their endpoint directly without intent classification.
- [ ] Typed text uses the intent endpoint with product context and examples.
- [ ] Async endpoints return a job id and store V1 state in Redis/Celery memory state only.
- [ ] All model calls use `ai_services.llm`; no provider SDK or provider key is used by frontend code.
- [ ] Endpoint responses distinguish chat, summary, review, proposal, refused, validation-failed, pending, failed, and completed states without relying on generic UI guessing.

## Blocked by

Blocked by #28.
