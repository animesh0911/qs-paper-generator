/**
 * Deterministic guardrail validator for AI editor proposals (frontend mirror).
 *
 * The backend validates a proposal before storing it, but the teacher's Apply
 * button is only enabled after the frontend *re-runs the same guards* against
 * the live document (PRD #30: "deterministic backend/frontend validation still
 * decides whether Apply is enabled"). This module is that re-validation: it is a
 * line-for-line mirror of `backend/ai_editor/proposals.py` and shares the guard
 * registry in `src/types/ai-proposal.schema.ts`.
 *
 * Patterns:
 * - Deny-by-default: a patch is allowed only when it is a scalar `replace` at an
 *   allowed id-addressed path whose ids resolve in the live document.
 * - Marks edits are allowed but emit a recompute warning rather than trusting any
 *   total the model asserted.
 *
 * Where it fits:
 * - Used by: the assistant proposal preview (enables/disables Apply).
 * - Mirrors: `backend/ai_editor/proposals.py`.
 *
 * @module aiProposal
 */
import type { PaperDocument } from '@/types';
import {
  GUARD_MESSAGES,
  type EditPatch,
  type GuardId,
  type GuardViolation,
  type ProposalValidation,
} from '@/types/ai-proposal.schema';

// A proposal larger than this is refused rather than diffed — an unbounded
// payload is a runaway-cost / denial-of-service vector, not a scoped edit.
export const MAX_PATCHES = 40;
export const MAX_VALUE_CHARS = 20_000;

const ALLOWED_OP = 'replace';

const FORMAT_LAYOUT_ROLES =
  'marks|questionNumbers|mcqOptions|instructions|masthead|footer';

type IdKind = 'chromeBlockId' | 'instructionBlockId' | 'sectionId' | 'slotId';
type ValueKind = 'text' | 'number';

interface AllowedPathPattern {
  pattern: RegExp;
  idKinds: IdKind[];
  valueKind: ValueKind;
}

// Block kinds are collection-specific so a chrome path can't resolve an
// instruction block (or vice versa); `valueKind` keeps a string off a numeric
// field (slot marks) even though both are scalars.
const ALLOWED_PATH_PATTERNS: AllowedPathPattern[] = [
  { pattern: /^\/paper\/title$/, idKinds: [], valueKind: 'text' },
  { pattern: /^\/paper\/subtitle$/, idKinds: [], valueKind: 'text' },
  {
    pattern: /^\/paper\/chromeBlocks\/(?<blockId>[^/]+)\/text$/,
    idKinds: ['chromeBlockId'],
    valueKind: 'text',
  },
  {
    pattern: /^\/paper\/instructionBlocks\/(?<blockId>[^/]+)\/text$/,
    idKinds: ['instructionBlockId'],
    valueKind: 'text',
  },
  {
    pattern: /^\/paper\/sections\/(?<sectionId>[^/]+)\/title$/,
    idKinds: ['sectionId'],
    valueKind: 'text',
  },
  {
    pattern: /^\/paper\/sections\/(?<sectionId>[^/]+)\/subtitle$/,
    idKinds: ['sectionId'],
    valueKind: 'text',
  },
  {
    pattern: /^\/paper\/sections\/(?<sectionId>[^/]+)\/instructions$/,
    idKinds: ['sectionId'],
    valueKind: 'text',
  },
  {
    pattern:
      /^\/paper\/sections\/(?<sectionId>[^/]+)\/slots\/(?<slotId>[^/]+)\/marks$/,
    idKinds: ['sectionId', 'slotId'],
    valueKind: 'number',
  },
  {
    pattern: /^\/format\/page\/(?:size|orientation)$/,
    idKinds: [],
    valueKind: 'text',
  },
  {
    pattern: new RegExp(`^/format/layout/(?:${FORMAT_LAYOUT_ROLES})$`),
    idKinds: [],
    valueKind: 'text',
  },
];

const BLOCK_COLLECTION: Record<string, string> = {
  chromeBlockId: 'chromeBlocks',
  instructionBlockId: 'instructionBlocks',
};

const MARKS_PATH =
  /^\/paper\/sections\/(?<sectionId>[^/]+)\/slots\/(?<slotId>[^/]+)\/marks$/;

function segments(path: string): string[] {
  if (!path.startsWith('/')) return [path];
  return path
    .slice(1)
    .split('/')
    .map((seg) => seg.replace(/~1/g, '/').replace(/~0/g, '~'));
}

function isScalar(value: unknown): boolean {
  return (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  );
}

// `number` rejects boolean (a `true` marks value is a type confusion, not a
// quantity); `text` requires a string so a bare number can't land on a label.
function valueMatchesKind(value: unknown, valueKind: ValueKind): boolean {
  if (valueKind === 'number') return typeof value === 'number';
  return typeof value === 'string';
}

function findById(
  items: unknown,
  targetId: string,
): Record<string, unknown> | undefined {
  if (!Array.isArray(items)) return undefined;
  return items.find(
    (item): item is Record<string, unknown> =>
      typeof item === 'object' &&
      item !== null &&
      (item as Record<string, unknown>).id === targetId,
  );
}

function targetExists(
  document: PaperDocument,
  kind: IdKind,
  captured: Record<string, string>,
): boolean {
  const paper = document.paper as unknown as Record<string, unknown>;
  if (kind in BLOCK_COLLECTION) {
    return (
      findById(paper[BLOCK_COLLECTION[kind]], captured.blockId) !== undefined
    );
  }
  const section = findById(paper.sections, captured.sectionId);
  if (section === undefined) return false;
  if (kind === 'sectionId') return true;
  return findById(section.slots, captured.slotId) !== undefined;
}

function forbiddenGuard(path: string): GuardId {
  const segs = segments(path);
  if (segs[0] === 'questions') {
    if (segs.includes('source') || segs.includes('metadata')) {
      return 'forbidden_question_source';
    }
    return 'forbidden_question_text';
  }
  if (segs[0] === 'paper' && segs.includes('sections')) {
    const last = segs[segs.length - 1];
    if (last === 'selectedQuestionId' || last === 'alternateQuestionIds') {
      return 'forbidden_question_swap';
    }
    if (
      last === 'slots' ||
      (segs.length >= 5 && segs[segs.length - 2] === 'slots')
    ) {
      return 'forbidden_question_count';
    }
    if (
      last === 'sections' ||
      (segs.length === 3 && segs[segs.length - 2] === 'sections')
    ) {
      return 'forbidden_section_membership';
    }
  }
  return 'forbidden_path';
}

function classifyPatch(
  document: PaperDocument,
  patch: EditPatch,
): GuardId | null {
  if (patch.op !== ALLOWED_OP) return 'unsupported_operation';

  for (const { pattern, idKinds, valueKind } of ALLOWED_PATH_PATTERNS) {
    const match = pattern.exec(patch.path);
    if (match === null) continue;
    const captured = (match.groups ?? {}) as Record<string, string>;
    for (const kind of idKinds) {
      if (!targetExists(document, kind, captured)) return 'unknown_target';
    }
    if (!isScalar(patch.value)) return 'forbidden_raw_content';
    if (!valueMatchesKind(patch.value, valueKind)) {
      return 'forbidden_value_type';
    }
    return null;
  }
  return forbiddenGuard(patch.path);
}

function marksWarnings(
  document: PaperDocument,
  patches: EditPatch[],
): string[] {
  const slotMarks = new Map<string, number>();
  for (const section of document.paper.sections) {
    for (const slot of section.slots) {
      slotMarks.set(slot.id, slot.marks ?? 0);
    }
  }

  const oldTotal = [...slotMarks.values()].reduce((sum, m) => sum + m, 0);
  const newMarks = new Map(slotMarks);
  let touched = false;
  for (const patch of patches) {
    const match = MARKS_PATH.exec(patch.path);
    if (match === null || typeof patch.value !== 'number') continue;
    const slotId = match.groups?.slotId;
    if (slotId !== undefined && newMarks.has(slotId)) {
      newMarks.set(slotId, patch.value);
      touched = true;
    }
  }

  const newTotal = [...newMarks.values()].reduce((sum, m) => sum + m, 0);
  if (touched && newTotal !== oldTotal) {
    return [`Total marks changed from ${oldTotal} to ${newTotal}.`];
  }
  return [];
}

export interface ValidateProposalArgs {
  baseRevision: number;
  currentRevision: number;
}

/**
 * Run the deterministic guardrails over a proposal's patches against the live
 * document. A non-empty `blocking` list means Apply must stay disabled.
 */
export function validateProposal(
  document: PaperDocument,
  patches: EditPatch[],
  { baseRevision, currentRevision }: ValidateProposalArgs,
): ProposalValidation {
  const blocking: GuardViolation[] = [];
  const seen = new Set<string>();

  const add = (guardId: GuardId, path?: string) => {
    const key = `${guardId}::${path ?? ''}`;
    if (seen.has(key)) return;
    seen.add(key);
    blocking.push({
      guardId,
      message: GUARD_MESSAGES[guardId],
      ...(path !== undefined ? { path } : {}),
    });
  };

  if (baseRevision !== currentRevision) add('stale_base_revision');

  const totalValueChars = patches.reduce(
    (sum, patch) =>
      sum + (patch.value === undefined ? 0 : String(patch.value).length),
    0,
  );
  if (patches.length > MAX_PATCHES || totalValueChars > MAX_VALUE_CHARS) {
    add('proposal_too_large');
  }

  for (const patch of patches) {
    const guardId = classifyPatch(document, patch);
    if (guardId !== null) add(guardId, patch.path);
  }

  // Warnings only describe an otherwise-valid proposal; a blocked proposal will
  // not apply, so recompute noise would mislead.
  const warnings = blocking.length > 0 ? [] : marksWarnings(document, patches);
  return { blocking, warnings };
}
