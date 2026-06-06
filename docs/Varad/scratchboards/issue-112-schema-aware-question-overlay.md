# Issue 112 — Schema-Aware Question Overlay

## Public Interfaces

- `questionToSemanticBlocks(question)` converts canonical Question content into
  QPG BlockNote blocks.
- `semanticBlocksToQuestionContent(type, blocks, originalContent)` validates and
  maps an overlay draft back to canonical content.
- `setSlotContentOverride(state, slotId, content)` stores structural edits on
  the paper Slot without mutating the source Question.
- `QuestionEditOverlay` owns transient BlockNote state and applies only a valid
  draft.

## Success Criteria

- Every current `QuestionType` round-trips without losing semantic regions.
- Unknown future types load safely and remain read-only until registered.
- Options, subparts, and choice options retain collection identity and order.
- Image, image-placeholder, equation, and table items remain typed content.
- Unsupported freeform blocks reset the overlay draft and do not change paper
  state.
- Source Questions in `questions[]` remain immutable.

## Contract Decision

Legacy `overrides.regions` cannot represent collection add/remove/reorder.
Optional `overrides.content` stores a full paper-local Question content override
for those edits. It is additive and takes precedence over source content while
old region-only drafts remain valid.

## Verification

- Focused converter, state, mapper, action-rail, and contract tests.
- Full frontend test, type-check, build, and lint gate.
- Browser verification at the default desktop viewport and 390px mobile:
  focused overlay opens, stays open during option insertion, uses the light
  BlockNote theme, and rejects/reset empty options before apply.
- Backend PDF fallback test was added. Local pytest collection is blocked
  because the existing venv lacks `fitz`; `compileall` passes for the changed
  renderer and test modules.
- Antigravity review found and Codex accepted two issues: required-region
  deletion was being restored silently, and subpart region keys had drifted.
  Required deletions now fail loud, canonical `subpart:<label>` keys are used,
  and legacy `subquestion:<label>` overrides remain readable.
