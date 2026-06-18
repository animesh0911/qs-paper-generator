/**
 * AI editor proposal response contract.
 *
 * Pins the parse boundary the assistant reads: a proposal and a refusal each
 * parse and route by `status`, and malformed model output (missing patches,
 * unknown status) is rejected loudly rather than reaching the inspector as a
 * blank diff. This is the structural layer beneath the semantic guards in
 * `src/lib/ai-proposal.ts`.
 */
import { describe, expect, it } from 'vitest';
import {
  editProposalSchema,
  proposalResponseSchema,
  refusalSchema,
} from './ai-proposal.schema';

const PROPOSAL = {
  status: 'proposal',
  jobId: 'ai_job_123',
  baseRevision: 12,
  summary: 'Updated Section B instructions.',
  affected: [{ type: 'section', sectionId: 'section-b', label: 'Section B' }],
  patches: [
    {
      op: 'replace',
      path: '/paper/sections/section-b/instructions',
      oldValue: 'Answer any four questions.',
      value: 'Answer any five questions.',
    },
  ],
  validation: {
    blocking: [],
    warnings: ['Total marks changed from 80 to 82.'],
  },
};

const REFUSAL = {
  status: 'refused',
  message: 'I cannot rewrite sourced question text.',
  brokenGuards: ['forbidden_question_text'],
};

describe('proposal response schema', () => {
  it('parses a proposal and a refusal', () => {
    expect(editProposalSchema.parse(PROPOSAL).patches).toHaveLength(1);
    expect(refusalSchema.parse(REFUSAL).brokenGuards).toEqual([
      'forbidden_question_text',
    ]);
  });

  it('routes the discriminated union by status', () => {
    const proposal = proposalResponseSchema.parse(PROPOSAL);
    const refusal = proposalResponseSchema.parse(REFUSAL);
    expect(proposal.status).toBe('proposal');
    expect(refusal.status).toBe('refused');
  });

  it('rejects a proposal missing required patches', () => {
    const withoutPatches: Record<string, unknown> = { ...PROPOSAL };
    delete withoutPatches.patches;
    expect(proposalResponseSchema.safeParse(withoutPatches).success).toBe(
      false,
    );
  });

  it('rejects an unknown status', () => {
    expect(
      proposalResponseSchema.safeParse({ ...PROPOSAL, status: 'whatever' })
        .success,
    ).toBe(false);
  });
});
