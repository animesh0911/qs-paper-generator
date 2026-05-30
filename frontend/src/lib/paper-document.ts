/**
 * PaperDocumentV1 validation and normalization helpers.
 *
 * This module is the frontend seam between raw backend JSON and the editor's
 * canonical state maps. API adapters validate here before React stores a paper;
 * editor features consume the normalized shape instead of walking nested
 * contract arrays.
 *
 * Patterns:
 * - `questions[]` remains source content; slot-level edits live in
 *   `slotEditsById`.
 * - Unknown optional contract fields are preserved by the schema and carried in
 *   the original parsed document.
 *
 * Where it fits:
 * - Used by: `src/lib/api.ts`, editor state tests.
 * - Uses: `src/types/paper-document.schema.ts`.
 *
 * @module paperDocument
 */
import type {
  DocQuestion,
  DocSlot,
  PaperDocument,
  PaperFormat,
  SlotOverrides,
} from '@/types';
import { paperDocumentSchema } from '@/types/paper-document.schema';

export interface NormalizedPaperDocument {
  document: PaperDocument;
  questionsById: Record<string, DocQuestion>;
  slotsById: Record<string, DocSlot>;
  sectionOrder: string[];
  slotOrderBySection: Record<string, string[]>;
  slotEditsById: Record<string, SlotOverrides>;
  lockStateBySlotId: Record<string, boolean>;
  formatRules: PaperFormat;
}

export class PaperDocumentContractError extends Error {
  readonly userMessage =
    'The generated paper did not match the editor contract. Please try again.';

  constructor(readonly details: string) {
    super(`Backend returned an unexpected PaperDocument shape: ${details}`);
    this.name = 'PaperDocumentContractError';
  }
}

export function parsePaperDocument(payload: unknown) {
  return paperDocumentSchema.safeParse(payload);
}

export function assertPaperDocument(payload: unknown): PaperDocument {
  const parsed = parsePaperDocument(payload);
  if (!parsed.success) {
    throw new PaperDocumentContractError(parsed.error.message);
  }
  return parsed.data as PaperDocument;
}

export function getPaperDocumentErrorMessage(error: unknown): string {
  if (error instanceof PaperDocumentContractError) {
    return error.userMessage;
  }
  return error instanceof Error ? error.message : 'Something went wrong.';
}

export function normalizePaperDocument(
  document: PaperDocument,
): NormalizedPaperDocument {
  const questionsById = Object.fromEntries(
    document.questions.map((question) => [question.questionId, question]),
  );
  const slotsById: Record<string, DocSlot> = {};
  const slotOrderBySection: Record<string, string[]> = {};
  const slotEditsById: Record<string, SlotOverrides> = {};
  const lockStateBySlotId: Record<string, boolean> = {};

  for (const section of document.paper.sections) {
    slotOrderBySection[section.sectionId] = section.slots.map((slot) => {
      slotsById[slot.slotId] = slot;
      slotEditsById[slot.slotId] = slot.overrides ?? {
        modifiedFromSource: false,
        regions: {},
      };
      lockStateBySlotId[slot.slotId] = slot.locked;
      return slot.slotId;
    });
  }

  return {
    document,
    questionsById,
    slotsById,
    sectionOrder: document.paper.sections.map((section) => section.sectionId),
    slotOrderBySection,
    slotEditsById,
    lockStateBySlotId,
    formatRules: document.format,
  };
}
