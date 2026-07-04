/**
 * @vitest-environment jsdom
 * Tests for the question info drawer provenance display.
 *
 * @module editorQuestionInfoOverlayTests
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { EditorPaperSlotView } from '@/lib/editor-paper';
import type { DocQuestion } from '@/types';
import { EditorQuestionInfoOverlay } from './editor-question-info-overlay.component';

afterEach(() => cleanup());

describe('EditorQuestionInfoOverlay', () => {
  it('makes the selected question source clearly visible', () => {
    render(
      <EditorQuestionInfoOverlay
        selectedSlot={makeSlot()}
        selectedQuestion={makeQuestion()}
        onClose={vi.fn()}
        onRestoreSelectedSlot={vi.fn()}
      />,
    );

    expect(
      screen.getByRole('heading', { name: 'Source and question details' }),
    ).toBeTruthy();
    expect(screen.getByText('CBSE 2026 Science Set 31/1/1')).toBeTruthy();
    expect(screen.getByText('previous year paper')).toBeTruthy();
    expect(screen.getByText('science-2026.pdf')).toBeTruthy();
    expect(screen.getByText('12')).toBeTruthy();
    expect(screen.getByText('Q7')).toBeTruthy();
  });
});

function makeSlot(): EditorPaperSlotView {
  return {
    slotId: 'slot_A_01',
    displayNumber: '1',
    marksLabel: '1 mark',
    showMarksLabel: true,
    questionText: 'What is heredity?',
    questionType: 'mcq',
    locked: false,
    editCapabilities: {
      editText: true,
      editMarks: true,
      swap: true,
      lock: true,
      reorder: true,
    },
    modifiedFromSource: false,
    alternateQuestions: [],
    blockNoteBlocks: [],
    questionBlockTree: {
      blockType: 'questionContainerBlock',
      slotId: 'slot_A_01',
      questionId: 'q_1',
      allowRegionReorder: true,
      allowRegionDelete: true,
      children: [
        {
          blockType: 'questionStemBlock',
          regionKey: 'stem',
          text: 'What is heredity?',
          displayPrefix: '',
          displaySuffix: '',
          content: [{ type: 'paragraph', text: 'What is heredity?' }],
          blockNoteBlocks: [],
          editable: true,
          sourceKind: 'source_question_text',
          editTarget: 'slot_override',
          sourceLocked: true,
          isOverridden: false,
        },
      ],
    },
  };
}

function makeQuestion(): DocQuestion {
  return {
    id: 'q_1',
    language: 'en',
    defaultMarks: 1,
    type: 'mcq',
    rawText: 'What is heredity?',
    content: { stem: [{ type: 'paragraph', text: 'What is heredity?' }] },
    metadata: {
      classLevel: '10',
      subject: 'Science',
      chapterNames: ['Heredity'],
      topicNames: ['Inheritance'],
      difficulty: 'easy',
      cognitiveLevel: 'remember',
      requiresDiagram: false,
      requiresTable: false,
    },
    source: {
      type: 'previous_year_paper',
      name: 'CBSE 2026 Science Set 31/1/1',
      fileName: 'science-2026.pdf',
      pageNumber: 12,
      originalQuestionNumber: '7',
    },
  };
}
