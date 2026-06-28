import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { EditorPaperSlotView } from '@/lib/editor-paper';
import { EditorAnswerOverlay } from './editor-answer-overlay.component';

const slot: EditorPaperSlotView = {
  slotId: 'slot_A_01',
  displayNumber: '1',
  marksLabel: '1 mark',
  showMarksLabel: true,
  questionText: 'What is carbon?',
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
  questionBlockTree: {
    blockType: 'questionContainerBlock',
    slotId: 'slot_A_01',
    questionId: 'q_1',
    allowRegionReorder: false,
    allowRegionDelete: false,
    children: [
      {
        blockType: 'questionStemBlock',
        regionKey: 'stem',
        text: 'What is carbon?',
        displayPrefix: '',
        displaySuffix: '',
        content: [{ type: 'paragraph', text: 'What is carbon?' }],
        blockNoteBlocks: [],
        editable: true,
        sourceKind: 'source_question_text',
        editTarget: 'slot_override',
        sourceLocked: true,
        isOverridden: false,
      },
    ],
  },
  alternateQuestions: [],
  blockNoteBlocks: [],
};

describe('EditorAnswerOverlay', () => {
  it('shows answer content and warns for generated unverified answers', () => {
    const html = renderToStaticMarkup(
      <EditorAnswerOverlay
        selectedSlot={slot}
        answerEntry={{
          slotId: 'slot_A_01',
          questionId: 'q_1',
          content: [{ type: 'paragraph', text: 'Carbon is a tetravalent non-metal.' }],
          source: 'generated',
          modified: false,
        }}
        onClose={() => undefined}
      />,
    );

    expect(html).toContain('Question 1 answer');
    expect(html).toContain('Carbon is a tetravalent non-metal.');
    expect(html).toContain('AI-generated answer');
  });

  it('does not show a provenance chip for source answers', () => {
    const html = renderToStaticMarkup(
      <EditorAnswerOverlay
        selectedSlot={slot}
        answerEntry={{
          slotId: 'slot_A_01',
          questionId: 'q_1',
          content: [{ type: 'paragraph', text: 'From the bank.' }],
          source: 'source',
          modified: false,
        }}
        onClose={() => undefined}
      />,
    );

    expect(html).toContain('From the bank.');
    expect(html).not.toContain('AI-generated answer');
  });

  it('renders table answer content', () => {
    const html = renderToStaticMarkup(
      <EditorAnswerOverlay
        selectedSlot={slot}
        answerEntry={{
          slotId: 'slot_A_01',
          questionId: 'q_1',
          content: [
            {
              type: 'table',
              rows: [
                ['Bond', 'Example'],
                ['Covalent', 'Methane'],
              ],
            },
          ],
          source: 'source',
          modified: false,
        }}
        onClose={() => undefined}
      />,
    );

    expect(html).toContain('<table');
    expect(html).toContain('Covalent');
    expect(html).toContain('Methane');
  });

  it('shows a missing-answer state when no answer entry is available', () => {
    const html = renderToStaticMarkup(
      <EditorAnswerOverlay selectedSlot={slot} onClose={() => undefined} />,
    );

    expect(html).toContain('No answer on file.');
  });
});
