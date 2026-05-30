Title: V: Define AI proposal schema and hard guardrail validators
Labels: V
GitHub: #32

## What to build

Define the AI proposal contract and deterministic validators that protect canonical paper state from unsafe model output before any preview or apply action is enabled.

## Acceptance criteria

- [ ] Editor-edit proposals use scoped patches, not full modified documents and not BlockNote JSON.
- [ ] Allowed patch paths include paper title/header, general instructions, section titles, section instructions, approved format fields, and marks fields.
- [ ] Validators reject changes to sourced question text, question-bank source data, section membership, question count, cross-section movement, raw BlockNote JSON, unknown operations, missing IDs, oversized output, and stale `baseRevision`.
- [ ] Marks changes are allowed but trigger total recomputation or validation warnings.
- [ ] Guardrail refusal responses carry a user-safe message and broken guard ids.
- [ ] Backend and frontend share the same proposal schema or equivalent generated/runtime validation.

## Blocked by

Blocked by #21, #31.
