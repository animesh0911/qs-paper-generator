/**
 * Focused source and metadata drawer for the selected paper Slot.
 *
 * Keeps dense provenance out of the everyday inspector while giving teachers a
 * trustworthy place to verify where a question came from.
 *
 * @module EditorQuestionInfoOverlay
 */
import { useEffect, useRef, type KeyboardEvent, type ReactNode } from 'react';
import {
  BookOpen,
  CheckCircle2,
  Clock3,
  FileText,
  Hash,
  Lock,
  RotateCcw,
  Tag,
  Unlock,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MathContent } from '@/components/math/math-content.component';
import type {
  EditorQuestionContainerBlock,
  EditorPaperSlotView,
} from '@/lib/editor-paper';
import type { DocQuestion } from '@/types';

export function EditorQuestionInfoOverlay({
  selectedSlot,
  selectedQuestion,
  onClose,
  onRestoreSelectedSlot,
}: {
  selectedSlot: EditorPaperSlotView;
  selectedQuestion: DocQuestion;
  onClose: () => void;
  onRestoreSelectedSlot: () => void;
}) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const relevance = formatRelevance(selectedQuestion.metadata.cbseRelevance);
  const sourceRows = sourceDetails(selectedQuestion.source);
  const flags = questionFlags(selectedQuestion);

  useEffect(() => {
    closeButtonRef.current?.focus();
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.preventDefault();
      onClose();
      return;
    }

    if (event.key !== 'Tab' || !dialogRef.current) return;

    const focusableElements = Array.from(
      dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((element) => !element.hasAttribute('disabled'));

    if (focusableElements.length === 0) return;

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    if (event.shiftKey && document.activeElement === firstElement) {
      event.preventDefault();
      lastElement.focus();
    } else if (!event.shiftKey && document.activeElement === lastElement) {
      event.preventDefault();
      firstElement.focus();
    }
  }

  return (
    <div
      data-editor-chrome
      className="fixed inset-0 z-40 bg-foreground/35"
      role="dialog"
      aria-modal="true"
      aria-labelledby="question-info-title"
      ref={dialogRef}
      onKeyDown={handleKeyDown}
    >
      <div className="ml-auto flex h-full w-full max-w-2xl flex-col overflow-hidden border-l bg-background shadow-[0_12px_28px_rgba(15,23,42,0.18)]">
        <header className="flex items-start justify-between gap-3 border-b px-5 py-4">
          <div className="min-w-0">
            <p className="text-xs font-medium text-muted-foreground">
              Question {selectedSlot.displayNumber}
            </p>
            <h2
              id="question-info-title"
              className="mt-1 text-base font-semibold"
            >
              Source and question details
            </h2>
          </div>
          <Button
            ref={closeButtonRef}
            type="button"
            variant="ghost"
            size="sm"
            aria-label="Close question details"
            onClick={onClose}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </header>

        <div className="min-h-0 flex-1 overflow-auto px-5 py-5">
          <section className="rounded-md border bg-secondary/45 p-4">
            <div className="flex items-start gap-3">
              <FileText className="mt-0.5 h-5 w-5 flex-none text-muted-foreground" />
              <div className="min-w-0">
                <p className="text-xs font-medium text-muted-foreground">
                  Source
                </p>
                <p className="mt-1 break-words text-sm font-semibold">
                  {selectedQuestion.source.name}
                </p>
                {sourceRows.length > 0 && (
                  <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                    {sourceRows.map((row) => (
                      <div key={row.label}>
                        <dt className="text-xs font-medium text-muted-foreground">
                          {row.label}
                        </dt>
                        <dd className="mt-0.5 break-words">{row.value}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>
            </div>
          </section>

          <section className="mt-5">
            <p className="text-xs font-medium text-muted-foreground">
              Question text
            </p>
            <QuestionPreview
              questionBlockTree={selectedSlot.questionBlockTree}
              className="mt-2 rounded-md border p-4 text-sm leading-6"
            />
          </section>

          <section className="mt-5 grid gap-3 sm:grid-cols-2">
            <InfoRow
              icon={<Hash className="h-4 w-4" aria-hidden="true" />}
              label="Marks"
              value={selectedSlot.marksLabel}
            />
            <InfoRow
              icon={<Tag className="h-4 w-4" aria-hidden="true" />}
              label="Type"
              value={formatQuestionType(selectedSlot.questionType)}
            />
            <InfoRow
              icon={<BookOpen className="h-4 w-4" aria-hidden="true" />}
              label="Difficulty"
              value={selectedQuestion.metadata.difficulty}
            />
            <InfoRow
              icon={<CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
              label="CBSE relevance"
              value={relevance ?? 'Not scored'}
            />
            <InfoRow
              icon={
                selectedSlot.locked ? (
                  <Lock className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Unlock className="h-4 w-4" aria-hidden="true" />
                )
              }
              label="Lock state"
              value={selectedSlot.locked ? 'Locked' : 'Unlocked'}
            />
            <InfoRow
              icon={<Clock3 className="h-4 w-4" aria-hidden="true" />}
              label="Estimated time"
              value={
                selectedQuestion.metadata.estimatedMinutes
                  ? `${selectedQuestion.metadata.estimatedMinutes} min`
                  : 'Not estimated'
              }
            />
          </section>

          <section className="mt-5 grid gap-4 sm:grid-cols-2">
            <MetadataList
              label="Chapter"
              values={selectedQuestion.metadata.chapterNames}
            />
            <MetadataList
              label="Topics"
              values={selectedQuestion.metadata.topicNames ?? []}
            />
            <MetadataList
              label="Keywords"
              values={selectedQuestion.metadata.keywords ?? []}
            />
            <MetadataList label="Flags" values={flags} />
          </section>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t px-5 py-4">
          <p className="text-xs text-muted-foreground">
            {selectedSlot.modifiedFromSource
              ? 'This slot has manual edits.'
              : 'Showing original source text.'}
          </p>
          <Button
            variant="outline"
            size="sm"
            disabled={!selectedSlot.modifiedFromSource}
            onClick={(event) => {
              event.stopPropagation();
              onRestoreSelectedSlot();
            }}
          >
            <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
            Restore original
          </Button>
        </footer>
      </div>
    </div>
  );
}

function QuestionPreview({
  questionBlockTree,
  className,
}: {
  questionBlockTree: EditorQuestionContainerBlock;
  className?: string;
}) {
  if (questionBlockTree.children.length === 0) {
    return <p className={className}>No question text available.</p>;
  }

  return (
    <div className={className}>
      <div className="space-y-2">
        {questionBlockTree.children.map((region) => (
          <div
            key={region.regionKey}
            className="flex min-w-0 items-start gap-1.5"
          >
            {region.displayPrefix && (
              <span className="flex-none select-none font-semibold">
                {region.displayPrefix}
              </span>
            )}
            <span className="min-w-0 flex-1 whitespace-pre-wrap break-words">
              <MathContent items={region.content} />
            </span>
            {region.displaySuffix && (
              <span className="flex-none select-none text-xs text-muted-foreground">
                {region.displaySuffix}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function InfoRow({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-md border p-3">
      <span className="mt-0.5 text-muted-foreground">{icon}</span>
      <div className="min-w-0">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="mt-0.5 break-words text-sm">{value}</p>
      </div>
    </div>
  );
}

function MetadataList({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs">
        {values.length > 0 ? (
          values.map((value) => (
            <MetadataChip key={value}>{value}</MetadataChip>
          ))
        ) : (
          <span className="text-muted-foreground">Not tagged</span>
        )}
      </div>
    </div>
  );
}

function MetadataChip({ children }: { children: string | number }) {
  return (
    <span className="rounded border bg-secondary px-1.5 py-0.5 text-muted-foreground">
      {children}
    </span>
  );
}

function sourceDetails(source: {
  type: string;
  fileName?: string;
  pageNumber?: number;
  originalQuestionNumber?: string;
}) {
  return [
    { label: 'Type', value: formatSourceType(source.type) },
    source.fileName ? { label: 'File', value: source.fileName } : undefined,
    source.pageNumber
      ? { label: 'Page', value: String(source.pageNumber) }
      : undefined,
    source.originalQuestionNumber
      ? {
          label: 'Original question',
          value: `Q${source.originalQuestionNumber}`,
        }
      : undefined,
  ].filter((value): value is { label: string; value: string } =>
    Boolean(value),
  );
}

function questionFlags(question: DocQuestion) {
  return [
    question.metadata.requiresDiagram ? 'Diagram' : undefined,
    question.metadata.requiresCalculation ? 'Calculation' : undefined,
    question.metadata.requiresTable ? 'Table' : undefined,
    question.metadata.cognitiveLevel
      ? formatQuestionType(question.metadata.cognitiveLevel)
      : undefined,
  ].filter((value): value is string => Boolean(value));
}

function formatQuestionType(questionType: string) {
  return questionType.replace(/_/g, ' ');
}

function formatSourceType(sourceType: string) {
  return sourceType.replace(/_/g, ' ');
}

function formatRelevance(relevance: string | number | undefined) {
  if (relevance === undefined) return undefined;
  return typeof relevance === 'number' ? `${relevance}/100` : relevance;
}
