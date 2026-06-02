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
  reorderSlotWithinOrderZone,
  setSlotSelectedQuestion,
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
      showMarksLabel: true,
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

  it('preserves multi-paragraph manual edits as separate editable blocks', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);
    const nextState = setSlotRegionOverride(state, 'slot_A_01', 'stem', [
      {
        type: 'paragraph',
        text: 'Edited first line.',
      },
      {
        type: 'paragraph',
        text: 'Added line from Enter key.',
      },
    ]);

    const view = buildEditorPaperView(document, {
      slotEditsById: nextState.slotEditsById,
    });
    const stemRegion = view.sections[0].slots[0].questionBlockTree.children[0];

    expect(stemRegion.text).toBe(
      'Edited first line.\nAdded line from Enter key.',
    );
    expect(stemRegion.blockNoteBlocks).toEqual([
      {
        type: 'paragraph',
        content: 'Edited first line.',
      },
      {
        type: 'paragraph',
        content: 'Added line from Enter key.',
      },
    ]);
  });

  it('maps structured tables into editable BlockNote table blocks', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    const firstQuestion = document.questions[0];

    firstQuestion.content.stem = [
      { type: 'paragraph', text: 'Use the observations below.' },
      {
        type: 'table',
        rows: [
          ['I (A)', '0.4', '0.8'],
          ['V (V)', '1.2', '2.4'],
        ],
      },
    ];

    const view = buildEditorPaperView(document);
    const stemRegion = view.sections[0].slots[0].questionBlockTree.children[0];

    expect(stemRegion.blockNoteBlocks).toEqual([
      {
        type: 'paragraph',
        content: 'Use the observations below.',
      },
      {
        type: 'table',
        content: {
          type: 'tableContent',
          rows: [
            { cells: ['I (A)', '0.4', '0.8'] },
            { cells: ['V (V)', '1.2', '2.4'] },
          ],
        },
      },
    ]);
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

  it('does not duplicate slot marks when imported question text carries them', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    const question = document.questions.find(
      (candidate) => candidate.id === 'q_short_electricity_001',
    );
    expect(question).toBeDefined();
    question!.rawText =
      'State Ohm law and write its mathematical form. (2 marks)';
    question!.content.stem = [
      {
        type: 'paragraph',
        text: 'State Ohm law and write its mathematical form. (2 marks)',
      },
      { type: 'equation', latex: 'V = IR', text: 'V = IR' },
    ];

    const view = buildEditorPaperView(document);
    const slot = findSlot(view, 'slot_B_02');

    expect(slot.marksLabel).toBe('2 marks');
    expect(slot.showMarksLabel).toBe(false);
  });

  it('keeps subpart marks without adding a duplicate total marks column', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const view = buildEditorPaperView(document);
    const slot = findSlot(view, 'slot_C_01');

    expect(slot.marksLabel).toBe('5 marks');
    expect(slot.showMarksLabel).toBe(false);
    expect(
      slot.questionBlockTree.children
        .filter((region) => region.displaySuffix)
        .map((region) => region.displaySuffix),
    ).toEqual([' (2 marks)', ' (2 marks)', ' (1 mark)']);
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
      warnings: [
        'Paper total is 80 marks, but Slot marks total 30.',
        'Section A is labelled 30 marks, but its Slots total 13.',
        'Section B is labelled 25 marks, but its Slots total 10.',
        'Section C is labelled 25 marks, but its Slots total 7.',
      ],
    });
  });

  it('warns when inline mark edits make paper totals mathematically inconsistent', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const section = document.paper.sections[0];

    document.paper.totalMarks = 30;
    section.marks = 13;
    section.slots[0].marks = 2;

    const view = buildEditorPaperView(document);

    expect(view.validationSummary.warnings).toEqual(
      expect.arrayContaining([
        'Paper total is 30 marks, but Slot marks total 31.',
        'Section A is labelled 13 marks, but its Slots total 14.',
      ]),
    );
  });

  it('renders recomputed display numbers after slot reorder', () => {
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

    const view = buildEditorPaperView(result.state.document);

    expect(view.sections[0].slots[0]).toMatchObject({
      slotId: 'slot_A_02',
      displayNumber: '1',
    });
    expect(view.sections[0].slots[1]).toMatchObject({
      slotId: 'slot_A_01',
      displayNumber: '2',
    });
  });

  it('resolves slot alternatives for the selected-question inspector', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const view = buildEditorPaperView(document);
    const firstSlot = view.sections[0].slots[0];
    const lockedSlot = view.sections[0].slots[2];

    expect(firstSlot.alternateQuestions).toEqual([
      expect.objectContaining({
        questionId: 'q_mcq_heredity_002',
        marks: 1,
        questionType: 'mcq',
        chapterNames: ['Heredity'],
        topicNames: ['Mendel Experiments'],
        difficulty: 'easy',
        sourceName: 'School Science Question Bank',
      }),
      expect.objectContaining({
        questionId: 'q_mcq_electricity_001',
        chapterNames: ['Electricity'],
        difficulty: 'easy',
      }),
      expect.objectContaining({
        questionId: 'q_mcq_chemotropism_001',
        chapterNames: ['Control and Coordination'],
        difficulty: 'easy',
      }),
      expect.objectContaining({
        questionId: 'q_mcq_spirogyra_001',
        chapterNames: ['How do Organisms Reproduce'],
        difficulty: 'medium',
      }),
      expect.objectContaining({
        questionId: 'q_mcq_photosynthesis_001',
        chapterNames: ['Life Processes'],
        difficulty: 'medium',
      }),
    ]);
    expect(lockedSlot.locked).toBe(true);
    expect(lockedSlot.alternateQuestions).toHaveLength(4);
  });

  it('keeps the previous selected Question visible as an alternative after swap', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);
    const replacedState = setSlotSelectedQuestion(
      state,
      'slot_E_02',
      'q_table_metals_002',
    );

    const view = buildEditorPaperView(replacedState.document);
    const swappedSlot = findSlot(view, 'slot_E_02');

    expect(swappedSlot.questionText).toBe(
      'Compare the properties of metals and non-metals in tabular form.',
    );
    expect(
      swappedSlot.alternateQuestions.map((question) => question.questionId),
    ).toEqual(['q_table_metals_001']);
  });

  it('shows all rotated alternatives after swap when filtered modes would hide them', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);
    const replacedState = setSlotSelectedQuestion(
      state,
      'slot_E_02',
      'q_table_metals_002',
    );

    const easierView = buildEditorPaperView(replacedState.document, {
      alternativesIntentBySlotId: {
        slot_E_02: 'easier',
      },
    });
    const swapView = buildEditorPaperView(replacedState.document, {
      alternativesIntentBySlotId: {
        slot_E_02: 'swap',
      },
    });

    expect(findSlot(easierView, 'slot_E_02').alternateQuestions).toHaveLength(
      0,
    );
    expect(
      findSlot(swapView, 'slot_E_02').alternateQuestions.map(
        (question) => question.questionId,
      ),
    ).toEqual(['q_table_metals_001']);
  });

  it('formats alternatives from structured question regions instead of raw text only', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    const alternateQuestion = document.questions.find(
      (question) => question.id === 'q_mcq_heredity_002',
    );
    expect(alternateQuestion).toBeDefined();
    alternateQuestion!.rawText = 'Truncated imported stem.';

    const view = buildEditorPaperView(document);
    const firstAlternative = findSlot(view, 'slot_A_01').alternateQuestions[0];

    expect(firstAlternative.questionText).toBe('Truncated imported stem.');
    expect(
      firstAlternative.questionBlockTree.children.map((region) => ({
        regionKey: region.regionKey,
        prefix: region.displayPrefix,
        text: region.text,
      })),
    ).toEqual([
      {
        regionKey: 'stem',
        prefix: '',
        text: 'Which pair represents contrasting traits studied by Mendel in pea plants?',
      },
      { regionKey: 'option:A', prefix: '(A) ', text: 'Tall and dwarf' },
      { regionKey: 'option:B', prefix: '(B) ', text: 'Red and green blood' },
      { regionKey: 'option:C', prefix: '(C) ', text: 'Metal and non-metal' },
      { regionKey: 'option:D', prefix: '(D) ', text: 'Acid and base' },
    ]);
  });

  it('filters alternatives by topic first and falls back to chapter matches', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const topicView = buildEditorPaperView(document, {
      alternativesIntentBySlotId: {
        slot_A_01: 'topic',
        slot_B_01: 'topic',
      },
    });
    const hereditarySlot = findSlot(topicView, 'slot_A_01');
    const stomataSlot = findSlot(topicView, 'slot_B_01');

    expect(hereditarySlot.alternateQuestions).toEqual([
      expect.objectContaining({ questionId: 'q_mcq_heredity_002' }),
    ]);
    expect(stomataSlot.alternateQuestions).toEqual([
      expect.objectContaining({ questionId: 'q_short_stomata_002' }),
    ]);
  });

  it('filters alternatives by difficulty relative to the current question', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const filteredView = buildEditorPaperView(document, {
      alternativesIntentBySlotId: {
        slot_B_01: 'harder',
        slot_E_02: 'easier',
      },
    });
    const stomataSlot = findSlot(filteredView, 'slot_B_01');
    const metalsSlot = findSlot(filteredView, 'slot_E_02');

    expect(
      stomataSlot.alternateQuestions.map((question) => question.questionId),
    ).toEqual([
      'q_short_stomata_002',
      'q_short_hormones_001',
      'q_short_electrical_impulse_001',
      'q_short_variation_001',
    ]);
    expect(
      metalsSlot.alternateQuestions.map((question) => question.questionId),
    ).toEqual(['q_table_metals_002']);
  });
});

function findSlot(
  view: ReturnType<typeof buildEditorPaperView>,
  slotId: string,
) {
  const slot = view.sections
    .flatMap((section) => section.slots)
    .find((candidate) => candidate.slotId === slotId);

  expect(slot).toBeDefined();
  return slot!;
}
