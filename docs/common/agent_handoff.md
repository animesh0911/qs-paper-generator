# Agent Handoff

## How To Update This File

This file is an append-only coordination log for agents working on the repo.
When you make a change that another agent should build on, add a new entry at
the top of the handoff log.

Each entry must include:

- `Commit`: the implementation commit or commit range the entry explains.
- `Owner`: the human/agent responsible for the change.
- `Summary`: what changed in plain language.
- `Files`: the important files to read first.
- `Boundary`: what future agents should or should not change.
- `Next`: the most useful next steps.

If the implementation is not committed yet, use `Commit: PENDING` and include
`Base commit: <sha>` so the next agent knows which HEAD the work started from.
After the code is committed, update the entry with the final implementation
commit hash. Do not rewrite old entries except to replace `PENDING` with the
actual commit hash for the same change.

Recommended workflow for another agent after pulling:

1. Read this file first.
2. For each relevant entry, inspect the referenced commit:
   `git show --stat <commit>` and `git show <commit> -- <files>`.
3. Continue from the `Next` section instead of rediscovering the same context.

## Handoff Log

### 2026-05-29 — Shared LiteLLM Gateway For Backend AI Calls

Commit: `db0edda`
Base commit: `a4acae3`
Owner: Varad / Codex

Summary:

The backend LLM call path was lifted from custom provider-specific wrappers to
a shared LiteLLM gateway. Existing question-bank ingestion still calls
`bank.llm.make_llm_client()`, but that now delegates to
`ai_services.llm.LiteLLMClient`, which calls `litellm.completion()`.

Current call path:

```text
bank.ingestor
  -> bank.llm.make_llm_client()
  -> ai_services.llm.LiteLLMClient
  -> litellm.completion()
  -> configured provider model
```

Files:

- `backend/ai_services/llm.py`
- `backend/ai_services/tests/test_llm.py`
- `backend/bank/llm.py`
- `backend/requirements.txt`
- `.env.example`
- `backend/pyproject.toml`

Boundary:

- Do not add new OpenAI, Anthropic, or Gemini SDK wrappers in feature modules.
- Do not call model providers directly from React.
- Future editor AI endpoints should call the shared backend AI gateway.
- Keep React-to-Django API calls in `frontend/src/lib/api.ts`; LiteLLM belongs
  behind Django, not in the frontend.
- `bank.llm` is now a compatibility export for ingestion, not the place for new
  editor AI behavior.

Next:

- Add an editor-facing backend AI app or route group, for example
  `/api/ai/chat/` and `/api/ai/review-paper/`.
- Define Pydantic/serializer schemas for chat and review responses before
  allowing model output to affect editor state.
- Keep V1 guardrail: AI must not rewrite sourced question text.
- Decide model defaults per action. Likely small/fast model for chat and a
  stronger model for whole-paper review.
- Add throttling and request logging around editor AI endpoints.
