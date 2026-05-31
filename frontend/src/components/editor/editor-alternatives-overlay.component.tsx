/**
 * Full-screen alternatives picker for a selected Paper Slot.
 *
 * The overlay gives slot-safe replacement candidates enough space for
 * comparison while keeping the editor paper in the background.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `src/lib/editor-paper.ts`, `src/types`.
 *
 * @module EditorAlternativesOverlay
 */
import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { AlertTriangle, Search, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type {
  EditorQuestionAlternativeView,
  EditorPaperSlotView,
} from '@/lib/editor-paper';
import type { DocQuestion } from '@/types';
import type { AlternativesIntent } from './editor-types';

export function EditorAlternativesOverlay({
  selectedSlot,
  selectedQuestion,
  alternativesIntent,
  onAlternativesIntentChange,
  onClose,
  onUseAlternative,
}: {
  selectedSlot: EditorPaperSlotView;
  selectedQuestion: DocQuestion;
  alternativesIntent: AlternativesIntent;
  onAlternativesIntentChange: (intent: AlternativesIntent) => void;
  onClose: () => void;
  onUseAlternative: (questionId: string) => void;
}) {
  const alternatives = selectedSlot.alternateQuestions;
  const [confirmingQuestionId, setConfirmingQuestionId] = useState<
    string | null
  >(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

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

  function handleUseAlternative(questionId: string) {
    if (
      selectedSlot.modifiedFromSource &&
      confirmingQuestionId !== questionId
    ) {
      setConfirmingQuestionId(questionId);
      return;
    }
    onUseAlternative(questionId);
  }

  return (
    <div
      data-editor-chrome
      className="fixed inset-0 z-40 bg-foreground/45 p-4 max-sm:p-0"
      role="dialog"
      aria-modal="true"
      aria-labelledby="alternatives-title"
      ref={dialogRef}
      onKeyDown={handleKeyDown}
    >
      <div className="mx-auto flex h-full max-w-6xl flex-col overflow-hidden rounded-lg border bg-background shadow-[0_12px_28px_rgba(15,23,42,0.18)] max-sm:rounded-none">
        <header className="flex flex-wrap items-start justify-between gap-3 border-b px-5 py-4">
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">
              Question {selectedSlot.displayNumber} replacement
            </p>
            <h2 id="alternatives-title" className="mt-1 text-lg font-semibold">
              {alternativesHeading(alternativesIntent)}
            </h2>
          </div>
          <Button
            ref={closeButtonRef}
            type="button"
            variant="ghost"
            size="sm"
            aria-label="Close alternatives"
            onClick={onClose}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-[17rem_minmax(0,1fr)] max-lg:grid-cols-1">
          <aside className="border-r bg-secondary/70 p-4 max-lg:border-b max-lg:border-r-0">
            <div className="space-y-4">
              <div>
                <p className="text-xs font-medium text-muted-foreground">
                  Current question
                </p>
                <p className="mt-1 text-sm font-medium leading-6">
                  {selectedQuestion.rawText}
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5 text-xs">
                <MetadataChip>{selectedSlot.marksLabel}</MetadataChip>
                <MetadataChip>
                  {formatQuestionType(selectedSlot.questionType)}
                </MetadataChip>
                <MetadataChip>
                  {selectedQuestion.metadata.difficulty}
                </MetadataChip>
              </div>
              <MetadataList
                label="Chapter"
                values={selectedQuestion.metadata.chapterNames}
              />
              <MetadataList
                label="Topics"
                values={selectedQuestion.metadata.topicNames ?? []}
              />
            </div>
          </aside>

          <main className="flex min-h-0 flex-col">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3">
              <div className="flex flex-wrap items-center gap-3">
                <div
                  className="flex rounded-md border bg-secondary p-0.5"
                  aria-label="Alternative filter"
                >
                  {(['swap', 'easier', 'harder'] as const).map((intent) => (
                    <Button
                      key={intent}
                      type="button"
                      variant={
                        alternativesIntent === intent ? 'default' : 'ghost'
                      }
                      size="sm"
                      className="h-8 px-3 text-xs"
                      aria-pressed={alternativesIntent === intent}
                      onClick={() => onAlternativesIntentChange(intent)}
                    >
                      {filterLabel(intent)}
                    </Button>
                  ))}
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                {selectedSlot.locked
                  ? 'Unlock this question before replacing it.'
                  : `${alternatives.length} slot-safe option${alternatives.length === 1 ? '' : 's'}`}
              </p>
            </div>

            <div className="min-h-0 flex-1 overflow-auto p-5">
              {alternatives.length > 0 ? (
                <div className="grid grid-cols-[repeat(auto-fit,minmax(18rem,1fr))] gap-3">
                  {alternatives.map((alternative) => (
                    <AlternativeCard
                      key={alternative.questionId}
                      alternative={alternative}
                      disabled={selectedSlot.locked}
                      requiresEditClearance={selectedSlot.modifiedFromSource}
                      confirming={
                        confirmingQuestionId === alternative.questionId
                      }
                      onRequestConfirmation={() =>
                        setConfirmingQuestionId(alternative.questionId)
                      }
                      onCancelConfirmation={() => setConfirmingQuestionId(null)}
                      onUseAlternative={handleUseAlternative}
                    />
                  ))}
                </div>
              ) : (
                <EmptyAlternatives
                  alternativesIntent={alternativesIntent}
                  onShowAllAlternatives={() =>
                    onAlternativesIntentChange('swap')
                  }
                />
              )}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

function AlternativeCard({
  alternative,
  disabled,
  requiresEditClearance,
  confirming,
  onRequestConfirmation,
  onCancelConfirmation,
  onUseAlternative,
}: {
  alternative: EditorQuestionAlternativeView;
  disabled: boolean;
  requiresEditClearance: boolean;
  confirming: boolean;
  onRequestConfirmation: () => void;
  onCancelConfirmation: () => void;
  onUseAlternative: (questionId: string) => void;
}) {
  const relevance = formatRelevance(alternative.cbseRelevance);
  const replaceButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (confirming) {
      replaceButtonRef.current?.focus();
    }
  }, [confirming]);

  return (
    <article className="flex min-h-[18rem] flex-col rounded-lg border bg-background p-4">
      <p className="text-sm font-medium leading-6">
        {alternative.questionText}
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
        <MetadataChip>{`${alternative.marks} marks`}</MetadataChip>
        <MetadataChip>
          {formatQuestionType(alternative.questionType)}
        </MetadataChip>
        <MetadataChip>{alternative.difficulty}</MetadataChip>
        {relevance && <MetadataChip>{`${relevance} relevance`}</MetadataChip>}
      </div>
      <div className="mt-3 space-y-2">
        <MetadataList label="Chapter" values={alternative.chapterNames} />
        <MetadataList label="Topics" values={alternative.topicNames} />
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        {alternative.sourceName}
      </p>
      <div className="mt-auto pt-4">
        {confirming ? (
          <div className="rounded-md border bg-secondary/70 p-3">
            <div className="flex gap-2">
              <AlertTriangle
                className="mt-0.5 h-4 w-4 flex-none text-muted-foreground"
                aria-hidden="true"
              />
              <p className="text-xs leading-5">
                This slot has manual edits. Replacing the question will clear
                those edits.
              </p>
            </div>
            <div className="mt-3 flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={onCancelConfirmation}
              >
                Keep edits
              </Button>
              <Button
                ref={replaceButtonRef}
                type="button"
                size="sm"
                className="flex-1"
                onClick={() => onUseAlternative(alternative.questionId)}
              >
                Replace and clear
              </Button>
            </div>
          </div>
        ) : (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full"
            disabled={disabled}
            onClick={() =>
              requiresEditClearance
                ? onRequestConfirmation()
                : onUseAlternative(alternative.questionId)
            }
          >
            Use this question
          </Button>
        )}
      </div>
    </article>
  );
}

function EmptyAlternatives({
  alternativesIntent,
  onShowAllAlternatives,
}: {
  alternativesIntent: AlternativesIntent;
  onShowAllAlternatives: () => void;
}) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center rounded-lg border bg-secondary/60 p-6 text-center">
      <Search className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
      <p className="mt-3 text-sm font-medium">
        No {filterLabel(alternativesIntent).toLowerCase()} alternatives match
        this slot.
      </p>
      <p className="mt-1 text-sm leading-6 text-muted-foreground">
        The slot is still protected. You can return to every provided alternate,
        or wait for question-bank search in a later slice.
      </p>
      <div className="mt-4 flex w-full flex-col gap-2">
        <Button type="button" variant="outline" onClick={onShowAllAlternatives}>
          Show all alternatives
        </Button>
        <Button type="button" variant="outline" disabled>
          Find more in question bank
        </Button>
      </div>
    </div>
  );
}

function MetadataList({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
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

function formatQuestionType(questionType: string) {
  return questionType.replace(/_/g, ' ');
}

function formatRelevance(relevance: string | number | undefined) {
  if (relevance === undefined) return undefined;
  return typeof relevance === 'number' ? `${relevance}/100` : relevance;
}

function filterLabel(intent: AlternativesIntent) {
  switch (intent) {
    case 'topic':
      return 'Topic';
    case 'easier':
      return 'Easier';
    case 'harder':
      return 'Harder';
    default:
      return 'Swap';
  }
}

function alternativesHeading(intent: AlternativesIntent) {
  switch (intent) {
    case 'topic':
      return 'Topic alternatives';
    case 'easier':
      return 'Easier alternatives';
    case 'harder':
      return 'Harder alternatives';
    default:
      return 'Swap alternatives';
  }
}
