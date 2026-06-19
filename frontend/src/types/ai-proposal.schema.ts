/**
 * Zod runtime schema + guard registry for the AI editor proposal contract.
 *
 * The editor AI never returns a re-written paper; it returns a scoped *proposal*
 * — a small list of replace-only patches against `PaperDocumentV1` — or a
 * guardrail *refusal*. This module parses that response shape at the API
 * boundary and owns the guard-id registry. The deny-by-default guard *logic*
 * (which paths are allowed, marks recompute) lives in `src/lib/ai-proposal.ts`;
 * the backend mirror is `backend/ai_editor/proposals.py` and the shared contract
 * is `contracts/ai_proposal.v1.md`.
 *
 * Patterns:
 * - `op`/`value` are permissive at the schema layer so an unknown operation or a
 *   non-scalar BlockNote value surfaces as a *user-safe guard*, not a parse error.
 * - Patches address by stable id (`/paper/sections/<id>/...`), never array index.
 * - `GUARD_MESSAGES` keys are the contract pinned by the backend parity test.
 *
 * Where it fits:
 * - Used by: `src/lib/ai-proposal.ts`, the assistant chat/inspector.
 * - Mirrors: `backend/ai_editor/proposals.py`.
 *
 * @module aiProposalSchema
 */
import { z } from 'zod';

/**
 * Guard ids and the user-safe message each carries into the chat/inspector.
 * Mirrored verbatim from `backend/ai_editor/proposals.py::GUARD_MESSAGES`; the
 * backend parity test pins this id set so the two cannot drift silently.
 */
export const GUARD_MESSAGES = {
  stale_base_revision:
    'The paper changed after this suggestion was prepared. Please ask again.',
  proposal_too_large: 'This suggestion is too large to apply safely.',
  unsupported_operation:
    'I can only update existing fields, not add, remove, or move parts of the paper.',
  unknown_target:
    'This suggestion points at a part of the paper that no longer exists.',
  forbidden_question_text: "I can't rewrite sourced question text.",
  forbidden_question_source: "I can't change question-bank source data.",
  forbidden_question_swap: "I can't change which question fills a slot here.",
  forbidden_question_count: "I can't add or remove questions.",
  forbidden_section_membership:
    "I can't change which questions belong to a section.",
  forbidden_raw_content:
    'I can only set plain text or a number here, not raw editor content.',
  forbidden_value_type: "That value isn't the right type for this field.",
  forbidden_path: "I can't change that part of the paper.",
} as const;

export type GuardId = keyof typeof GUARD_MESSAGES;

export const editPatchSchema = z
  .object({
    op: z.string(),
    path: z.string(),
    value: z.unknown().optional(),
    oldValue: z.unknown().optional(),
  })
  .passthrough();

export const guardViolationSchema = z
  .object({
    guardId: z.string(),
    message: z.string(),
    path: z.string().optional(),
  })
  .passthrough();

export const proposalValidationSchema = z
  .object({
    blocking: z.array(guardViolationSchema),
    warnings: z.array(z.string()),
  })
  .passthrough();

export const affectedAreaSchema = z
  .object({
    type: z.string(),
    label: z.string().optional(),
  })
  .passthrough();

export const editProposalSchema = z
  .object({
    status: z.literal('proposal'),
    jobId: z.union([z.string(), z.number()]),
    baseRevision: z.number(),
    summary: z.string(),
    affected: z.array(affectedAreaSchema),
    patches: z.array(editPatchSchema),
    validation: proposalValidationSchema,
  })
  .passthrough();

export const refusalSchema = z
  .object({
    status: z.literal('refused'),
    message: z.string(),
    brokenGuards: z.array(z.string()),
  })
  .passthrough();

/**
 * Endpoint-specific union the chat reads. Discriminated on `status` so the UI
 * routes proposal vs refusal without guessing (PRD #30 "without relying on
 * generic UI guessing").
 */
export const proposalResponseSchema = z.discriminatedUnion('status', [
  editProposalSchema,
  refusalSchema,
]);

export type EditPatch = z.infer<typeof editPatchSchema>;
export type GuardViolation = z.infer<typeof guardViolationSchema>;
export type ProposalValidation = z.infer<typeof proposalValidationSchema>;
export type EditProposal = z.infer<typeof editProposalSchema>;
export type Refusal = z.infer<typeof refusalSchema>;
export type ProposalResponse = z.infer<typeof proposalResponseSchema>;
