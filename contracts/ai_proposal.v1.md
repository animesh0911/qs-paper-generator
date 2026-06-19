# AI Editor Proposal Contract V1

**Product:** AI-assisted question-paper builder
**Audience:** Frontend and backend teams
**Parent:** PRD #30 · Issue #32
**Goal:** Define the scoped proposal the editor AI returns and the deterministic
guardrails that decide — independently of the model — whether it may reach
preview/apply.

## 1. Principle

The model never returns a re-written paper and never returns BlockNote JSON. It
returns a **scoped proposal**: a small list of `replace`-only **patches** against
the canonical `PaperDocumentV1` (see `contracts/v1_contract.md`), or a guardrail
**refusal**. The model is never the source of truth for safety — every proposal
passes the same deterministic validators on the backend (before it is stored) and
the frontend (before Apply is enabled).

Both validators are mirrors:

- Backend: `backend/ai_editor/proposals.py`
- Frontend: `frontend/src/types/ai-proposal.schema.ts` + `frontend/src/lib/ai-proposal.ts`

The guard-id set below is pinned by a parity test on each side.

## 2. Response shapes

Endpoint-specific, discriminated on `status` (PRD #30: no generic UI guessing).
These shapes are the validated **`job.result`** payload — the async job poll
envelope (`GET /api/ai/jobs/{jobId}/`, #31) carries the job lifecycle `status`
(`pending`/`running`/`done`/…) at its top level and nests this proposal/refusal
under `result`. Parse `result` with these schemas only once the job is `done`.

### Proposal

```json
{
  "status": "proposal",
  "jobId": "ai_job_123",
  "baseRevision": 12,
  "summary": "Updated Section B instructions.",
  "affected": [
    { "type": "section", "sectionId": "section-b", "label": "Section B" }
  ],
  "patches": [
    {
      "op": "replace",
      "path": "/paper/sections/section-b/instructions",
      "oldValue": "Answer any four questions.",
      "value": "Answer any five questions."
    }
  ],
  "validation": {
    "blocking": [],
    "warnings": ["Total marks changed from 80 to 82."]
  }
}
```

A non-empty `validation.blocking` means Apply stays disabled. `oldValue` is
advisory (inspector diff only) — guards read the live document, never `oldValue`,
so a wrong `oldValue` cannot widen what Apply touches.

### Refusal

```json
{
  "status": "refused",
  "message": "I cannot rewrite sourced question text.",
  "brokenGuards": ["forbidden_question_text"]
}
```

## 3. Patches

| Field      | Type                        | Notes                                            |
| ---------- | --------------------------- | ------------------------------------------------ |
| `op`       | string                      | Only `replace` is allowed. Others → unsupported. |
| `path`     | JSON Pointer                | **ID-addressed**, not array index (see §4).      |
| `value`    | string \| number            | Scalar, typed per field: text fields require a string, slot marks require a number. Structured value → raw content. |
| `oldValue` | any (optional)              | Advisory; not trusted by guards.                 |

Patches address by **stable id** (`/paper/sections/<sectionId>/...`), never array
index, so a reorder can never silently retarget a patch (#32 decision).

## 4. Allowed paths (deny-by-default)

A patch is allowed **only** when it is a `replace` whose `path` matches one of
these, the ids resolve in the live document, and the value is the field's
expected type. A block id resolves **only** within the collection its path names
(`chromeBlocks` vs `instructionBlocks`). Everything else is blocked.

| Path                                                                             | Edits                      |
| -------------------------------------------------------------------------------- | -------------------------- |
| `/paper/title`, `/paper/subtitle`                                                | Paper title / subtitle     |
| `/paper/chromeBlocks/<blockId>/text`                                             | Header / masthead text     |
| `/paper/instructionBlocks/<blockId>/text`                                        | General instructions       |
| `/paper/sections/<sectionId>/title`                                              | Section title              |
| `/paper/sections/<sectionId>/subtitle`                                           | Section subtitle           |
| `/paper/sections/<sectionId>/instructions`                                       | Section instructions       |
| `/paper/sections/<sectionId>/slots/<slotId>/marks`                               | Slot marks (warns, see §6) |
| `/format/page/size`, `/format/page/orientation`                                  | Approved format fields     |
| `/format/layout/{marks,questionNumbers,mcqOptions,instructions,masthead,footer}` | Approved format fields     |

Derived totals (`/paper/totalMarks`, `/paper/sections/<id>/marks`) are **not**
patchable — they are recomputed from slot marks by the reducer.

## 5. Guard registry

Every blocking guard carries a `guardId` and a user-safe `message` (no path/JSON
jargon). Adding or renaming an id requires updating both mirrors and the doc; the
parity tests enforce the set.

| Guard id                       | Rejects                                                      |
| ------------------------------ | ----------------------------------------------------------- |
| `stale_base_revision`          | `baseRevision` ≠ the paper's current revision               |
| `proposal_too_large`           | > 40 patches or > 20 000 value chars                        |
| `unsupported_operation`        | Any `op` other than `replace` (add/remove/move/copy)        |
| `unknown_target`               | A `sectionId`/`slotId`/`blockId` that does not resolve       |
| `forbidden_question_text`      | Any `/questions/...` content or `rawText`                    |
| `forbidden_question_source`    | `/questions/<id>/source` or `/metadata` (question-bank data) |
| `forbidden_question_swap`      | `selectedQuestionId` / `alternateQuestionIds`               |
| `forbidden_question_count`     | A whole-slot or slots-collection target                     |
| `forbidden_section_membership` | A whole-section or sections-collection target               |
| `forbidden_raw_content`        | A non-scalar (object/array) value — raw BlockNote JSON       |
| `forbidden_value_type`         | A scalar of the wrong type for the field (e.g. text on marks) |
| `forbidden_path`               | Any other path outside the allowlist                        |

The PRD's forbidden categories (sourced question text, question-bank source data,
section membership, question count, cross-section movement, raw BlockNote JSON,
unknown operations, missing ids, oversized output, stale `baseRevision`) all fall
out of this single allowlist; the named guards make each rejection legible.

## 6. Marks

Marks edits are allowed but the model's arithmetic is never trusted. A valid slot
marks patch emits a `validation.warnings` entry
(`Total marks changed from X to Y.`) computed from the live slot marks; the
reducer performs the real recompute on Apply.
