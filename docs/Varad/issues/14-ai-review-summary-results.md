Title: V: Add live AI summary and review result flows
Labels: V
GitHub: #34

## What to build

Connect Summary and Review Paper to backend AI jobs and render their results in the bottom chat and right inspector, with individual review fixes that can be applied safely.

## Acceptance criteria

- [ ] Summary endpoint returns a read-only overview result shown in the bottom chat.
- [ ] Review endpoint returns findings with severity, affected areas, concise summary, details, and optional proposed fixes.
- [ ] Review can propose individual safe swaps using `slotId`, `fromQuestionId`, `toQuestionId`, and reason.
- [ ] Review fixes are applied individually; there is no Apply All in V1.
- [ ] Swap fixes validate against slot alternatives, marks/type/section constraints, locked state, and current document revision.
- [ ] Review and summary results do not use guardrail-refusal semantics meant for edit proposals.

## Blocked by

Blocked by #31, #32, #25, #28.
