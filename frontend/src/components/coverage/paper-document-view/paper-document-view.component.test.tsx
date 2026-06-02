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
    expect(html).toContain('Explain the mechanism of breathing in human beings.');
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
});
