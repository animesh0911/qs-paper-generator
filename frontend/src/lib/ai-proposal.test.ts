/**
 * AI editor proposal guardrails (frontend mirror).
 *
 * These pin the re-validation that gates the teacher's Apply button: allowed
 * chrome edits pass, every forbidden category is rejected with the *same* named
 * guard the backend uses, and the guard-id set matches the contract. The why:
 * the model is never the source of truth for safety, so the frontend must reach
 * the same verdict the backend did — a drift here would enable Apply on a change
 * the backend would reject (`backend/ai_editor/tests/test_proposals.py`).
 */
import { describe, expect, it } from 'vitest';
import type { PaperDocument } from '@/types';
import { GUARD_MESSAGES, type EditPatch } from '@/types/ai-proposal.schema';
import { MAX_PATCHES, validateProposal } from './ai-proposal';

const DOCUMENT = {
  paper: {
    title: 'Science — Mock',
    subtitle: 'Class 10',
    chromeBlocks: [{ id: 'chrome-1', role: 'masthead', text: 'Header' }],
    instructionBlocks: [
      { id: 'instr-1', role: 'general', text: 'Answer all questions.' },
    ],
    sections: [
      {
        id: 'section-a',
        title: 'Section A',
        subtitle: 'Objective',
        instructions: 'Answer any four questions.',
        marks: 5,
        slots: [
          { id: 'slot-a1', marks: 2, selectedQuestionId: 'q1' },
          { id: 'slot-a2', marks: 3, selectedQuestionId: 'q2' },
        ],
      },
      {
        id: 'section-b',
        title: 'Section B',
        marks: 4,
        slots: [{ id: 'slot-b1', marks: 4, selectedQuestionId: 'q3' }],
      },
    ],
  },
} as unknown as PaperDocument;

const REVISION = 7;

function validate(
  patches: EditPatch[],
  { base = REVISION, current = REVISION } = {},
) {
  return validateProposal(DOCUMENT, patches, {
    baseRevision: base,
    currentRevision: current,
  });
}

function guardIds(result: ReturnType<typeof validate>): Set<string> {
  return new Set(result.blocking.map((entry) => entry.guardId));
}

describe('validateProposal allowed edits', () => {
  it.each([
    '/paper/title',
    '/paper/subtitle',
    '/paper/chromeBlocks/chrome-1/text',
    '/paper/instructionBlocks/instr-1/text',
    '/paper/sections/section-a/title',
    '/paper/sections/section-a/instructions',
    '/format/page/size',
    '/format/layout/marks',
  ])('passes the allowed chrome path %s', (path) => {
    const result = validate([{ op: 'replace', path, value: 'New value' }]);
    expect(result.blocking).toEqual([]);
  });

  it('allows a marks edit but warns on the recomputed total', () => {
    const result = validate([
      {
        op: 'replace',
        path: '/paper/sections/section-a/slots/slot-a1/marks',
        value: 4,
        oldValue: 2,
      },
    ]);
    expect(result.blocking).toEqual([]);
    expect(result.warnings).toEqual(['Total marks changed from 9 to 11.']);
  });

  it('does not warn when marks net to no change', () => {
    const result = validate([
      {
        op: 'replace',
        path: '/paper/sections/section-a/slots/slot-a1/marks',
        value: 2,
      },
    ]);
    expect(result.warnings).toEqual([]);
  });
});

describe('validateProposal forbidden categories', () => {
  it.each([
    ['/questions/q1/content/stem/0/text', 'forbidden_question_text'],
    ['/questions/q1/rawText', 'forbidden_question_text'],
    ['/questions/q1/source/name', 'forbidden_question_source'],
    ['/questions/q1/metadata/difficulty', 'forbidden_question_source'],
    [
      '/paper/sections/section-a/slots/slot-a1/selectedQuestionId',
      'forbidden_question_swap',
    ],
    ['/paper/sections/section-a/slots', 'forbidden_question_count'],
    ['/paper/sections/section-a/slots/slot-a1', 'forbidden_question_count'],
    ['/paper/sections', 'forbidden_section_membership'],
    ['/paper/sections/section-a', 'forbidden_section_membership'],
    ['/paper/totalMarks', 'forbidden_path'],
    ['/paper/sections/section-a/marks', 'forbidden_path'],
  ])('rejects %s with %s', (path, expectedGuard) => {
    const result = validate([{ op: 'replace', path, value: 'x' }]);
    expect(guardIds(result)).toContain(expectedGuard);
  });

  it.each(['add', 'remove', 'move', 'copy'])(
    'rejects the non-replace operation %s',
    (op) => {
      const result = validate([{ op, path: '/paper/title', value: 'x' }]);
      expect(guardIds(result)).toContain('unsupported_operation');
    },
  );

  it('rejects a raw BlockNote value on an allowed path', () => {
    const result = validate([
      {
        op: 'replace',
        path: '/paper/title',
        value: [{ type: 'paragraph', content: [] }],
      },
    ]);
    expect(guardIds(result)).toContain('forbidden_raw_content');
  });

  it('rejects an unknown target id', () => {
    const result = validate([
      {
        op: 'replace',
        path: '/paper/sections/section-z/instructions',
        value: 'x',
      },
    ]);
    expect(guardIds(result)).toContain('unknown_target');
  });

  it('treats a slot addressed under the wrong section as unknown', () => {
    const result = validate([
      {
        op: 'replace',
        path: '/paper/sections/section-b/slots/slot-a1/marks',
        value: 5,
      },
    ]);
    expect(guardIds(result)).toContain('unknown_target');
  });

  it.each([
    '/paper/chromeBlocks/instr-1/text', // instr-1 is an instruction block
    '/paper/instructionBlocks/chrome-1/text', // chrome-1 is a chrome block
  ])('rejects a block id addressed under the wrong collection: %s', (path) => {
    const result = validate([{ op: 'replace', path, value: 'x' }]);
    expect(guardIds(result)).toContain('unknown_target');
  });

  it.each([
    ['hello', 'forbidden_value_type'],
    [true, 'forbidden_value_type'],
    [[], 'forbidden_raw_content'], // non-scalar caught first
  ])('rejects a non-numeric marks value %s', (value, expected) => {
    const result = validate([
      {
        op: 'replace',
        path: '/paper/sections/section-a/slots/slot-a1/marks',
        value,
      },
    ]);
    expect(guardIds(result)).toContain(expected);
  });

  it('rejects a numeric value on a text field', () => {
    const result = validate([
      { op: 'replace', path: '/paper/title', value: 5 },
    ]);
    expect(guardIds(result)).toContain('forbidden_value_type');
  });

  it('rejects an oversized proposal', () => {
    const patches = Array.from({ length: MAX_PATCHES + 1 }, () => ({
      op: 'replace',
      path: '/paper/title',
      value: 'x',
    }));
    expect(guardIds(validate(patches))).toContain('proposal_too_large');
  });

  it('rejects a stale base revision', () => {
    const result = validate(
      [{ op: 'replace', path: '/paper/title', value: 'New' }],
      {
        base: REVISION - 1,
      },
    );
    expect(guardIds(result)).toContain('stale_base_revision');
  });
});

describe('validateProposal contract', () => {
  it('carries a user-safe message and path on each blocking entry', () => {
    const result = validate([
      { op: 'replace', path: '/questions/q1/rawText', value: 'x' },
    ]);
    const entry = result.blocking[0];
    expect(entry.path).toBe('/questions/q1/rawText');
    expect(entry.message).toBe(GUARD_MESSAGES.forbidden_question_text);
    expect(entry.message).not.toContain('/');
  });

  it('collapses duplicate guard/path pairs', () => {
    const result = validate([
      { op: 'replace', path: '/questions/q1/rawText', value: 'a' },
      { op: 'replace', path: '/questions/q1/rawText', value: 'b' },
    ]);
    expect(result.blocking).toHaveLength(1);
  });

  it('exposes exactly the pinned guard-id registry', () => {
    expect(new Set(Object.keys(GUARD_MESSAGES))).toEqual(
      new Set([
        'stale_base_revision',
        'proposal_too_large',
        'unsupported_operation',
        'unknown_target',
        'forbidden_question_text',
        'forbidden_question_source',
        'forbidden_question_swap',
        'forbidden_question_count',
        'forbidden_section_membership',
        'forbidden_raw_content',
        'forbidden_value_type',
        'forbidden_path',
      ]),
    );
  });
});
