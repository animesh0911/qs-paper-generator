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
  setSlotRegionOverride,
} from './paper-document';

describe('PaperDocumentV1 validation', () => {
  it('rejects slot question references that are missing or incompatible', () => {
    const invalidDocument = structuredClone(mockPaperDocumentV1);
    const firstSlot = invalidDocument.paper.sections[0].slots[0];
    firstSlot.selectedQuestionId = 'q_missing';
    firstSlot.alternateQuestionIds = [invalidDocument.questions[0].questionId];
    invalidDocument.questions[0].marks = firstSlot.marks + 1;

    const result = parsePaperDocument(invalidDocument);

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((issue) => issue.message)).toEqual(
        expect.arrayContaining([
          'selectedQuestionId must reference a question in questions[]',
          'referenced questions must match slot marks, questionType, and paper language',
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
        (question) => question.questionId === firstSlot.selectedQuestionId,
      ),
    );
    expect(state.slotsById[firstSlot.slotId]).toEqual(firstSlot);
    expect(state.sectionOrder).toEqual(
      parsed.data.paper.sections.map((section) => section.sectionId),
    );
    expect(state.slotOrderBySection[firstSection.sectionId]).toEqual(
      firstSection.slots.map((slot) => slot.slotId),
    );
    expect(state.slotEditsById[firstSlot.slotId]).toEqual(
      firstSlot.overrides ?? { modifiedFromSource: false, regions: {} },
    );
    expect(state.lockStateBySlotId[firstSlot.slotId]).toBe(firstSlot.locked);
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
      modifiedFromSource: true,
      regions: {
        stem: [{ type: 'paragraph', text: 'Paper-specific stem text.' }],
      },
    });
    expect(editedState.questionsById.q_mcq_heredity_001).toBe(
      state.questionsById.q_mcq_heredity_001,
    );

    const restoredState = restoreSlotSource(editedState, 'slot_A_01');

    expect(restoredState.slotEditsById.slot_A_01).toEqual({
      modifiedFromSource: false,
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
});
