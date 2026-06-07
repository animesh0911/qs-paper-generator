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
 *   `slotStateById`.
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
  ContentItem,
  EditableTextBlock,
  DocQuestion,
  DocSlot,
  DocSection,
  PaperDocument,
  PaperFormat,
  SlotOverrides,
} from '@/types';
import { paperDocumentSchema } from '@/types/paper-document.schema';

export interface NormalizedPaperDocument {
  document: PaperDocument;
  sectionOrder: string[];
  slotOrderBySection: Record<string, string[]>;
  formatRules: PaperFormat;
  index: {
    questionsById: Record<string, DocQuestion>;
    slotsById: Record<string, DocSlot>;
  };
  slotStateById: Record<
    string,
    {
      locked: boolean;
      overrides: SlotOverrides;
    }
  >;
}

export interface PaperOrderZone {
  zoneId: string;
  label: string;
  itemKind: 'slot';
  orderedItemIds: string[];
  reorder: {
    enabled: boolean;
    allowedTargetZoneIds: string[];
  };
}

export interface SlotOrderZoneReorderParams {
  slotId: string;
  fromZoneId: string;
  toZoneId: string;
  toIndex: number;
}

export type SlotOrderZoneReorderResult =
  | { success: true; state: NormalizedPaperDocument }
  | { success: false; state: NormalizedPaperDocument; error: string };

export interface StructuredPaperUndoEntry {
  previousState: NormalizedPaperDocument;
}

export interface StructuredPaperActionState {
  state: NormalizedPaperDocument;
  undoEntry: StructuredPaperUndoEntry | null;
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
    document.questions.map((question) => [question.id, question]),
  );
  const slotsById: Record<string, DocSlot> = {};
  const slotOrderBySection: Record<string, string[]> = {};
  const slotEditsById: Record<string, SlotOverrides> = {};
  const lockStateBySlotId: Record<string, boolean> = {};

  for (const section of document.paper.sections) {
    slotOrderBySection[section.id] = section.slots.map((slot) => {
      slotsById[slot.id] = slot;
      slotEditsById[slot.id] = slot.overrides ?? {
        modified: false,
        regions: {},
      };
      lockStateBySlotId[slot.id] = slot.locked;
      return slot.id;
    });
  }

  return {
    document,
    sectionOrder: document.paper.sections.map((section) => section.id),
    slotOrderBySection,
    formatRules: document.format,
    index: {
      questionsById,
      slotsById,
    },
    slotStateById: Object.fromEntries(
      Object.keys(slotsById).map((slotId) => [
        slotId,
        {
          locked: lockStateBySlotId[slotId],
          overrides: slotEditsById[slotId],
        },
      ]),
    ),
  };
}

export function getQuestion(
  state: NormalizedPaperDocument,
  questionId: string,
): DocQuestion | undefined {
  return state.index.questionsById[questionId];
}

export function getSlot(
  state: NormalizedPaperDocument,
  slotId: string,
): DocSlot | undefined {
  const slot = state.index.slotsById[slotId];
  return slot ? slotWithCurrentState(state, slotId) : undefined;
}

export function getSlotOverrides(
  state: NormalizedPaperDocument,
  slotId: string,
): SlotOverrides | undefined {
  return state.slotStateById[slotId]?.overrides;
}

export function getSlotOverridesById(
  state: NormalizedPaperDocument,
): Record<string, SlotOverrides> {
  return Object.fromEntries(
    Object.entries(state.slotStateById).map(([slotId, slotState]) => [
      slotId,
      slotState.overrides,
    ]),
  );
}

export function getSlotLockState(
  state: NormalizedPaperDocument,
  slotId: string,
): boolean | undefined {
  return state.slotStateById[slotId]?.locked;
}

export function canEditSlotText(
  state: NormalizedPaperDocument,
  slotId: string,
): boolean {
  return getSlot(state, slotId)?.can?.editText ?? true;
}

export function canSwapSlot(
  state: NormalizedPaperDocument,
  slotId: string,
): boolean {
  return getSlot(state, slotId)?.can?.swap ?? true;
}

export function canLockSlot(
  state: NormalizedPaperDocument,
  slotId: string,
): boolean {
  return getSlot(state, slotId)?.can?.lock ?? true;
}

export function canReorderSlot(
  state: NormalizedPaperDocument,
  slotId: string,
): boolean {
  return getSlot(state, slotId)?.can?.reorder ?? true;
}

export function setSlotRegionOverride(
  state: NormalizedPaperDocument,
  slotId: string,
  regionKey: string,
  content: ContentItem[],
): NormalizedPaperDocument {
  const slot = getSlot(state, slotId);
  if (!slot || !canEditSlotText(state, slotId)) return state;

  const currentEdits = getSlotOverrides(state, slotId) ?? {
    modified: false,
    regions: {},
  };
  const nextOverrides = {
    modified: true,
    regions: {
      ...currentEdits.regions,
      [regionKey]: content,
    },
  };

  return updatePaperSlot(state, slotId, { overrides: nextOverrides });
}

export function restoreSlotSource(
  state: NormalizedPaperDocument,
  slotId: string,
): NormalizedPaperDocument {
  if (!getSlot(state, slotId)) return state;

  return updatePaperSlot(state, slotId, {
    overrides: {
      modified: false,
      regions: {},
    },
  });
}

export function setSlotLockState(
  state: NormalizedPaperDocument,
  slotId: string,
  locked: boolean,
): NormalizedPaperDocument {
  if (!canLockSlot(state, slotId)) return state;

  return updatePaperSlot(state, slotId, { locked });
}

export function setSlotSelectedQuestion(
  state: NormalizedPaperDocument,
  slotId: string,
  selectedQuestionId: string,
): NormalizedPaperDocument {
  const currentSlot = getSlot(state, slotId);
  if (!currentSlot) return state;
  if (!canSwapSlot(state, slotId)) return state;

  const alternateQuestionIds = rotateSlotAlternativeQuestionIds(
    currentSlot,
    selectedQuestionId,
  );
  const resetOverrides: SlotOverrides = {
    modified: false,
    regions: {},
  };

  return updatePaperSlot(state, slotId, {
    selectedQuestionId,
    alternateQuestionIds,
    overrides: resetOverrides,
  });
}

function rotateSlotAlternativeQuestionIds(
  slot: DocSlot,
  nextSelectedQuestionId: string,
) {
  const previousSelectedQuestionId = slot.selectedQuestionId;
  const nextAlternateQuestionIds = slot.alternateQuestionIds.filter(
    (questionId) => questionId !== nextSelectedQuestionId,
  );

  if (
    previousSelectedQuestionId &&
    previousSelectedQuestionId !== nextSelectedQuestionId &&
    !nextAlternateQuestionIds.includes(previousSelectedQuestionId)
  ) {
    nextAlternateQuestionIds.unshift(previousSelectedQuestionId);
  }

  return nextAlternateQuestionIds;
}

export function setPaperChromeText(
  state: NormalizedPaperDocument,
  regionKey: string,
  text: string,
): NormalizedPaperDocument {
  if (!canEditPaperChromeRegion(state.document, regionKey)) return state;

  return {
    ...state,
    document: {
      ...state.document,
      paper: {
        ...state.document.paper,
        title: regionKey === 'paper:title' ? text : state.document.paper.title,
        subtitle:
          regionKey === 'paper:subtitle' ? text : state.document.paper.subtitle,
        chromeBlocks: updateEditableTextBlocks(
          state.document.paper.chromeBlocks,
          'chrome',
          regionKey,
          text,
        ),
        instructionBlocks: updateEditableTextBlocks(
          state.document.paper.instructionBlocks,
          'instruction',
          regionKey,
          text,
        ),
        sections: state.document.paper.sections.map((section) =>
          updateSectionChromeText(section, regionKey, text),
        ),
      },
    },
  };
}

export function removePaperChromeBlock(
  state: NormalizedPaperDocument,
  regionKey: string,
): NormalizedPaperDocument {
  const parsedRegion = parsePaperTextBlockRegion(regionKey);
  if (!parsedRegion) return state;

  const blocks =
    parsedRegion.kind === 'chrome'
      ? state.document.paper.chromeBlocks
      : state.document.paper.instructionBlocks;
  const block = blocks?.find((candidate) => candidate.id === parsedRegion.id);

  if (!block || (block.can?.delete ?? false) === false) return state;

  return {
    ...state,
    document: {
      ...state.document,
      paper: {
        ...state.document.paper,
        chromeBlocks:
          parsedRegion.kind === 'chrome'
            ? removeEditableTextBlock(
                state.document.paper.chromeBlocks,
                block.id,
              )
            : state.document.paper.chromeBlocks,
        instructionBlocks:
          parsedRegion.kind === 'instruction'
            ? removeEditableTextBlock(
                state.document.paper.instructionBlocks,
                block.id,
              )
            : state.document.paper.instructionBlocks,
      },
    },
  };
}

function canEditPaperChromeRegion(document: PaperDocument, regionKey: string) {
  const parsedRegion = parsePaperTextBlockRegion(regionKey);
  if (!parsedRegion) return true;

  const blocks =
    parsedRegion.kind === 'chrome'
      ? document.paper.chromeBlocks
      : document.paper.instructionBlocks;
  const block = blocks?.find((candidate) => candidate.id === parsedRegion.id);

  return block?.can?.editText ?? true;
}

function parsePaperTextBlockRegion(regionKey: string):
  | {
      kind: 'chrome' | 'instruction';
      id: string;
    }
  | undefined {
  if (regionKey.startsWith('chrome:')) {
    return { kind: 'chrome', id: regionKey.slice('chrome:'.length) };
  }
  if (regionKey.startsWith('instruction:')) {
    return {
      kind: 'instruction',
      id: regionKey.slice('instruction:'.length),
    };
  }
  return undefined;
}

function removeEditableTextBlock(
  blocks: EditableTextBlock[] | undefined,
  blockId: string,
) {
  return blocks?.filter((block) => block.id !== blockId);
}

function updateEditableTextBlocks(
  blocks: EditableTextBlock[] | undefined,
  prefix: string,
  regionKey: string,
  text: string,
) {
  return blocks?.map((block) =>
    regionKey === `${prefix}:${block.id}` ? { ...block, text } : block,
  );
}

function updateSectionChromeText(
  section: DocSection,
  regionKey: string,
  text: string,
): DocSection {
  if (regionKey === `section:${section.id}:title`) {
    return { ...section, title: text };
  }
  if (regionKey === `section:${section.id}:subtitle`) {
    return { ...section, subtitle: text };
  }
  if (regionKey === `section:${section.id}:instructions`) {
    return { ...section, instructions: text };
  }
  return section;
}

export function renumberPaperSlots(document: PaperDocument): PaperDocument {
  let index = 1;
  return {
    ...document,
    paper: {
      ...document.paper,
      sections: document.paper.sections.map((section) => ({
        ...section,
        slots: section.slots.map((slot) => {
          const nextSlot = {
            ...slot,
            number: String(index),
          };
          index += 1;
          return nextSlot;
        }),
      })),
    },
  };
}

export function materializePaperDocument(
  state: NormalizedPaperDocument,
): PaperDocument {
  return {
    ...state.document,
    paper: {
      ...state.document.paper,
      sections: state.document.paper.sections.map((section) => ({
        ...section,
        slots: section.slots.map((slot) =>
          slotWithCurrentState(state, slot.id),
        ),
      })),
    },
  };
}

export function buildOrderZones(
  input: PaperDocument | NormalizedPaperDocument,
): PaperOrderZone[] {
  const document = isNormalizedPaperDocument(input) ? input.document : input;

  return document.paper.sections.map((section) => ({
    zoneId: `section:${section.id}`,
    label: section.title,
    itemKind: 'slot',
    orderedItemIds: section.slots.map((slot) => slot.id),
    reorder: {
      enabled: true,
      allowedTargetZoneIds: [`section:${section.id}`],
    },
  }));
}

function isNormalizedPaperDocument(
  input: PaperDocument | NormalizedPaperDocument,
): input is NormalizedPaperDocument {
  return (
    typeof input === 'object' &&
    input !== null &&
    'index' in input &&
    'slotStateById' in input
  );
}

export function reorderSlotWithinOrderZone(
  state: NormalizedPaperDocument,
  params: SlotOrderZoneReorderParams,
): SlotOrderZoneReorderResult {
  const zones = buildOrderZones(state);
  const sourceZone = zones.find((zone) =>
    zone.orderedItemIds.includes(params.slotId),
  );

  if (!sourceZone) {
    return { success: false, state, error: 'Slot not found in any order zone' };
  }
  if (sourceZone.zoneId !== params.fromZoneId) {
    return {
      success: false,
      state,
      error: `Slot belongs to ${sourceZone.zoneId}, not ${params.fromZoneId}`,
    };
  }

  const targetZone = zones.find((zone) => zone.zoneId === params.toZoneId);
  if (!targetZone) {
    return { success: false, state, error: 'Target order zone not found' };
  }
  if (!sourceZone.reorder.enabled) {
    return {
      success: false,
      state,
      error: 'Reorder is disabled for this zone',
    };
  }
  if (!canReorderSlot(state, params.slotId)) {
    return {
      success: false,
      state,
      error: 'Reorder is disabled for this slot',
    };
  }
  if (!sourceZone.reorder.allowedTargetZoneIds.includes(targetZone.zoneId)) {
    return {
      success: false,
      state,
      error: `Move from ${sourceZone.zoneId} to ${targetZone.zoneId} is not allowed`,
    };
  }
  if (
    params.toIndex < 0 ||
    params.toIndex >= targetZone.orderedItemIds.length
  ) {
    return { success: false, state, error: 'Target index is outside the zone' };
  }

  const reorderedItemIds = [...sourceZone.orderedItemIds];
  const fromIndex = reorderedItemIds.indexOf(params.slotId);
  if (fromIndex === -1) {
    return { success: false, state, error: 'Slot not found in source zone' };
  }
  if (fromIndex === params.toIndex) {
    return { success: true, state };
  }

  reorderedItemIds.splice(fromIndex, 1);
  reorderedItemIds.splice(params.toIndex, 0, params.slotId);

  const nextSections = state.document.paper.sections.map((section) => {
    if (`section:${section.id}` === sourceZone.zoneId) {
      return {
        ...section,
        slots: reorderedItemIds.map((slotId) =>
          slotWithCurrentState(state, slotId),
        ),
      };
    }
    return {
      ...section,
      slots: section.slots.map((slot) => slotWithCurrentState(state, slot.id)),
    };
  });

  let nextDocument: PaperDocument = {
    ...state.document,
    paper: {
      ...state.document.paper,
      sections: nextSections,
    },
  };

  nextDocument = renumberPaperSlots(nextDocument);
  const nextState = normalizePaperDocument(nextDocument);

  return { success: true, state: nextState };
}

export function commitStructuredPaperAction(
  currentState: NormalizedPaperDocument,
  nextState: NormalizedPaperDocument,
): StructuredPaperActionState {
  return {
    state: nextState,
    undoEntry: {
      previousState: currentState,
    },
  };
}

export function undoStructuredPaperAction(
  currentState: NormalizedPaperDocument,
  undoEntry: StructuredPaperUndoEntry | null,
): StructuredPaperActionState {
  if (!undoEntry) {
    return {
      state: currentState,
      undoEntry: null,
    };
  }

  return {
    state: undoEntry.previousState,
    undoEntry: null,
  };
}

function slotWithCurrentState(
  state: NormalizedPaperDocument,
  slotId: string,
): DocSlot {
  const slot = state.index.slotsById[slotId];

  return {
    ...slot,
    locked: state.slotStateById[slotId]?.locked ?? slot.locked,
    overrides: state.slotStateById[slotId]?.overrides ?? slot.overrides,
  };
}

function updatePaperSlot(
  state: NormalizedPaperDocument,
  slotId: string,
  patch: Partial<DocSlot>,
): NormalizedPaperDocument {
  const currentSlot = getSlot(state, slotId);
  if (!currentSlot) return state;

  const nextSlot: DocSlot = {
    ...currentSlot,
    ...patch,
  };

  return {
    ...state,
    slotStateById: {
      ...state.slotStateById,
      [slotId]: {
        locked:
          patch.locked ??
          state.slotStateById[slotId]?.locked ??
          nextSlot.locked,
        overrides: patch.overrides ??
          state.slotStateById[slotId]?.overrides ??
          nextSlot.overrides ?? {
            modified: false,
            regions: {},
          },
      },
    },
    index: {
      ...state.index,
      slotsById: {
        ...state.index.slotsById,
        [slotId]: nextSlot,
      },
    },
    document: {
      ...state.document,
      paper: {
        ...state.document.paper,
        sections: state.document.paper.sections.map((section) => ({
          ...section,
          slots: section.slots.map((slot) =>
            slot.id === slotId ? nextSlot : slot,
          ),
        })),
      },
    },
  };
}
