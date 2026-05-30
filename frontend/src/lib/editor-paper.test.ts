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
import { assertPaperDocument } from './paper-document';
import { buildEditorPaperView } from './editor-paper';

describe('editor paper view model', () => {
  it('loads the mocked PaperDocumentV1 into a CBSE paper canvas model', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const view = buildEditorPaperView(document);

    expect(view.title).toBe('Science');
    expect(view.paperMeta).toEqual([
      'Class X',
      'Maximum Marks: 30',
      'Time: 3 hours',
    ]);
    expect(view.instructions).toEqual([
      'Maximum Marks: 30. Time allowed: 3 hours.',
      'All questions are compulsory unless an internal choice is provided.',
    ]);
    expect(view.sections.map((section) => section.title)).toEqual([
      'Section A',
      'Section B',
      'Section C',
      'Section D',
      'Section E',
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
          content: '(B) 3 : 1',
        }),
      ]),
    );
  });

  it('derives the left rail outline and validation summary from the contract', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const view = buildEditorPaperView(document);

    expect(view.outline).toEqual([
      { sectionId: 'A', title: 'Section A', slotCount: 2, marks: 2 },
      { sectionId: 'B', title: 'Section B', slotCount: 2, marks: 4 },
      { sectionId: 'C', title: 'Section C', slotCount: 2, marks: 10 },
      { sectionId: 'D', title: 'Section D', slotCount: 1, marks: 4 },
      { sectionId: 'E', title: 'Section E', slotCount: 2, marks: 10 },
    ]);
    expect(view.validationSummary).toEqual({
      totalSlots: 9,
      filledSlots: 9,
      lockedSlots: 1,
      warnings: [],
    });
  });
});
