/**
 * Print-only answer-key surface backed by the saved paper-local answer document.
 *
 * The renderer deliberately walks the current paper slot order and then looks
 * up answers by stable slot id, so reordering in the editor is reflected in the
 * printed key without depending on bank/live answer state.
 *
 * @module AnswerKeyPrintView
 */
import { MathExpression } from '@/components/math/math-expression.component';
import { LatexText } from '@/components/math/latex-text.component';
import { latexHasMath } from '@/components/math/latex';
import type { ContentItem, PaperAnswerDocument, PaperDocument } from '@/types';

export interface AnswerKeyPrintViewProps {
  document: PaperDocument;
  answerDocument: PaperAnswerDocument;
}

export function AnswerKeyPrintView({
  document,
  answerDocument,
}: AnswerKeyPrintViewProps) {
  return (
    <article className="paper-sheet answer-key-paper">
      <header className="answer-key-header">
        <p className="answer-key-eyebrow">Answer key</p>
        <h1 className="paper-title">{document.paper.title}</h1>
        <p className="paper-meta">
          {document.template.classLevel} — {document.template.subject} · Maximum
          Marks: {document.paper.totalMarks}
        </p>
      </header>

      <div className="answer-key-sections">
        {document.paper.sections.map((section) => (
          <section key={section.id} className="answer-key-section">
            <header className="paper-section-header answer-key-section-header">
              <h2 className="paper-section-title">{section.title}</h2>
              {section.subtitle && (
                <p className="paper-section-subtitle">{section.subtitle}</p>
              )}
            </header>
            <ol className="answer-key-answers">
              {section.slots.map((slot) => {
                const answer = answerDocument.answersBySlotId[slot.id];
                return (
                  <li key={slot.id} className="answer-key-answer">
                    <div className="answer-key-answer-meta">
                      <span className="paper-question-number">
                        {slot.number}.
                      </span>
                      <span className="paper-marks">
                        {slot.marks} mark{slot.marks === 1 ? '' : 's'}
                      </span>
                    </div>
                    <div className="answer-key-answer-body">
                      {answer?.content?.length ? (
                        <AnswerContentItems items={answer.content} />
                      ) : (
                        <p className="paper-unfilled">Answer not available</p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
      </div>
    </article>
  );
}

function AnswerContentItems({ items }: { items: ContentItem[] }) {
  return (
    <>
      {items.map((item, index) => (
        <AnswerContentItem key={index} item={item} />
      ))}
    </>
  );
}

function AnswerContentItem({ item }: { item: ContentItem }) {
  if (item.type === 'table' && item.rows) {
    return (
      <table className="paper-content-table">
        <tbody>
          {item.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  // Prefer the `latex` field when it carries real math (no plain text, or math
  // survives once `\text{…}` prose is stripped); plain-prose latex falls
  // through to text. Mirrors the question paper renderer.
  if (item.latex && !item.text) {
    return (
      <p>
        <MathExpression latex={item.latex} />
      </p>
    );
  }
  // A paragraph carrying both text and math-bearing latex: render the prose
  // wrappable and typeset only the math fragments.
  if (item.latex && latexHasMath(item.latex)) {
    return (
      <p>
        <LatexText latex={item.latex} />
      </p>
    );
  }

  return <p>{contentItemToText(item)}</p>;
}

function contentItemToText(item: ContentItem) {
  if (item.text) return item.text;
  if (item.latex) return item.latex;
  if (item.type === 'image_placeholder') {
    return item.caption ? `[Diagram: ${item.caption}]` : '[Diagram]';
  }
  return item.caption ?? '';
}
