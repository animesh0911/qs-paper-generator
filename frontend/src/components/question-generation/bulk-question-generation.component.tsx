import type {
  Chapter,
  ChapterTopicNode,
  GenerationBatch,
  GenerationBatchStatus,
  GeneratedQuestionCandidate,
} from '@/types';
import { Check, LoaderCircle, MousePointer2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { shouldShowNoValidQuestionsMessage } from '@/lib/question-generation';
import { CandidateReviewPanel } from './candidate-review-panel.component';

const ACTIVE_GENERATION_STATUSES: GenerationBatch['status'][] = [
  'queued',
  'generating_questions',
  'validating',
];

const MAX_GENERATION_DRAFTS_TO_SHOW = 3;

// Placeholder chapters shown (disabled) so teachers can see that AI Q&A
// generation will expand to the rest of the NCERT Class 10 Science syllabus.
// These are not yet wired to any content and cannot be selected.
const UPCOMING_CHAPTERS: { order: number; name: string }[] = [
  { order: 1, name: 'Chemical Reactions and Equations' },
  { order: 2, name: 'Acids, Bases and Salts' },
  { order: 3, name: 'Metals and Non-metals' },
  { order: 5, name: 'Life Processes' },
  { order: 6, name: 'Control and Coordination' },
  { order: 7, name: 'How do Organisms Reproduce?' },
  { order: 8, name: 'Heredity' },
  { order: 9, name: 'Light – Reflection and Refraction' },
  { order: 11, name: 'Electricity' },
  { order: 12, name: 'Magnetic Effects of Electric Current' },
  { order: 13, name: 'Our Environment' },
];

export interface BulkQuestionGenerationSetupProps {
  batches?: GenerationBatch[];
  batchesLoading?: boolean;
  batchesError?: string;
  chapters: Chapter[];
  chaptersLoading: boolean;
  chaptersError: string;
  selectedChapterSlug: string;
  topics: ChapterTopicNode[];
  topicsLoading: boolean;
  topicsError: string;
  selectedTopicIds: Set<string>;
  busy: boolean;
  error: string;
  activeBatchId?: number | null;
  onSelectChapter: (slug: string) => void;
  onToggleTopic: (nodeId: string) => void;
  onClearTopics: () => void;
  onStart: () => void;
  onOpenActiveBatch?: () => void;
  onOpenBatch?: (batchId: number) => void;
  onRetryBatch?: (batchId: number) => void;
  onDiscardBatch?: (batchId: number) => void;
}

function formatTopicTitle(title: string): string {
  const match = title.match(/^(\d+(?:\.\d+)*\s+)(.*)$/);
  if (!match) return title;

  const [, numberPrefix, body] = match;
  if (body !== body.toUpperCase()) return title;

  const smallWords = new Set([
    'and',
    'be',
    'for',
    'in',
    'its',
    'of',
    'the',
    'to',
  ]);
  const words = body.toLowerCase().split(' ');
  const formatted = words
    .map((word, index) => {
      if (word === '-') return word;
      const followsDash = index > 0 && words[index - 1] === '-';
      if (index > 0 && !followsDash && smallWords.has(word)) return word;
      return word.replace(/^[a-z]/, (letter) => letter.toUpperCase());
    })
    .join(' ');

  return `${numberPrefix}${formatted}`;
}

export function BulkQuestionGenerationSetup({
  batches = [],
  batchesLoading = false,
  batchesError = '',
  chapters,
  chaptersLoading,
  chaptersError,
  selectedChapterSlug,
  topics,
  topicsLoading,
  topicsError,
  selectedTopicIds,
  busy,
  error,
  activeBatchId = null,
  onSelectChapter,
  onToggleTopic,
  onClearTopics,
  onStart,
  onOpenActiveBatch,
  onOpenBatch,
  onRetryBatch,
  onDiscardBatch,
}: BulkQuestionGenerationSetupProps) {
  const selectedTopicCount = selectedTopicIds.size;
  const selectedChapter = chapters.find(
    (chapter) => chapter.slug === selectedChapterSlug,
  );
  const canStart =
    Boolean(selectedChapterSlug) && selectedTopicCount > 0 && !busy;
  const reviewableBatches = batches
    .filter((batch) =>
      [
        'queued',
        'generating_questions',
        'validating',
        'ready_for_review',
        // Keep failures visible: a batch that died mid-generation must not
        // silently vanish from the list — the teacher needs to see it failed and
        // open the reason, not wonder where their generation went.
        'failed',
      ].includes(batch.status),
    )
    .slice(0, MAX_GENERATION_DRAFTS_TO_SHOW);

  return (
    <div className="space-y-5 rounded-lg border border-white/70 bg-white/55 p-4">
      {(batchesLoading || batchesError || reviewableBatches.length > 0) && (
        <section className="space-y-3 rounded-lg border border-white/70 bg-white/60 p-3">
          <div>
            <p className="text-sm font-medium">Generation drafts</p>
            <p className="mt-1 text-sm leading-5 text-muted-foreground">
              Return to an in-progress batch or review generated Q&amp;A that is
              ready.
            </p>
          </div>
          {batchesLoading && (
            <p className="text-sm text-muted-foreground">
              Checking for drafts…
            </p>
          )}
          {batchesError && (
            <p className="text-sm text-muted-foreground" role="alert">
              {batchesError}
            </p>
          )}
          {reviewableBatches.length > 0 && (
            <ul className="space-y-2">
              {reviewableBatches.map((batch) => {
                const ready = batch.status === 'ready_for_review';
                const failed = batch.status === 'failed';
                const statusLabel = ready
                  ? 'Ready for review'
                  : failed
                    ? 'Failed'
                    : 'Generating';
                const detail = ready
                  ? `${batch.candidate_count} candidate${batch.candidate_count === 1 ? '' : 's'} ready`
                  : failed
                    ? batch.error ||
                      'Generation failed. Open for details, or start a new batch.'
                    : 'We’ll update this when candidates are ready.';
                return (
                  <li
                    key={batch.id}
                    className="flex flex-col gap-2 rounded-lg border border-white/70 bg-white/70 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <span className="text-sm leading-5">
                      <span className="font-medium">
                        Batch #{batch.id} · {statusLabel}
                      </span>
                      <span
                        className={cn(
                          'block',
                          failed ? 'text-destructive' : 'text-muted-foreground',
                        )}
                      >
                        {detail}
                      </span>
                    </span>
                    {failed ? (
                      <span className="flex shrink-0 items-center gap-2">
                        {onRetryBatch && (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => onRetryBatch(batch.id)}
                          >
                            Retry
                          </Button>
                        )}
                        {onDiscardBatch && (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => onDiscardBatch(batch.id)}
                          >
                            Remove
                          </Button>
                        )}
                      </span>
                    ) : (
                      onOpenBatch && (
                        <Button
                          type="button"
                          size="sm"
                          variant={ready ? 'default' : 'outline'}
                          onClick={() => onOpenBatch(batch.id)}
                        >
                          {ready ? 'Review draft' : 'View progress'}
                        </Button>
                      )
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
      <section
        className="space-y-3"
        aria-labelledby="generation-chapter-heading"
      >
        <div className="space-y-1">
          <p
            id="generation-chapter-heading"
            className="text-[0.8125rem] font-medium leading-5"
          >
            NCERT Chapter
          </p>
        </div>

        {chaptersLoading && (
          <p className="border-t pt-3 text-sm">Loading Chapters…</p>
        )}

        {!chaptersLoading && chaptersError && (
          <div className="border-t pt-3" role="alert">
            <p className="text-sm font-medium">Chapters could not be loaded.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {chaptersError}
            </p>
          </div>
        )}

        {!chaptersLoading && !chaptersError && chapters.length === 0 && (
          <p className="border-t pt-3 text-sm">
            No Chapters are available for generation yet.
          </p>
        )}

        {chapters.length > 0 && (
          <div
            className="grid gap-2 sm:grid-cols-2"
            role="radiogroup"
            aria-label="NCERT Chapter"
          >
            {chapters.map((chapter) => {
              const chapterInputId = `generation-chapter-${chapter.slug}`;
              const selected = selectedChapterSlug === chapter.slug;
              return (
                <label
                  key={chapter.slug}
                  htmlFor={chapterInputId}
                  className={
                    selected
                      ? 'flex cursor-pointer items-start gap-3 rounded-lg border border-primary bg-white/90 px-3 py-3 text-sm leading-5 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring'
                      : 'flex cursor-pointer items-start gap-3 rounded-lg border border-white/70 bg-white/65 px-3 py-3 text-sm leading-5 transition-colors hover:bg-white/90 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring'
                  }
                >
                  <input
                    id={chapterInputId}
                    type="radio"
                    name="generation-chapter"
                    className="sr-only"
                    checked={selected}
                    onChange={() => onSelectChapter(chapter.slug)}
                  />
                  <span
                    className={
                      selected
                        ? 'mt-0.5 flex size-5 items-center justify-center rounded-md bg-primary text-primary-foreground'
                        : 'mt-0.5 flex size-5 items-center justify-center rounded-md border bg-white text-transparent'
                    }
                    aria-hidden="true"
                  >
                    <Check className="size-3.5" />
                  </span>
                  <span className="min-w-0">
                    <span className="block font-medium">
                      Chapter {chapter.order}: {chapter.name}
                    </span>
                  </span>
                </label>
              );
            })}

            {UPCOMING_CHAPTERS.map((chapter) => (
              <div
                key={`upcoming-${chapter.order}`}
                aria-disabled="true"
                title="Coming soon"
                className="flex cursor-not-allowed items-start gap-3 rounded-lg border border-dashed border-white/70 bg-white/30 px-3 py-3 text-sm leading-5 opacity-60"
              >
                <span
                  className="mt-0.5 flex size-5 items-center justify-center rounded-md border bg-white/50 text-transparent"
                  aria-hidden="true"
                >
                  <Check className="size-3.5" />
                </span>
                <span className="min-w-0">
                  <span className="block font-medium text-muted-foreground">
                    Chapter {chapter.order}: {chapter.name}
                  </span>
                  <span className="mt-0.5 inline-flex items-center rounded-sm bg-secondary px-1.5 py-0.5 text-xs font-medium text-secondary-foreground">
                    Coming soon
                  </span>
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {selectedChapterSlug && (
        <section
          className="space-y-3 border-t border-white/70 pt-4"
          aria-labelledby="generation-topics-heading"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1">
              <p
                id="generation-topics-heading"
                className="text-[0.8125rem] font-medium leading-5"
              >
                Topics{selectedChapter ? ` — ${selectedChapter.name}` : ''}
              </p>
              <p className="text-sm leading-5 text-muted-foreground">
                {selectedTopicCount === 0
                  ? 'Select at least one topic.'
                  : `${selectedTopicCount} topic${selectedTopicCount === 1 ? '' : 's'} selected for generation.`}
              </p>
            </div>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onClearTopics}
              disabled={selectedTopicCount === 0}
            >
              <X className="mr-1.5 size-3.5" aria-hidden="true" />
              Clear topics
            </Button>
          </div>

          {topicsLoading && (
            <div className="grid gap-2 sm:grid-cols-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  className="h-16 animate-pulse rounded-lg border border-white/70 bg-white/55"
                />
              ))}
            </div>
          )}

          {!topicsLoading && topicsError && (
            <div role="alert">
              <p className="text-sm font-medium">Topics could not be loaded.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {topicsError}
              </p>
            </div>
          )}

          {!topicsLoading && !topicsError && topics.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No NCERT topic metadata is available for this Chapter yet.
            </p>
          )}

          {!topicsLoading && !topicsError && topics.length > 0 && (
            <ul className="grid max-h-80 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
              {topics.map((topic) => {
                const topicInputId = `topic-${topic.id}`;
                const selected = selectedTopicIds.has(topic.id);
                return (
                  <li key={topic.id}>
                    <label
                      htmlFor={topicInputId}
                      className={
                        selected
                          ? 'flex h-full cursor-pointer items-start gap-3 rounded-lg border border-primary bg-white/90 px-3 py-3 text-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring'
                          : 'flex h-full cursor-pointer items-start gap-3 rounded-lg border border-white/70 bg-white/65 px-3 py-3 text-sm transition-colors hover:bg-white/90 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring'
                      }
                    >
                      <input
                        id={topicInputId}
                        type="checkbox"
                        className="sr-only"
                        checked={selectedTopicIds.has(topic.id)}
                        onChange={() => onToggleTopic(topic.id)}
                      />
                      <span
                        className={
                          selected
                            ? 'mt-0.5 flex size-5 items-center justify-center rounded-md bg-primary text-primary-foreground'
                            : 'mt-0.5 flex size-5 items-center justify-center rounded-md border bg-white text-transparent'
                        }
                        aria-hidden="true"
                      >
                        <Check className="size-3.5" />
                      </span>
                      <span className="min-w-0 font-medium leading-snug">
                        {formatTopicTitle(topic.title)}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      {!selectedChapterSlug && (
        <div className="flex items-center gap-2 rounded-lg border border-white/70 bg-white/50 px-3 py-2 text-sm leading-5 text-muted-foreground">
          <MousePointer2 className="size-4 flex-none" aria-hidden="true" />
          Select a chapter to show topics.
        </div>
      )}

      {error && (
        <div className="space-y-3 border-t border-white/70 pt-4" role="alert">
          <div>
            <p className="text-sm font-medium">
              {activeBatchId
                ? 'Q&A generation is already running.'
                : 'Generation could not start.'}
            </p>
            <p className="mt-1 text-sm leading-5 text-muted-foreground">
              {activeBatchId
                ? `Batch #${activeBatchId} is preparing questions now.`
                : error}
            </p>
          </div>
          {activeBatchId && onOpenActiveBatch && (
            <Button type="button" size="sm" onClick={onOpenActiveBatch}>
              View progress
            </Button>
          )}
        </div>
      )}

      <div className="flex flex-col gap-2 border-t border-white/70 pt-4 sm:flex-row sm:items-center">
        <Button type="button" onClick={onStart} disabled={!canStart}>
          {busy ? 'Starting generation…' : 'Generate AI Q&A'}
        </Button>
        {!canStart && !busy && (
          <p className="text-sm leading-5 text-muted-foreground">
            Select a chapter and at least one topic.
          </p>
        )}
      </div>
    </div>
  );
}

export interface GenerationProgressWorkspaceProps {
  batch: GenerationBatch | null;
  loading: boolean;
  error: string;
  lastCheckedAt: string;
  pollIntervalMs: number;
  candidates: GeneratedQuestionCandidate[];
  candidatesLoading: boolean;
  candidatesError: string;
  onRunInBackground: () => void;
  onTryAgain: () => void;
  accepting: boolean;
  acceptError: string;
  initialRejectedCandidateIds?: number[];
  onAcceptCandidates: (acceptedCandidateIds: number[]) => void;
  onRetryCandidates: () => void;
  onBackToPaperSetup: () => void;
  discarding?: boolean;
  discardError?: string;
  onGenerateAnother?: () => void;
}

function isActiveGenerationStatus(status: GenerationBatch['status']): boolean {
  return ACTIVE_GENERATION_STATUSES.includes(status);
}

function progressStageLabel(status: GenerationBatchStatus): string {
  switch (status) {
    case 'queued':
      return 'Preparing';
    case 'generating_questions':
      return 'Drafting Q&A';
    case 'validating':
      return 'Checking';
    case 'ready_for_review':
      return 'Ready to review';
    case 'accepted':
      return 'Imported';
    case 'expired':
      return 'Closed';
    case 'discarded':
      return 'Discarded';
    case 'failed':
      return 'Needs retry';
  }
}

function progressStageDescription(status: GenerationBatchStatus): string {
  switch (status) {
    case 'queued':
      return 'Your request is in line. This usually takes a moment.';
    case 'generating_questions':
      return 'Questions are being drafted from the selected topics.';
    case 'validating':
      return 'The draft is being checked before review.';
    case 'ready_for_review':
      return 'Review the candidates below and import the ones you want.';
    case 'accepted':
      return 'Accepted Q&A has been added to the Question bank.';
    case 'expired':
      return 'This request is no longer active.';
    case 'discarded':
      return 'You discarded this batch. Start a new one any time.';
    case 'failed':
      return 'No usable Q&A was created.';
  }
}

function progressStep(status: GenerationBatchStatus): number {
  switch (status) {
    case 'queued':
      return 0;
    case 'generating_questions':
    case 'validating':
      return 1;
    case 'ready_for_review':
    case 'accepted':
      return 2;
    case 'expired':
    case 'discarded':
    case 'failed':
      return 0;
  }
}

function ActiveGenerationIndicator() {
  return (
    <div
      className="mt-4 flex items-center gap-3 rounded-lg border border-white/70 bg-white/60 px-3 py-2"
      role="status"
      aria-live="polite"
    >
      <span className="relative flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <span
          className="absolute inline-flex size-8 animate-ping rounded-md bg-primary/25 motion-reduce:hidden"
          aria-hidden="true"
        />
        <LoaderCircle
          className="relative size-4 animate-spin motion-reduce:animate-none"
          aria-hidden="true"
        />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium leading-5">
          Q&amp;A generation is in progress
        </span>
        <span className="block text-xs leading-5 text-muted-foreground">
          This will update automatically when review is ready.
        </span>
      </span>
    </div>
  );
}

export function GenerationProgressWorkspace({
  batch,
  loading,
  error,
  candidates,
  candidatesLoading,
  candidatesError,
  accepting,
  acceptError,
  initialRejectedCandidateIds = [],
  onRunInBackground,
  onTryAgain,
  onAcceptCandidates,
  onRetryCandidates,
  onBackToPaperSetup,
  discarding = false,
  discardError = '',
  onGenerateAnother,
}: GenerationProgressWorkspaceProps) {
  const noValidQuestions = batch
    ? shouldShowNoValidQuestionsMessage(batch)
    : false;
  const active = batch ? isActiveGenerationStatus(batch.status) : false;
  const step = batch ? progressStep(batch.status) : 0;
  // On a still-active review batch this discards first; on a settled batch it
  // just returns to the (pre-filled) setup. Either way it frees a queue slot,
  // so the teacher never needs the browser back button to generate again.
  const canGenerateAnother =
    Boolean(onGenerateAnother) &&
    Boolean(batch) &&
    batch?.status !== 'queued' &&
    !active;
  const generateAnotherLabel =
    batch?.status === 'ready_for_review'
      ? 'Discard & generate another'
      : 'Generate another batch';

  return (
    <div className="min-h-screen bg-secondary">
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
        <div className="space-y-6 rounded-lg border border-white/70 bg-white/80 p-5 shadow-none backdrop-blur-2xl sm:p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1.5">
              <h1 className="text-xl font-semibold leading-7">
                Question bank generation
              </h1>
              <p className="max-w-prose text-[0.9375rem] leading-6 text-muted-foreground">
                We’ll prepare the Q&amp;A and bring it here for review.
              </p>
            </div>
            {batch && (
              <span className="inline-flex w-fit rounded-md bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground">
                {progressStageLabel(batch.status)}
              </span>
            )}
          </div>

          {loading && !batch && (
            <p className="text-sm leading-5">Loading generation status…</p>
          )}

          {error && !batch && (
            <div className="border-t pt-4 space-y-3" role="alert">
              <div>
                <p className="text-sm font-medium">
                  We could not load this generation job.
                </p>
                <p className="mt-1 text-sm text-muted-foreground">{error}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={onTryAgain} disabled={loading}>
                  {loading ? 'Trying again…' : 'Try again'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={onBackToPaperSetup}
                >
                  Back to paper setup
                </Button>
              </div>
            </div>
          )}

          {batch && !noValidQuestions && (
            <div className="space-y-5">
              <div className="space-y-4 border-t border-white/70 pt-5">
                <div className="rounded-lg border border-white/70 bg-white/55 p-4">
                  <p className="text-[0.8125rem] font-medium leading-5 text-muted-foreground">
                    Status
                  </p>
                  <p className="mt-1 text-2xl font-semibold leading-8">
                    {progressStageLabel(batch.status)}
                  </p>
                  <p className="mt-2 text-sm leading-5 text-muted-foreground">
                    {progressStageDescription(batch.status)}
                  </p>
                  {active && <ActiveGenerationIndicator />}
                </div>

                <ol
                  className="grid gap-2 sm:grid-cols-3"
                  aria-label="Generation progress"
                >
                  {['Preparing', 'Drafting', 'Review'].map((label, index) => {
                    const complete = index <= step;
                    return (
                      <li
                        key={label}
                        className={
                          complete
                            ? 'rounded-lg border border-primary bg-white/85 px-3 py-2 text-sm font-medium leading-5'
                            : 'rounded-lg border border-white/70 bg-white/45 px-3 py-2 text-sm font-medium leading-5 text-muted-foreground'
                        }
                      >
                        <span
                          className={
                            complete
                              ? 'mr-2 inline-flex size-5 items-center justify-center rounded-md bg-primary text-xs text-primary-foreground'
                              : 'mr-2 inline-flex size-5 items-center justify-center rounded-md border bg-white text-xs'
                          }
                          aria-hidden="true"
                        >
                          {index + 1}
                        </span>
                        {label}
                      </li>
                    );
                  })}
                </ol>
              </div>

              {canGenerateAnother && (
                <div className="flex flex-col gap-2 border-t border-white/70 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={onGenerateAnother}
                    disabled={discarding}
                  >
                    {discarding ? 'Closing this batch…' : generateAnotherLabel}
                  </Button>
                  {discardError && (
                    <p className="text-sm text-muted-foreground" role="alert">
                      {discardError}
                    </p>
                  )}
                </div>
              )}

              {error && (
                <div className="border-t pt-3" role="status">
                  <p className="text-sm font-medium">
                    Latest status check failed.
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">{error}</p>
                </div>
              )}

              {batch.status === 'ready_for_review' && (
                <CandidateReviewPanel
                  candidates={candidates}
                  candidatesLoading={candidatesLoading}
                  candidatesError={candidatesError}
                  accepting={accepting}
                  acceptError={acceptError}
                  initialRejectedCandidateIds={initialRejectedCandidateIds}
                  onAcceptCandidates={onAcceptCandidates}
                  onRetryCandidates={onRetryCandidates}
                />
              )}

              {active && (
                <div className="flex flex-col gap-2 border-t border-white/70 pt-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm leading-5 text-muted-foreground">
                    You can leave this page and come back later.
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={onRunInBackground}
                  >
                    Back to setup
                  </Button>
                </div>
              )}

              {batch.status === 'accepted' && (
                <div className="border-t pt-4 space-y-3">
                  <div>
                    <h2 className="font-medium">Generation batch accepted</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Accepted generated Q&amp;A entered the Question bank.
                      Rejected candidates were not imported.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={onBackToPaperSetup}
                  >
                    Back to paper setup
                  </Button>
                </div>
              )}

              {batch.status === 'expired' && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={onBackToPaperSetup}
                >
                  Back to paper setup
                </Button>
              )}
            </div>
          )}

          {noValidQuestions && (
            <div className="border-t pt-4 space-y-3">
              <div>
                <h2 className="font-medium">
                  No valid Questions were produced
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {batch?.error ||
                    'The generation job finished, but no candidates passed validation.'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {onGenerateAnother && (
                  <Button
                    type="button"
                    onClick={onGenerateAnother}
                    disabled={discarding}
                  >
                    {discarding
                      ? 'Closing this batch…'
                      : 'Generate another batch'}
                  </Button>
                )}
                <Button type="button" variant="outline" onClick={onTryAgain}>
                  Try again
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={onBackToPaperSetup}
                >
                  Back to paper setup
                </Button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
