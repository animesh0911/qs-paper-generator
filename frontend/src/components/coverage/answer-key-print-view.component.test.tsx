/**
 * Tests for the print-only answer-key renderer.
 *
 * @module answerKeyPrintViewTests
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { assertPaperDocument } from '@/lib/paper-document';
import { mockPaperDocumentV1 } from '@/mocks';
import type { PaperAnswerDocument, PaperDocument } from '@/types';
import { AnswerKeyPrintView } from './answer-key-print-view.component';

function answerDocumentFor(document: PaperDocument): PaperAnswerDocument {
  return {
    schemaVersion: 'paper_answer_document.v1',
    paperId: document.paper.id,
    answersBySlotId: Object.fromEntries(
      document.paper.sections.flatMap((section) =>
        section.slots.map((slot) => [
          slot.id,
          {
            slotId: slot.id,
            questionId: slot.selectedQuestionId ?? '',
            content: [
              {
                type: 'paragraph',
                text: `Answer for stable slot ${slot.id}`,
              },
            ],
            source: 'source' as const,
            modified: false,
          },
        ]),
      ),
    ),
  };
}

describe('AnswerKeyPrintView', () => {
  it('walks current slot order and looks up answers by stable slot id', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    const section = document.paper.sections[0];
    const [firstSlot, secondSlot] = section.slots;
    const answerDocument = answerDocumentFor(document);

    section.slots = [secondSlot, firstSlot, ...section.slots.slice(2)];

    const html = renderToStaticMarkup(
      <AnswerKeyPrintView document={document} answerDocument={answerDocument} />,
    );

    expect(html.indexOf(`Answer for stable slot ${secondSlot.id}`)).toBeLessThan(
      html.indexOf(`Answer for stable slot ${firstSlot.id}`),
    );
    expect(html).toContain(`<span class="paper-question-number">${secondSlot.number}.</span>`);
  });

  it('renders missing answers as an explicit fallback', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    const slot = document.paper.sections[0].slots[0];
    const answerDocument = answerDocumentFor(document);
    delete answerDocument.answersBySlotId[slot.id];

    const html = renderToStaticMarkup(
      <AnswerKeyPrintView document={document} answerDocument={answerDocument} />,
    );

    expect(html).toContain('Answer not available');
    expect(html).toContain(`<span class="paper-question-number">${slot.number}.</span>`);
  });

  it('renders rich answer content', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    const slot = document.paper.sections[0].slots[0];
    const answerDocument = answerDocumentFor(document);
    answerDocument.answersBySlotId[slot.id].content = [
      { type: 'paragraph', text: 'Use Ohm’s law.' },
      { type: 'equation', latex: 'V = IR' },
      { type: 'table', rows: [['Quantity', 'Value'], ['R', '3 Ω']] },
    ];

    const html = renderToStaticMarkup(
      <AnswerKeyPrintView document={document} answerDocument={answerDocument} />,
    );

    expect(html).toContain('Use Ohm’s law.');
    expect(html).toContain('class="katex"');
    expect(html).toContain('class="paper-content-table"');
    expect(html).toContain('<td>Quantity</td>');
    expect(html).toContain('<td>3 Ω</td>');
  });

  it('keeps output compact and omits full question text and provenance state', () => {
    const document = structuredClone(assertPaperDocument(mockPaperDocumentV1));
    const slot = document.paper.sections[0].slots[0];
    const question = document.questions.find(
      (candidate) => candidate.id === slot.selectedQuestionId,
    );
    const answerDocument = answerDocumentFor(document);
    answerDocument.answersBySlotId[slot.id] = {
      ...answerDocument.answersBySlotId[slot.id],
      source: 'generated',
      modified: true,
      content: [{ type: 'paragraph', text: 'Compact final answer only.' }],
    };

    const html = renderToStaticMarkup(
      <AnswerKeyPrintView document={document} answerDocument={answerDocument} />,
    );

    expect(html).toContain('Compact final answer only.');
    expect(html).not.toContain(question?.rawText ?? 'missing question');
    expect(html).not.toContain('generated');
    expect(html).not.toContain('modified');
  });
});
