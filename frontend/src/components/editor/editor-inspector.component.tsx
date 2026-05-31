/**
 * Right-side inspector for selected Paper Slot details and alternatives.
 *
 * The inspector owns formatting and restore affordances for selected Question
 * metadata. The editor page passes already-derived Slot and Question data.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `src/lib/editor-paper.ts`, `src/types`.
 *
 * @module EditorInspector
 */
import { RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type {
  EditorQuestionAlternativeView,
  EditorPaperSlotView,
} from '@/lib/editor-paper';
import type { DocQuestion } from '@/types';
import type { AlternativesIntent, InspectorMode } from './editor-types';

export function EditorInspector({
  selectedSlot,
  selectedQuestion,
  inspectorMode,
  alternativesIntent,
  onInspectorModeChange,
  onShowAllAlternatives,
  onUseAlternative,
  onRestoreSelectedSlot,
}: {
  selectedSlot?: EditorPaperSlotView;
  selectedQuestion?: DocQuestion;
  inspectorMode: InspectorMode;
  alternativesIntent: AlternativesIntent;
  onInspectorModeChange: (mode: InspectorMode) => void;
  onShowAllAlternatives: () => void;
  onUseAlternative: (questionId: string) => void;
  onRestoreSelectedSlot: () => void;
}) {
  return (
    <aside
      data-editor-chrome
      className="editor-inspector sticky top-[4.5rem] h-[calc(100vh-6rem)] overflow-auto rounded-lg border bg-background p-4"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Inspector</h2>
        {selectedSlot && selectedQuestion && (
          <div
            className="flex rounded-md border bg-secondary p-0.5"
            aria-label="Inspector mode"
          >
            <Button
              type="button"
              variant={inspectorMode === 'info' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => onInspectorModeChange('info')}
            >
              Info
            </Button>
            <Button
              type="button"
              variant={inspectorMode === 'alternatives' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => onInspectorModeChange('alternatives')}
            >
              Alternatives
            </Button>
          </div>
        )}
      </div>
      {selectedSlot && selectedQuestion ? (
        inspectorMode === 'info' ? (
          <QuestionInfoPanel
            selectedSlot={selectedSlot}
            selectedQuestion={selectedQuestion}
            onRestoreSelectedSlot={onRestoreSelectedSlot}
          />
        ) : (
          <AlternativesPanel
            selectedSlot={selectedSlot}
            alternativesIntent={alternativesIntent}
            onShowAllAlternatives={onShowAllAlternatives}
            onUseAlternative={onUseAlternative}
          />
        )
      ) : (
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Select a question to inspect source, chapter, difficulty, and safe
          swap options.
        </p>
      )}
    </aside>
  );
}

function QuestionInfoPanel({
  selectedSlot,
  selectedQuestion,
  onRestoreSelectedSlot,
}: {
  selectedSlot: EditorPaperSlotView;
  selectedQuestion: DocQuestion;
  onRestoreSelectedSlot: () => void;
}) {
  return (
    <div className="mt-4 space-y-4 text-sm">
      <div>
        <p className="text-xs text-muted-foreground">
          Question {selectedSlot.displayNumber}
        </p>
        <p className="mt-1 font-medium">{selectedQuestion.rawText}</p>
      </div>
      <dl className="space-y-3">
        <div>
          <dt className="text-xs text-muted-foreground">Marks</dt>
          <dd>{selectedSlot.marksLabel}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Type</dt>
          <dd>{formatQuestionType(selectedSlot.questionType)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Chapter</dt>
          <dd>
            {selectedQuestion.metadata.chapterNames.join(', ') || 'Not tagged'}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Topics</dt>
          <dd>
            {selectedQuestion.metadata.topicNames?.join(', ') || 'Not tagged'}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Difficulty</dt>
          <dd>{selectedQuestion.metadata.difficulty}</dd>
        </div>
        {formatRelevance(selectedQuestion.metadata.cbseRelevance) && (
          <div>
            <dt className="text-xs text-muted-foreground">CBSE relevance</dt>
            <dd>{formatRelevance(selectedQuestion.metadata.cbseRelevance)}</dd>
          </div>
        )}
        <div>
          <dt className="text-xs text-muted-foreground">Source</dt>
          <dd>{selectedQuestion.source.sourceName}</dd>
          {sourceDetails(selectedQuestion.source).length > 0 && (
            <dd className="text-xs text-muted-foreground">
              {sourceDetails(selectedQuestion.source).join(' · ')}
            </dd>
          )}
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Lock state</dt>
          <dd>{selectedSlot.locked ? 'Locked' : 'Unlocked'}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Modified state</dt>
          <dd>
            {selectedSlot.modifiedFromSource
              ? 'Modified from source'
              : 'Original source text'}
          </dd>
        </div>
      </dl>
      <Button
        variant="outline"
        size="sm"
        className="w-full"
        disabled={!selectedSlot.modifiedFromSource}
        onMouseDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onRestoreSelectedSlot();
        }}
        onClick={(event) => {
          event.stopPropagation();
          onRestoreSelectedSlot();
        }}
      >
        <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
        Restore original
      </Button>
    </div>
  );
}

function AlternativesPanel({
  selectedSlot,
  alternativesIntent,
  onShowAllAlternatives,
  onUseAlternative,
}: {
  selectedSlot: EditorPaperSlotView;
  alternativesIntent: AlternativesIntent;
  onShowAllAlternatives: () => void;
  onUseAlternative: (questionId: string) => void;
}) {
  return (
    <div className="mt-4 space-y-3 text-sm">
      <div>
        <p className="font-medium">{alternativesHeading(alternativesIntent)}</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          {selectedSlot.locked
            ? 'Unlock this question before replacing it.'
            : `${selectedSlot.alternateQuestions.length} slot-safe option${selectedSlot.alternateQuestions.length === 1 ? '' : 's'}`}
        </p>
      </div>
      {selectedSlot.alternateQuestions.length > 0 ? (
        <div className="space-y-2">
          {selectedSlot.alternateQuestions.map((alternative) => (
            <AlternativeCard
              key={alternative.questionId}
              alternative={alternative}
              disabled={selectedSlot.locked}
              onUseAlternative={onUseAlternative}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2 rounded-md border p-3">
          <p className="text-muted-foreground">
            No slot-safe alternatives match this filter.
          </p>
          <div className="flex flex-col gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onShowAllAlternatives}
            >
              Show all alternatives
            </Button>
            <Button type="button" variant="outline" size="sm" disabled>
              Find more in question bank
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function AlternativeCard({
  alternative,
  disabled,
  onUseAlternative,
}: {
  alternative: EditorQuestionAlternativeView;
  disabled: boolean;
  onUseAlternative: (questionId: string) => void;
}) {
  const relevance = formatRelevance(alternative.cbseRelevance);

  return (
    <div className="rounded-md border p-3">
      <p className="font-medium leading-5">{alternative.questionText}</p>
      <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
        <MetadataChip>{`${alternative.marks} marks`}</MetadataChip>
        <MetadataChip>
          {formatQuestionType(alternative.questionType)}
        </MetadataChip>
        <MetadataChip>{alternative.difficulty}</MetadataChip>
        {relevance && <MetadataChip>{`${relevance} relevance`}</MetadataChip>}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
        {alternative.chapterNames.map((chapterName) => (
          <MetadataChip key={chapterName}>{chapterName}</MetadataChip>
        ))}
        {alternative.topicNames.map((topicName) => (
          <MetadataChip key={topicName}>{topicName}</MetadataChip>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        {alternative.sourceName}
      </p>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mt-3 w-full"
        disabled={disabled}
        onClick={() => onUseAlternative(alternative.questionId)}
      >
        Use this question
      </Button>
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

function sourceDetails(source: {
  fileName?: string;
  pageNumber?: number;
  originalQuestionNumber?: string;
}) {
  return [
    source.fileName,
    source.pageNumber ? `p. ${source.pageNumber}` : undefined,
    source.originalQuestionNumber
      ? `Q${source.originalQuestionNumber}`
      : undefined,
  ].filter((value): value is string => Boolean(value));
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
