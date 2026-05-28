/**
 * Renders an assembled `PaperDocument` (PaperDocumentV1 format).
 *
 * Builds a questions-by-id lookup from `doc.questions`, then iterates
 * `doc.paper.sections[].slots[]` to render each question. Pure — no fetches,
 * no state. The forwarded ref is used by the dashboard to scroll into view.
 *
 * @module PaperPreview
 */
import { forwardRef, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { PaperDocument } from '@/types';

export interface PaperPreviewProps {
  paper: PaperDocument;
}

export const PaperPreview = forwardRef<HTMLDivElement, PaperPreviewProps>(
  function PaperPreview({ paper: doc }, ref) {
    const questionById = useMemo(
      () => Object.fromEntries(doc.questions.map((q) => [q.questionId, q])),
      [doc.questions],
    );

    return (
      <Card ref={ref}>
        <CardHeader>
          <CardTitle>{doc.paper.title}</CardTitle>
          <p className="text-sm text-muted-foreground">
            Class 10 — Science · Maximum Marks: {doc.paper.totalMarks}
          </p>
        </CardHeader>
        <CardContent className="space-y-5">
          {doc.paper.sections.map((section) => (
            <div key={section.sectionId}>
              <h2 className="font-semibold mb-1">{section.title}</h2>
              {section.instructions && (
                <p className="text-xs text-muted-foreground mb-2">
                  {section.instructions}
                </p>
              )}
              <ol className="space-y-3">
                {section.slots.map((slot) => {
                  const q = slot.selectedQuestionId
                    ? questionById[slot.selectedQuestionId]
                    : null;
                  return (
                    <li key={slot.slotId} className="text-sm">
                      <span className="font-medium">
                        Q{slot.displayNumber}.
                      </span>{' '}
                      {q ? (
                        <>
                          {q.rawText}{' '}
                          <span className="text-muted-foreground">
                            ({slot.marks} mark{slot.marks !== 1 ? 's' : ''})
                          </span>
                          {q.content.options &&
                            q.content.options.length > 0 && (
                              <ul className="ml-6 mt-1 space-y-0.5 text-muted-foreground">
                                {q.content.options.map((o) => (
                                  <li key={o.label}>
                                    ({o.label}) {o.content[0]?.text}
                                  </li>
                                ))}
                              </ul>
                            )}
                        </>
                      ) : (
                        <span className="text-muted-foreground italic">
                          No question selected ({slot.marks}m)
                        </span>
                      )}
                    </li>
                  );
                })}
              </ol>
            </div>
          ))}
        </CardContent>
      </Card>
    );
  },
);
