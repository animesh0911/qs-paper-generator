/**
 * Tests for the shared print/preview PaperDocument renderer.
 *
 * These pin the renderer-side interpretation of editor overrides so PDF output
 * does not drift from the editable region keys produced by the editor.
 *
 * @module paperDocumentViewTests
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { mockPaperDocumentV1 } from '@/mocks';
import { assertPaperDocument } from '@/lib/paper-document';
import { PaperDocumentView } from './paper-document-view.component';

describe('PaperDocumentView', () => {
  it('renders a safe message instead of guessing for unsupported format IDs', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    document.format.id = 'unknown_format_v1';

    const html = renderToStaticMarkup(
      <PaperDocumentView paper={document} mode="print" />,
    );

    expect(html).toContain(
      'This paper format is not supported by the editor yet.',
    );
    expect(html).not.toContain('Section A');
  });

  it('renders overrides for the matching internal choice group index', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    const slot = document.paper.sections[1].slots[1];
    const question = document.questions.find(
      (candidate) => candidate.id === slot.selectedQuestionId,
    );

    expect(question?.content.choices).toBeDefined();
    if (!question?.content.choices) return;

    question.content.choices.push(structuredClone(question.content.choices[0]));
    slot.overrides = {
      modified: true,
      regions: {
        'choice:1:A': [
          {
            type: 'paragraph',
            text: 'Edited second choice group option.',
          },
        ],
      },
    };

    const html = renderToStaticMarkup(
      <PaperDocumentView paper={document} mode="print" />,
    );

    expect(html).toContain('Edited second choice group option.');
    expect(html).toContain(
      'Explain the mechanism of breathing in human beings.',
    );
  });

  it('uses format layout rules for MCQ options and right-column marks', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    document.format.layout.mcqOptions = 'two_column';
    document.format.layout.marks = 'right_column';

    const html = renderToStaticMarkup(
      <PaperDocumentView paper={document} mode="print" />,
    );

    expect(html).toContain('paper-options paper-options-two-column');
    expect(html).toContain('class="paper-marks">1</span>');
    expect(html).not.toContain('class="paper-inline-marks"');
  });

  it('renders CBSE masthead chrome and one right-column mark per slot', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    document.paper.chromeBlocks = document.paper.chromeBlocks?.map((block) => {
      if (block.role === 'series') return { ...block, text: 'SERIES-X' };
      if (block.role === 'set') return { ...block, text: 'SET-9' };
      if (block.role === 'paper_code') return { ...block, text: '99/9/9' };
      if (block.role === 'subject_label') return { ...block, text: 'SCIENCE' };
      if (block.role === 'paper_meta_left') {
        return { ...block, text: 'Time allowed : 2 hours' };
      }
      if (block.role === 'paper_meta_right') {
        return { ...block, text: 'Maximum Marks : 40' };
      }
      return block;
    });

    const html = renderToStaticMarkup(
      <PaperDocumentView paper={document} mode="print" />,
    );
    const slotCount = document.paper.sections.reduce(
      (total, section) => total + section.slots.length,
      0,
    );

    expect(html).toContain('Series : SERIES-X');
    expect(html).toContain('SET-9');
    expect(html).toContain('99/9/9');
    expect(html).toContain('SCIENCE');
    expect(html).toContain('Roll No.');
    expect(html).toContain('class="paper-roll-blank"');
    expect(html).toContain('Time allowed : 2 hours');
    expect(html).toContain('Maximum Marks : 40');
    expect(html.match(/class="paper-marks"/g)).toHaveLength(slotCount);
  });

  it('can render marks inline when the format does not request a right column', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    document.format.layout.marks = 'inline';

    const html = renderToStaticMarkup(
      <PaperDocumentView paper={document} mode="print" />,
    );

    expect(html).toContain('class="paper-inline-marks">(1 mark)</span>');
    expect(html).toContain('paper-subquestion paper-subquestion-inline-marks');
    expect(html).toContain('class="paper-inline-marks">(2 marks)</span>');
    expect(html).not.toContain('class="paper-marks">1</span>');
  });

  it('renders structured content tables as paper tables', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    const slot = document.paper.sections[0].slots[0];
    const question = document.questions.find(
      (candidate) => candidate.id === slot.selectedQuestionId,
    );

    expect(question).toBeDefined();
    if (!question) return;

    question.content.stem = [
      { type: 'paragraph', text: 'Use the observations below.' },
      {
        type: 'table',
        rows: [
          ['I (A)', '0.4', '0.8'],
          ['V (V)', '1.2', '2.4'],
        ],
      },
    ];
    question.rawText = 'Use the observations below.';

    const html = renderToStaticMarkup(
      <PaperDocumentView paper={document} mode="print" />,
    );

    expect(html).toContain('<table');
    expect(html).toContain('class="paper-content-table"');
    expect(html).toContain('<td>I (A)</td>');
    expect(html).toContain('<td>2.4</td>');
  });

  it('keeps table content inside option and subquestion grid body cells', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    const slot = document.paper.sections[0].slots[0];
    const question = document.questions.find(
      (candidate) => candidate.id === slot.selectedQuestionId,
    );

    expect(question).toBeDefined();
    if (!question) return;

    question.content.options = [
      {
        label: 'A',
        content: [
          { type: 'paragraph', text: 'Use the option table.' },
          { type: 'table', rows: [['Metal', 'Reaction']] },
        ],
      },
    ];
    question.content.subparts = [
      {
        label: 'a',
        marks: 1,
        content: [
          { type: 'paragraph', text: 'Use the subquestion table.' },
          { type: 'table', rows: [['I (A)', '0.4']] },
        ],
      },
    ];

    const html = renderToStaticMarkup(
      <PaperDocumentView paper={document} mode="print" />,
    );

    expect(html).toContain('class="paper-option-body"');
    expect(html).toContain('class="paper-subquestion-body"');
    expect(html).toContain('<td>Metal</td>');
    expect(html).toContain('<td>I (A)</td>');
  });
});
