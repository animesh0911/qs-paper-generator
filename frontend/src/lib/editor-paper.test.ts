/**
 * Tests for the PaperDocumentV1 editor shell view model.
 *
 * These tests pin the public mapper behavior used by the editor route:
 * mocked documents become printable paper metadata, section rows, BlockNote
 * starter blocks, and validation counts.
 *
 * @module editorPaperTests
 */
import { describe, expect, it } from 'vitest';
import { mockPaperDocumentV1 } from '@/mocks';
import {
  assertPaperDocument,
  normalizePaperDocument,
  setSlotRegionOverride,
} from './paper-document';
import { buildEditorPaperView } from './editor-paper';

describe('editor paper view model', () => {
  it('loads the mocked PaperDocumentV1 into a CBSE paper canvas model', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const view = buildEditorPaperView(document);

    expect(view.title).toBe('Science');
    expect(view.paperMeta).toEqual([
      'Class X',
      'Maximum Marks: 80',
      'Time: 3 hours',
    ]);
    expect(view.instructions).toEqual(
      expect.arrayContaining([
        'NOTE',
        'Please check that this question paper contains 39 questions.',
        'General Instructions',
        'This question paper contain 39 questions. All questions are compulsory.',
      ]),
    );
    expect(view.sections.map((section) => section.title)).toEqual([
      'Section A',
      'Section B',
      'Section C',
    ]);
    expect(view.sections[0].slots[0]).toMatchObject({
      displayNumber: '1',
      marksLabel: '1 mark',
      questionText:
        'What is the phenotypic ratio in the F2 generation of a monohybrid cross?',
      locked: false,
    });
    expect(view.sections[0].slots[0].blockNoteBlocks).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: 'paragraph',
          content:
            'What is the phenotypic ratio in the F2 generation of a monohybrid cross?',
        }),
        expect.objectContaining({
          type: 'paragraph',
          content: '3 : 1',
        }),
      ]),
    );
  });

  it('maps selected questions into a stable editable region block tree', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const view = buildEditorPaperView(document);
    const firstSlot = view.sections[0].slots[0];

    expect(firstSlot.questionBlockTree).toMatchObject({
      blockType: 'questionContainerBlock',
      slotId: 'slot_A_01',
      questionId: 'q_mcq_heredity_001',
      allowRegionReorder: false,
      allowRegionDelete: false,
    });
    expect(
      firstSlot.questionBlockTree.children.map((region) => ({
        blockType: region.blockType,
        regionKey: region.regionKey,
        sourceKind: region.sourceKind,
        editTarget: region.editTarget,
        sourceLocked: region.sourceLocked,
      })),
    ).toEqual([
      {
        blockType: 'questionStemBlock',
        regionKey: 'stem',
        sourceKind: 'source_question_text',
        editTarget: 'slot_override',
        sourceLocked: true,
      },
      {
        blockType: 'mcqOptionBlock',
        regionKey: 'option:A',
        sourceKind: 'source_question_text',
        editTarget: 'slot_override',
        sourceLocked: true,
      },
      {
        blockType: 'mcqOptionBlock',
        regionKey: 'option:B',
        sourceKind: 'source_question_text',
        editTarget: 'slot_override',
        sourceLocked: true,
      },
      {
        blockType: 'mcqOptionBlock',
        regionKey: 'option:C',
        sourceKind: 'source_question_text',
        editTarget: 'slot_override',
        sourceLocked: true,
      },
      {
        blockType: 'mcqOptionBlock',
        regionKey: 'option:D',
        sourceKind: 'source_question_text',
        editTarget: 'slot_override',
        sourceLocked: true,
      },
    ]);
    expect(view.paperChromeBlocks[0]).toMatchObject({
      blockType: 'paper_title',
      sourceKind: 'paper_chrome',
      editTarget: 'paper_document',
      sourceLocked: false,
    });
    expect(
      view.paperChromeBlocks.map((block) => ({
        blockType: block.blockType,
        sourceKind: block.sourceKind,
      })),
    ).toEqual(
      expect.arrayContaining([
        { blockType: 'section_heading', sourceKind: 'paper_chrome' },
        { blockType: 'section_subtitle', sourceKind: 'paper_chrome' },
        { blockType: 'section_marks', sourceKind: 'paper_chrome' },
        { blockType: 'section_instructions', sourceKind: 'paper_chrome' },
      ]),
    );
    expect(view.sections[0].titleBlock.regionKey).toBe('section:A:title');
    expect(view.sections[0].subtitleBlock?.regionKey).toBe(
      'section:A:subtitle',
    );
  });

  it('supports every V1 question region block type across the mock paper', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const view = buildEditorPaperView(document);

    const blockTypes = new Set(
      view.sections.flatMap((section) =>
        section.slots.flatMap((slot) =>
          slot.questionBlockTree.children.map((region) => region.blockType),
        ),
      ),
    );

    expect(blockTypes).toEqual(
      new Set([
        'questionStemBlock',
        'mcqOptionBlock',
        'passageBlock',
        'subQuestionBlock',
        'internalChoiceBlock',
      ]),
    );
  });

  it('renders slot-level region overrides without mutating source questions', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);
    const nextState = setSlotRegionOverride(state, 'slot_A_01', 'stem', [
      {
        type: 'paragraph',
        text: 'Edited only for this paper slot.',
      },
    ]);

    const view = buildEditorPaperView(document, {
      slotEditsById: nextState.slotEditsById,
    });
    const firstSlot = view.sections[0].slots[0];

    expect(nextState.questionsById.q_mcq_heredity_001.rawText).toBe(
      'What is the phenotypic ratio in the F2 generation of a monohybrid cross?',
    );
    expect(firstSlot.modifiedFromSource).toBe(true);
    expect(firstSlot.questionText).toBe('Edited only for this paper slot.');
    expect(firstSlot.questionBlockTree.children[0]).toMatchObject({
      regionKey: 'stem',
      isOverridden: true,
      text: 'Edited only for this paper slot.',
    });
  });

  it('keeps display prefixes outside editable region content', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const view = buildEditorPaperView(document);
    const optionRegion =
      view.sections[0].slots[0].questionBlockTree.children[1];

    expect(optionRegion.displayPrefix).toBe('(A) ');
    expect(optionRegion.text).toBe('1 : 1');
    expect(optionRegion.blockNoteBlocks).toEqual([
      {
        type: 'paragraph',
        content: '1 : 1',
      },
    ]);
  });

  it('derives the left rail outline and validation summary from the contract', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const view = buildEditorPaperView(document);

    expect(view.outline).toEqual([
      { sectionId: 'A', title: 'Section A', slotCount: 5, marks: 30 },
      { sectionId: 'B', title: 'Section B', slotCount: 2, marks: 25 },
      { sectionId: 'C', title: 'Section C', slotCount: 2, marks: 25 },
    ]);
    expect(view.validationSummary).toEqual({
      totalSlots: 9,
      filledSlots: 9,
      lockedSlots: 1,
      warnings: [],
    });
  });
});
