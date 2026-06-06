/**
 * Shared PaperDocumentV1 renderer for preview and print surfaces.
 *
 * `buildSimplePaperView` is the single mapping from slot references to
 * rendered Question text. Keeping that lookup here prevents dashboard preview
 * and browser PDF output from drifting as the document contract evolves.
 *
 * Patterns:
 * - Print mode only changes chrome and CSS classes, never document mapping.
 *
 * Where it fits:
 * - Used by: PaperPreview, PrintPaperPage
 * - Uses: PaperDocumentV1 from `types`
 *
 * @module PaperDocumentView
 */
import { useMemo } from 'react';
import { getPaperFormatRendererResult } from '@/lib/paper-format-renderers';
import type {
  ChoiceGroup,
  ChoiceOption,
  ContentItem,
  DocQuestion,
  DocSlot,
  EditableTextBlock,
  PaperDocument,
  SubQuestion,
} from '@/types';

export interface PaperDocumentViewProps {
  paper: PaperDocument;
  mode?: 'preview' | 'print';
  includeHeader?: boolean;
}

export function PaperDocumentView({
  paper,
  mode = 'preview',
  includeHeader = true,
}: PaperDocumentViewProps) {
  const rendererResult = useMemo(
    () => getPaperFormatRendererResult(paper.format.id),
    [paper.format.id],
  );
  const view = useMemo(
    () =>
      rendererResult.ok
        ? rendererResult.renderer.buildPrintPaperView(paper)
        : null,
    [paper, rendererResult],
  );
  const printMode = mode === 'print';

  if (!rendererResult.ok || !view) {
    return (
      <article className={printMode ? 'paper-sheet print-paper' : ''}>
        <p className={printMode ? 'paper-unfilled' : 'text-sm'}>
          {rendererResult.ok
            ? 'Unable to render paper.'
            : rendererResult.error.userMessage}
        </p>
      </article>
    );
  }

  if (printMode) {
    return (
      <article className="paper-sheet print-paper">
        {includeHeader && <PrintMasthead paper={paper} />}
        <PrintInstructionBlocks paper={paper} />

        <div className="paper-sections">
          {view.sections.map(({ section, slots }) => (
            <section key={section.id} className="paper-section">
              <header className="paper-section-header">
                <h2 className="paper-section-title">{section.title}</h2>
                {section.subtitle && (
                  <p className="paper-section-subtitle">{section.subtitle}</p>
                )}
                {section.instructions && (
                  <p className="paper-instructions">{section.instructions}</p>
                )}
              </header>
              <ol className="paper-questions">
                {slots.map(({ slot, question }) => (
                  <PrintQuestion
                    key={slot.id}
                    slot={slot}
                    question={question}
                    marksPlacement={paper.format.layout.marks}
                    mcqLayout={paper.format.layout.mcqOptions}
                  />
                ))}
              </ol>
            </section>
          ))}
        </div>

        <footer className="paper-footer">
          <span>{chromeBlock(paper, 'footer_left')?.text}</span>
          <span>Page 1</span>
          <span>{chromeBlock(paper, 'footer_right')?.text}</span>
        </footer>
      </article>
    );
  }

  return (
    <article>
      {includeHeader && (
        <header className={printMode ? 'paper-header' : 'space-y-1'}>
          <h1 className={printMode ? 'paper-title' : 'text-xl font-semibold'}>
            {view.document.paper.title}
          </h1>
          <p
            className={
              printMode ? 'paper-meta' : 'text-sm text-muted-foreground'
            }
          >
            Class 10 — Science · Maximum Marks: {view.document.paper.totalMarks}
          </p>
        </header>
      )}

      <div className={printMode ? 'paper-sections' : 'space-y-5'}>
        {view.sections.map(({ section, slots }) => (
          <section
            key={section.id}
            className={printMode ? 'paper-section' : ''}
          >
            <h2
              className={
                printMode ? 'paper-section-title' : 'font-semibold mb-1'
              }
            >
              {section.title}
            </h2>
            {section.instructions && (
              <p
                className={
                  printMode
                    ? 'paper-instructions'
                    : 'text-xs text-muted-foreground mb-2'
                }
              >
                {section.instructions}
              </p>
            )}
            <ol className={printMode ? 'paper-questions' : 'space-y-3'}>
              {slots.map(({ slot, question }) => (
                <li
                  key={slot.id}
                  className={printMode ? 'paper-question' : 'text-sm'}
                >
                  <span
                    className={
                      printMode ? 'paper-question-number' : 'font-medium'
                    }
                  >
                    Q{slot.number}.
                  </span>{' '}
                  {question ? (
                    <>
                      {question.rawText}{' '}
                      <span
                        className={
                          printMode ? 'paper-marks' : 'text-muted-foreground'
                        }
                      >
                        ({slot.marks} mark{slot.marks !== 1 ? 's' : ''})
                      </span>
                      {question.content.options &&
                        question.content.options.length > 0 && (
                          <ul
                            className={
                              printMode
                                ? 'paper-options'
                                : 'ml-6 mt-1 space-y-0.5 text-muted-foreground'
                            }
                          >
                            {question.content.options.map((option) => (
                              <li key={option.label}>
                                ({option.label}) {option.content[0]?.text}
                              </li>
                            ))}
                          </ul>
                        )}
                    </>
                  ) : (
                    <span
                      className={
                        printMode
                          ? 'paper-unfilled'
                          : 'text-muted-foreground italic'
                      }
                    >
                      No question selected ({slot.marks}m)
                    </span>
                  )}
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    </article>
  );
}

function PrintMasthead({ paper }: { paper: PaperDocument }) {
  const series = chromeBlock(paper, 'series');
  const set = chromeBlock(paper, 'set');
  const paperCode = chromeBlock(paper, 'paper_code');
  const subjectLabel = chromeBlock(paper, 'subject_label');
  const leftMeta = chromeBlock(paper, 'paper_meta_left');
  const rightMeta = chromeBlock(paper, 'paper_meta_right');

  return (
    <header className="paper-masthead">
      <div className="paper-topline">
        <div className="paper-series">
          {series ? `Series : ${series.text}` : ''}
        </div>
        <div className="paper-code-stack">
          <div className="paper-barcode" aria-hidden="true" />
          {set && <div className="paper-set">{set.text}</div>}
        </div>
      </div>

      <div className="paper-identity-row">
        <div className="paper-roll">
          <div>रोल नं.</div>
          <div>Roll No.</div>
          <div className="paper-roll-blank" aria-hidden="true" />
        </div>
        <div className="paper-code-box">
          <span>प्रश्न-पत्र कोड</span>
          <strong>Q.P. Code</strong>
          {paperCode && <b>{paperCode.text}</b>}
        </div>
      </div>

      <div className="paper-title-block">
        {subjectLabel && (
          <p className="paper-title-local">{subjectLabel.text}</p>
        )}
        <h1 className="paper-title">{paper.paper.title}</h1>
      </div>

      <div className="paper-meta-grid">
        <span>{leftMeta?.text ?? 'Time allowed : 3 hours'}</span>
        <span>
          {rightMeta?.text ?? `Maximum Marks : ${paper.paper.totalMarks}`}
        </span>
      </div>
    </header>
  );
}

function PrintInstructionBlocks({ paper }: { paper: PaperDocument }) {
  const blocks = paper.paper.instructionBlocks ?? [];
  const noteBlocks = blocks.filter((block) => block.role === 'note');
  const generalBlocks = blocks.filter(
    (block) => block.role === 'general_instruction',
  );
  const hasNoteHeading = blocks.some((block) => block.role === 'note_heading');
  const hasGeneralHeading = blocks.some(
    (block) => block.role === 'general_instructions_heading',
  );

  return (
    <div className="paper-instruction-flow">
      {hasNoteHeading && noteBlocks.length > 0 && (
        <section className="paper-note-table">
          <h2>नोट / NOTE</h2>
          {noteBlocks.map((block, index) => (
            <div key={block.id} className="paper-note-row">
              <span>({toRoman(index + 1)})</span>
              <p>{block.text}</p>
            </div>
          ))}
        </section>
      )}

      {hasGeneralHeading && generalBlocks.length > 0 && (
        <section className="paper-general-instructions">
          <h2>General Instructions :</h2>
          <p>Read the following instructions carefully and follow them :</p>
          {generalBlocks.map((block, index) => (
            <div key={block.id} className="paper-general-row">
              <span>({toRoman(index + 1).toLowerCase()})</span>
              <p>{block.text}</p>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function PrintQuestion({
  slot,
  question,
  marksPlacement,
  mcqLayout,
}: {
  slot: DocSlot;
  question: DocQuestion | null;
  marksPlacement: string;
  mcqLayout: string;
}) {
  const useRightColumnMarks = marksPlacement === 'right_column';

  if (!question) {
    return (
      <li
        className={
          useRightColumnMarks
            ? 'paper-question'
            : 'paper-question paper-question-inline-marks'
        }
      >
        <span className="paper-question-number">{slot.number}.</span>
        <div className="paper-question-body paper-unfilled">
          No question selected.
          {!useRightColumnMarks && (
            <span className="paper-inline-marks">
              ({marksLabel(slot.marks)})
            </span>
          )}
        </div>
        {useRightColumnMarks && (
          <span className="paper-marks">{slot.marks}</span>
        )}
      </li>
    );
  }

  return (
    <li
      className={
        useRightColumnMarks
          ? 'paper-question'
          : 'paper-question paper-question-inline-marks'
      }
    >
      <span className="paper-question-number">{slot.number}.</span>
      <div className="paper-question-body">
        <QuestionContent
          question={question}
          slot={slot}
          marksPlacement={marksPlacement}
          mcqLayout={mcqLayout}
        />
        {!useRightColumnMarks && (
          <span className="paper-inline-marks">({marksLabel(slot.marks)})</span>
        )}
      </div>
      {useRightColumnMarks && <span className="paper-marks">{slot.marks}</span>}
    </li>
  );
}

function QuestionContent({
  question,
  slot,
  marksPlacement,
  mcqLayout,
}: {
  question: DocQuestion;
  slot: DocSlot;
  marksPlacement: string;
  mcqLayout: string;
}) {
  const overrides = slot.overrides?.regions ?? {};
  const fallbackStem = [{ type: 'paragraph', text: question.rawText }];

  return (
    <>
      {renderRegion('passage', question.content.passage, overrides)}
      {renderRegion('assertion', question.content.assertion, overrides)}
      {renderRegion('reason', question.content.reason, overrides)}
      {renderRegion('stem', question.content.stem ?? fallbackStem, overrides)}
      {question.content.options && (
        <ol
          className={
            mcqLayout === 'two_column'
              ? 'paper-options paper-options-two-column'
              : 'paper-options'
          }
        >
          {question.content.options.map((option) => (
            <PrintOption
              key={option.label}
              option={option}
              overrides={overrides}
            />
          ))}
        </ol>
      )}
      {question.content.subparts?.map((subpart) => (
        <PrintSubQuestion
          key={subpart.label}
          subpart={subpart}
          overrides={overrides}
          marksPlacement={marksPlacement}
        />
      ))}
      {question.content.choices?.map((choice, index) => (
        <PrintChoiceGroup
          key={index}
          choice={choice}
          groupIndex={index}
          overrides={overrides}
        />
      ))}
    </>
  );
}

function PrintOption({
  option,
  overrides,
}: {
  option: ChoiceOption;
  overrides: Record<string, ContentItem[]>;
}) {
  return (
    <li>
      <span>({option.label})</span>
      <div className="paper-option-body">
        <PaperContentItems
          items={overrides[`option:${option.label}`] ?? option.content}
        />
      </div>
    </li>
  );
}

function PrintSubQuestion({
  subpart,
  overrides,
  marksPlacement,
}: {
  subpart: SubQuestion;
  overrides: Record<string, ContentItem[]>;
  marksPlacement: string;
}) {
  const useRightColumnMarks = marksPlacement === 'right_column';

  return (
    <div
      className={
        useRightColumnMarks
          ? 'paper-subquestion'
          : 'paper-subquestion paper-subquestion-inline-marks'
      }
    >
      <span>{subpart.label}.</span>
      <div className="paper-subquestion-body">
        <PaperContentItems
          items={
            overrides[`subpart:${subpart.label}`] ??
            overrides[`subquestion:${subpart.label}`] ??
            subpart.content
          }
        />
        {!useRightColumnMarks && subpart.marks && (
          <span className="paper-inline-marks">
            ({marksLabel(subpart.marks)})
          </span>
        )}
      </div>
      {useRightColumnMarks && subpart.marks && <b>{subpart.marks}</b>}
    </div>
  );
}

function PrintChoiceGroup({
  choice,
  groupIndex,
  overrides,
}: {
  choice: ChoiceGroup;
  groupIndex: number;
  overrides: Record<string, ContentItem[]>;
}) {
  return (
    <div className="paper-choice-group">
      {choice.options.map((option, index) => (
        <div key={option.label}>
          {index > 0 && <strong>OR</strong>}
          <PaperContentItems
            items={
              overrides[`choice:${groupIndex}:${option.label}`] ??
              option.content
            }
          />
        </div>
      ))}
    </div>
  );
}

function renderRegion(
  regionKey: string,
  items: ContentItem[] | undefined,
  overrides: Record<string, ContentItem[]>,
) {
  const content = overrides[regionKey] ?? items;
  if (!content?.length) return null;

  return <PaperContentItems items={content} />;
}

function PaperContentItems({ items }: { items: ContentItem[] }) {
  return (
    <>
      {items.map((item, index) => (
        <PaperContentItem key={index} item={item} />
      ))}
    </>
  );
}

function PaperContentItem({ item }: { item: ContentItem }) {
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

function chromeBlock(
  paper: PaperDocument,
  role: string,
): EditableTextBlock | undefined {
  return paper.paper.chromeBlocks?.find((block) => block.role === role);
}

function toRoman(value: number) {
  const numerals = [
    'I',
    'II',
    'III',
    'IV',
    'V',
    'VI',
    'VII',
    'VIII',
    'IX',
    'X',
  ];
  return numerals[value - 1] ?? String(value);
}

function marksLabel(marks: number) {
  return `${marks} mark${marks === 1 ? '' : 's'}`;
}
