Title: V: Add bottom assistant chat and paper review scaffold without live LLM integration
Labels: V

## What to build

Add the bottom floating assistant surface and review-paper entry point so the UI direction is present, while keeping live model integration out of scope for this slice.

## Acceptance criteria

- [ ] Bottom chat is persistently accessible from the editor without hiding the paper.
- [ ] Chat can receive selected-question context from the Ask action.
- [ ] Review paper button writes a mocked or deterministic review result into the chat surface.
- [ ] Chat helper copy states that V1 can explain/review/suggest but cannot rewrite sourced question text.
- [ ] The mocked result card uses the same UI slots planned for live AI results: two-line summary, affected areas, pending state, completed state, and action buttons that appear only after a response is ready.
- [ ] The scaffold does not depend on `@blocknote/xl-ai`; BlockNote AI behavior is only product inspiration.
- [ ] No frontend model-provider key is exposed.
- [ ] Live LLM calls are not implemented in this slice.

## Blocked by

Blocked by #22, #24.
