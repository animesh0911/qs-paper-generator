# Issue 115 — Question Edit Policy

## Public Interface

The schema-aware question overlay consumes a `QuestionType` edit policy from a
single frontend registry. A policy declares editable semantic regions,
collection operations, and apply-time validation.

Unregistered types are read-only and preserve their canonical
`PaperDocumentV1` content.

## Success Criteria

- Every current `QuestionType` has an explicit policy.
- Future types can add one policy without changing the overlay shell.
- `custom` is not used as a conversion target for unknown types.
- Unsupported edits fail before canonical paper state changes.
- User-facing copy avoids implementation vocabulary.

## Decisions

- Freeform flattening and a generic escape hatch are deferred.
- Labelled option/subpart identity is stable during an overlay session; display
  labels may be normalized when the draft is applied.
- Existing image assets may move or be deleted without changing the backend
  asset or bank Question.
- Internal-choice groups retain `displayStyle` and `chooseCount`; V1 edits
  options inside existing groups but does not add or remove groups.
- Unknown future types render read-only until their policy and round-trip tests
  are registered.

## Verification

- Policy recorded in
  `docs/common/backend_frontend_editor_integration_plan.md`.
- Implementation issue #112 can derive its registry and tests directly from
  the capability table.
