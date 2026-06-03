/**
 * Tests for PaperDocumentV1 validation and normalized editor state helpers.
 *
 * These tests pin the API-boundary contract checks and the state transitions
 * used by editor actions so source questions stay immutable.
 *
 * @module paperDocumentTests
 */
import { describe, expect, it } from 'vitest';
import { mockPaperDocumentV1 } from '@/mocks';
import {
  assertPaperDocument,
  getPaperDocumentErrorMessage,
  normalizePaperDocument,
  PaperDocumentContractError,
  parsePaperDocument,
  restoreSlotSource,
  setPaperChromeText,
  setSlotLockState,
  setSlotSelectedQuestion,
  setSlotRegionOverride,
  buildOrderZones,
  commitStructuredPaperAction,
  reorderSlotWithinOrderZone,
  renumberPaperSlots,
  undoStructuredPaperAction,
} from './paper-document';

describe('PaperDocumentV1 validation', () => {
  it('rejects slot question references that are missing or incompatible', () => {
    const invalidDocument = structuredClone(mockPaperDocumentV1);
    const firstSlot = invalidDocument.paper.sections[0].slots[0];
    firstSlot.selectedQuestionId = 'q_missing';
    firstSlot.alternateQuestionIds = [invalidDocument.questions[0].id];
    invalidDocument.questions[0].defaultMarks = firstSlot.marks + 1;

    const result = parsePaperDocument(invalidDocument);

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((issue) => issue.message)).toEqual(
        expect.arrayContaining([
          'selectedQuestionId must reference a question in questions[]',
          'referenced questions must match slot marks, type, and paper language',
        ]),
      );
    }
  });

  it('keeps contract details loud for developers while exposing a user-safe message', () => {
    expect(() => assertPaperDocument({ schemaVersion: 'wrong.v1' })).toThrow(
      PaperDocumentContractError,
    );

    try {
      assertPaperDocument({ schemaVersion: 'wrong.v1' });
    } catch (error) {
      expect((error as Error).message).toContain(
        'Backend returned an unexpected PaperDocument shape',
      );
      expect(getPaperDocumentErrorMessage(error)).toBe(
        'The generated paper did not match the editor contract. Please try again.',
      );
    }
  });

  it('preserves unknown optional fields on parsed contract objects', () => {
    const documentWithOptionalFields = structuredClone(mockPaperDocumentV1);
    const slot = documentWithOptionalFields.paper.sections[0].slots[0];

    Object.assign(documentWithOptionalFields, {
      capabilities: { canSaveDraft: true },
    });
    Object.assign(slot, {
      editorHints: { emphasis: 'normal' },
    });

    const parsed = parsePaperDocument(documentWithOptionalFields);

    expect(parsed.success).toBe(true);
    if (!parsed.success) return;
    expect(parsed.data.capabilities).toEqual({ canSaveDraft: true });
    expect(parsed.data.paper.sections[0].slots[0].editorHints).toEqual({
      emphasis: 'normal',
    });
  });
});

describe('PaperDocumentV1 normalization', () => {
  it('normalizes the document into editor state maps without mutating source questions', () => {
    const parsed = parsePaperDocument(mockPaperDocumentV1);
    expect(parsed.success).toBe(true);
    if (!parsed.success) return;

    const state = normalizePaperDocument(parsed.data);
    const firstSection = parsed.data.paper.sections[0];
    const firstSlot = firstSection.slots[0];

    expect(state.questionsById[firstSlot.selectedQuestionId ?? '']).toBe(
      parsed.data.questions.find(
        (question) => question.id === firstSlot.selectedQuestionId,
      ),
    );
    expect(state.slotsById[firstSlot.id]).toEqual(firstSlot);
    expect(state.sectionOrder).toEqual(
      parsed.data.paper.sections.map((section) => section.id),
    );
    expect(state.slotOrderBySection[firstSection.id]).toEqual(
      firstSection.slots.map((slot) => slot.id),
    );
    expect(state.slotEditsById[firstSlot.id]).toEqual(
      firstSlot.overrides ?? { modified: false, regions: {} },
    );
    expect(state.lockStateBySlotId[firstSlot.id]).toBe(firstSlot.locked);
    expect(state.formatRules).toBe(parsed.data.format);
  });

  it('stores and restores manual edits as slot-level region overrides', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);
    const editedState = setSlotRegionOverride(state, 'slot_A_01', 'stem', [
      {
        type: 'paragraph',
        text: 'Paper-specific stem text.',
      },
    ]);

    expect(editedState.slotEditsById.slot_A_01).toEqual({
      modified: true,
      regions: {
        stem: [{ type: 'paragraph', text: 'Paper-specific stem text.' }],
      },
    });
    expect(
      editedState.document.paper.sections[0].slots[0].overrides,
    ).toEqual({
      modified: true,
      regions: {
        stem: [{ type: 'paragraph', text: 'Paper-specific stem text.' }],
      },
    });
    expect(editedState.questionsById.q_mcq_heredity_001).toBe(
      state.questionsById.q_mcq_heredity_001,
    );

    const restoredState = restoreSlotSource(editedState, 'slot_A_01');

    expect(restoredState.slotEditsById.slot_A_01).toEqual({
      modified: false,
      regions: {},
    });
    expect(restoredState.questionsById.q_mcq_heredity_001.rawText).toBe(
      state.questionsById.q_mcq_heredity_001.rawText,
    );
  });

  it('updates editable paper chrome without changing source questions', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);
    const editedState = setPaperChromeText(
      state,
      'section:A:instructions',
      'Edited Biology section directions.',
    );

    expect(editedState.document.paper.sections[0].instructions).toBe(
      'Edited Biology section directions.',
    );
    expect(editedState.questionsById.q_mcq_heredity_001).toBe(
      state.questionsById.q_mcq_heredity_001,
    );
  });

  it('updates slot lock state in normalized maps and the canonical document', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);
    const lockedState = setSlotLockState(state, 'slot_A_01', true);

    expect(lockedState.lockStateBySlotId.slot_A_01).toBe(true);
    expect(lockedState.slotsById.slot_A_01.locked).toBe(true);
    expect(lockedState.document.paper.sections[0].slots[0].locked).toBe(true);
    expect(lockedState.questionsById.q_mcq_heredity_001).toBe(
      state.questionsById.q_mcq_heredity_001,
    );
  });

  it('replaces a slot selected question without changing slot placement or source questions', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);
    const editedState = setSlotRegionOverride(state, 'slot_A_01', 'stem', [
      {
        type: 'paragraph',
        text: 'Manual edit that belongs only to this Slot.',
      },
    ]);

    const replacedState = setSlotSelectedQuestion(
      editedState,
      'slot_A_01',
      'q_mcq_heredity_002',
    );
    const replacedSlot = replacedState.slotsById.slot_A_01;
    const canonicalSlot = replacedState.document.paper.sections[0].slots[0];

    expect(replacedSlot).toEqual({
      ...state.slotsById.slot_A_01,
      selectedQuestionId: 'q_mcq_heredity_002',
      alternateQuestionIds: [
        'q_mcq_heredity_001',
        'q_mcq_electricity_001',
        'q_mcq_chemotropism_001',
        'q_mcq_spirogyra_001',
        'q_mcq_photosynthesis_001',
      ],
      overrides: {
        modified: false,
        regions: {},
      },
    });
    expect(canonicalSlot).toEqual(replacedSlot);
    expect(replacedState.slotEditsById.slot_A_01).toEqual({
      modified: false,
      regions: {},
    });
    expect(replacedState.questionsById).toBe(editedState.questionsById);
    expect(replacedState.questionsById.q_mcq_heredity_001.rawText).toBe(
      state.questionsById.q_mcq_heredity_001.rawText,
    );
  });

  it('keeps the previous selected Question available after a Slot swap', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);

    const replacedState = setSlotSelectedQuestion(
      state,
      'slot_E_02',
      'q_table_metals_002',
    );
    const replacedSlot = replacedState.slotsById.slot_E_02;
    const canonicalSlot = replacedState.document.paper.sections[1].slots[0];

    expect(state.slotsById.slot_E_02.alternateQuestionIds).toEqual([
      'q_table_metals_002',
    ]);
    expect(replacedSlot.selectedQuestionId).toBe('q_table_metals_002');
    expect(replacedSlot.alternateQuestionIds).toEqual(['q_table_metals_001']);
    expect(canonicalSlot.alternateQuestionIds).toEqual([
      'q_table_metals_001',
    ]);
  });

  it('cycles swapped Questions without duplicating alternative ids', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);

    const firstSwap = setSlotSelectedQuestion(
      state,
      'slot_E_02',
      'q_table_metals_002',
    );
    const secondSwap = setSlotSelectedQuestion(
      firstSwap,
      'slot_E_02',
      'q_table_metals_001',
    );

    expect(secondSwap.slotsById.slot_E_02.selectedQuestionId).toBe(
      'q_table_metals_001',
    );
    expect(secondSwap.slotsById.slot_E_02.alternateQuestionIds).toEqual([
      'q_table_metals_002',
    ]);
  });

  it('ignores selected Question changes for missing Slots', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);

    const nextState = setSlotSelectedQuestion(
      state,
      'slot_missing',
      'q_table_metals_002',
    );

    expect(nextState).toBe(state);
  });
});

describe('PaperDocumentV1 ordering', () => {
  it('derives same-zone-only Slot ordering zones from the current document structure', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const zones = buildOrderZones(document);

    expect(zones[0]).toEqual({
      zoneId: 'section:A',
      label: 'Section A',
      itemKind: 'slot',
      orderedItemIds: [
        'slot_A_01',
        'slot_A_02',
        'slot_B_01',
        'slot_C_01',
        'slot_D_01',
      ],
      reorder: {
        enabled: true,
        allowedTargetZoneIds: ['section:A'],
      },
    });
    expect(zones.map((zone) => zone.zoneId)).toEqual([
      'section:A',
      'section:B',
      'section:C',
    ]);
  });

  it('renumbers slots continuously across sections', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const renumbered = renumberPaperSlots(document);
    let expectedIndex = 1;
    for (const section of renumbered.paper.sections) {
      for (const slot of section.slots) {
        expect(slot.number).toBe(String(expectedIndex));
        expectedIndex += 1;
      }
    }
  });

  it('reorders slots within the same order zone and updates display numbers', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);

    const result = reorderSlotWithinOrderZone(state, {
      slotId: 'slot_A_01',
      fromZoneId: 'section:A',
      toZoneId: 'section:A',
      toIndex: 1,
    });

    expect(result.success).toBe(true);
    if (!result.success) return;

    const nextState = result.state;

    expect(nextState.slotOrderBySection.A.slice(0, 2)).toEqual([
      'slot_A_02',
      'slot_A_01',
    ]);
    expect(nextState.document.paper.sections[0].slots[0]).toMatchObject({
      id: 'slot_A_02',
      number: '1',
    });
    expect(nextState.document.paper.sections[0].slots[1]).toMatchObject({
      id: 'slot_A_01',
      number: '2',
    });
  });

  it('rejects moves into a different order zone', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);

    const result = reorderSlotWithinOrderZone(state, {
      slotId: 'slot_A_01',
      fromZoneId: 'section:A',
      toZoneId: 'section:B',
      toIndex: 0,
    });

    expect(result.success).toBe(false);
    expect(result.state).toBe(state);
    if (result.success) return;
    expect(result.error).toContain('not allowed');
  });

  it('keeps one app-level undo entry for the latest structured paper action', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const initialState = normalizePaperDocument(document);
    const lockedState = setSlotLockState(initialState, 'slot_A_01', true);
    const firstCommit = commitStructuredPaperAction(initialState, lockedState);
    const reordered = reorderSlotWithinOrderZone(firstCommit.state, {
      slotId: 'slot_A_01',
      fromZoneId: 'section:A',
      toZoneId: 'section:A',
      toIndex: 1,
    });
    expect(reordered.success).toBe(true);
    if (!reordered.success) return;

    const secondCommit = commitStructuredPaperAction(
      firstCommit.state,
      reordered.state,
    );
    const undone = undoStructuredPaperAction(
      secondCommit.state,
      secondCommit.undoEntry,
    );

    expect(undone.state).toBe(firstCommit.state);
    expect(undone.undoEntry).toBeNull();
    expect(undone.state.lockStateBySlotId.slot_A_01).toBe(true);
    expect(undone.state.slotOrderBySection.A.slice(0, 2)).toEqual([
      'slot_A_01',
      'slot_A_02',
    ]);
  });

  it('undoes manual slot region edits committed as structured actions', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const initialState = normalizePaperDocument(document);
    const editedState = setSlotRegionOverride(initialState, 'slot_A_01', 'stem', [
      {
        type: 'paragraph',
        text: 'Manual question text that should be undoable.',
      },
    ]);

    const committed = commitStructuredPaperAction(initialState, editedState);
    const undone = undoStructuredPaperAction(
      committed.state,
      committed.undoEntry,
    );

    expect(committed.state.slotEditsById.slot_A_01).toMatchObject({
      modified: true,
    });
    expect(undone.state).toBe(initialState);
    expect(undone.undoEntry).toBeNull();
    expect(undone.state.slotEditsById.slot_A_01).toEqual({
      modified: false,
      regions: {},
    });
  });

  it('undoes manual paper chrome edits committed as structured actions', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const initialState = normalizePaperDocument(document);
    const editedState = setPaperChromeText(
      initialState,
      'paper:title',
      'Edited Science Title',
    );

    const committed = commitStructuredPaperAction(initialState, editedState);
    const undone = undoStructuredPaperAction(
      committed.state,
      committed.undoEntry,
    );

    expect(committed.state.document.paper.title).toBe('Edited Science Title');
    expect(undone.state).toBe(initialState);
    expect(undone.undoEntry).toBeNull();
    expect(undone.state.document.paper.title).toBe('Science');
  });
});
