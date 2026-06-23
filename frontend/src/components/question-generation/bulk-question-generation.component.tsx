import { useState } from 'react';
import type {
  Chapter,
  ChapterTopicNode,
  GenerationBatch,
  GeneratedQuestionCandidate,
  GenerationDifficultyLabel,
} from '@/types';
import { Button } from '@/components/ui/button';
import {
  GENERATION_DIFFICULTIES,
  generationStageDescription,
  generationStageLabel,
  shouldShowNoValidQuestionsMessage,
} from '@/lib/question-generation';
import {
  candidateAnswerText,
  candidateQuestionText,
  candidateReviewCounts,
  candidateTopicLabels,
  toggleRejectedCandidate,
} from './candidate-review';

const ACTIVE_GENERATION_STATUSES: GenerationBatch['status'][] = [
  'queued',
  'generating_questions',
  'validating',
];

export interface BulkQuestionGenerationSetupProps {
  chapters: Chapter[];
  chaptersLoading: boolean;
  chaptersError: string;
  selectedChapterSlug: string;
  topics: ChapterTopicNode[];
  topicsLoading: boolean;
  topicsError: string;
  selectedTopicIds: Set<string>;
  difficulty: GenerationDifficultyLabel;
  busy: boolean;
  error: string;
  onSelectChapter: (slug: string) => void;
  onToggleTopic: (nodeId: string) => void;
  onClearTopics: () => void;
  onDifficultyChange: (difficulty: GenerationDifficultyLabel) => void;
  onStart: () => void;
}

function formatPageRange(topic: ChapterTopicNode): string {
  if (topic.page_range.start === topic.page_range.end) {
    return `p. ${topic.page_range.start}`;
  }
  return `pp. ${topic.page_range.start}–${topic.page_range.end}`;
}

function nodeTypeLabel(type: string): string {
  return type.charAt(0).toUpperCase() + type.slice(1);
}

export function BulkQuestionGenerationSetup({
  chapters,
  chaptersLoading,
  chaptersError,
  selectedChapterSlug,
  topics,
  topicsLoading,
  topicsError,
  selectedTopicIds,
  difficulty,
  busy,
  error,
  onSelectChapter,
  onToggleTopic,
  onClearTopics,
  onDifficultyChange,
  onStart,
}: BulkQuestionGenerationSetupProps) {
  const selectedTopicCount = selectedTopicIds.size;
  const selectedChapter = chapters.find(
    (chapter) => chapter.slug === selectedChapterSlug,
  );
  const canStart =
    Boolean(selectedChapterSlug) && selectedTopicCount > 0 && !busy;

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <p className="text-sm font-medium">Generate AI Q&amp;A</p>
        <p className="max-w-prose text-sm text-muted-foreground">
          Selected NCERT topics define the generation scope. Choose one Chapter,
          then select the grounded NCERT topic nodes that should drive
          generation. Generated Q&amp;A stays separate from the Question bank
          until a teacher reviews and accepts it.
        </p>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Difficulty</legend>
        <div
          className="flex flex-wrap gap-2"
          role="group"
          aria-label="Difficulty"
        >
          {GENERATION_DIFFICULTIES.map((label) => (
            <Button
              key={label}
              type="button"
              size="sm"
              variant={difficulty === label ? 'default' : 'outline'}
              aria-pressed={difficulty === label}
              onClick={() => onDifficultyChange(label)}
            >
              {label}
            </Button>
          ))}
        </div>
      </fieldset>

      <section
        className="space-y-3"
        aria-labelledby="generation-chapter-heading"
      >
        <div className="space-y-1">
          <p id="generation-chapter-heading" className="text-sm font-medium">
            NCERT Chapter
          </p>
          <p className="text-sm text-muted-foreground">
            The MVP supports one Chapter per run, so selecting another Chapter
            clears the current topic scope.
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
            {chapters.map((chapter) => (
              <label
                key={chapter.slug}
                className="flex items-start gap-2 rounded-md border bg-background px-3 py-2 text-sm"
              >
                <input
                  type="radio"
                  name="generation-chapter"
                  checked={selectedChapterSlug === chapter.slug}
                  onChange={() => onSelectChapter(chapter.slug)}
                />
                <span>
                  <span className="block font-medium">
                    {chapter.order}. {chapter.name}
                  </span>
                  <span className="block text-muted-foreground">
                    Open this Chapter's NCERT topics
                  </span>
                </span>
              </label>
            ))}
          </div>
        )}
      </section>

      {selectedChapterSlug && (
        <section
          className="space-y-3 border-t pt-4"
          aria-labelledby="generation-topics-heading"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1">
              <p id="generation-topics-heading" className="text-sm font-medium">
                Topic scope{selectedChapter ? ` — ${selectedChapter.name}` : ''}
              </p>
              <p className="text-sm text-muted-foreground">
                {selectedTopicCount === 0
                  ? 'Select at least one NCERT topic to enable generation.'
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
              Clear topics
            </Button>
          </div>

          {topicsLoading && <p className="text-sm">Loading NCERT topics…</p>}

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
            <ul className="divide-y rounded-md border">
              {topics.map((topic) => {
                const topicInputId = `topic-${topic.id}`;
                return (
                  <li key={topic.id} className="p-3">
                    <label
                      htmlFor={topicInputId}
                      className="flex items-start gap-3 text-sm"
                    >
                      <input
                        id={topicInputId}
                        type="checkbox"
                        className="mt-1"
                        checked={selectedTopicIds.has(topic.id)}
                        onChange={() => onToggleTopic(topic.id)}
                      />
                      <span className="min-w-0 space-y-1">
                        <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                          <span className="font-medium">{topic.title}</span>
                          <span className="text-xs text-muted-foreground">
                            {nodeTypeLabel(topic.type)} ·{' '}
                            {formatPageRange(topic)}
                          </span>
                        </span>
                        {topic.preview && (
                          <span className="block text-muted-foreground">
                            {topic.preview}
                          </span>
                        )}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      {error && (
        <div className="border-t pt-3" role="alert">
          <p className="text-sm font-medium">Generation could not start.</p>
          <p className="mt-1 text-sm text-muted-foreground">{error}</p>
        </div>
      )}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <Button type="button" onClick={onStart} disabled={!canStart}>
          {busy ? 'Starting generation…' : 'Generate AI Q&A'}
        </Button>
        {!canStart && !busy && (
          <p className="text-sm text-muted-foreground">
            Select one Chapter and at least one topic to queue generation.
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
}

function isActiveGenerationStatus(status: GenerationBatch['status']): boolean {
  return ACTIVE_GENERATION_STATUSES.includes(status);
}

function formatStatusTime(value: string): string {
  if (!value) return 'Not checked yet';
  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value));
}

function candidateTypeLabel(candidate: GeneratedQuestionCandidate): string {
  const parts = [
    candidate.payload.qtype,
    typeof candidate.payload.marks === 'number'
      ? `${candidate.payload.marks} mark${candidate.payload.marks === 1 ? '' : 's'}`
      : '',
    candidate.payload.chapter_slug,
  ].filter((part): part is string => typeof part === 'string' && Boolean(part));
  return parts.join(' · ');
}

export function GenerationProgressWorkspace({
  batch,
  loading,
  error,
  lastCheckedAt,
  pollIntervalMs,
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
}: GenerationProgressWorkspaceProps) {
  const [rejectedCandidateIds, setRejectedCandidateIds] = useState<Set<number>>(
    () => new Set(initialRejectedCandidateIds),
  );
  const noValidQuestions = batch
    ? shouldShowNoValidQuestionsMessage(batch)
    : false;
  const active = batch ? isActiveGenerationStatus(batch.status) : false;
  const reviewCounts = candidateReviewCounts(candidates, rejectedCandidateIds);

  function toggleRejected(candidateId: number) {
    setRejectedCandidateIds((current) =>
      toggleRejectedCandidate(current, candidateId),
    );
  }

  function acceptedCandidateIds() {
    return candidates
      .filter((candidate) => !rejectedCandidateIds.has(candidate.id))
      .map((candidate) => candidate.id);
  }

  function importAcceptedCandidates() {
    onAcceptCandidates(acceptedCandidateIds());
  }

  return (
    <div className="min-h-screen bg-secondary">
      <main className="mx-auto max-w-3xl p-6">
        <div className="rounded-lg border bg-background p-6 space-y-5">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">
              Question generation status
            </p>
            <h1 className="text-2xl font-semibold">Question bank generation</h1>
            <p className="max-w-prose text-sm text-muted-foreground">
              Generated candidates stay separate from the Question bank until a
              teacher reviews and accepts them.
            </p>
          </div>

          {loading && !batch && (
            <p className="text-sm">Loading generation status…</p>
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
            <div className="space-y-4">
              <div className="border-t pt-4 space-y-2">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">
                      Current stage
                    </p>
                    <p className="text-lg font-medium">
                      {generationStageLabel(batch.status)}
                    </p>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Last checked{' '}
                    {formatStatusTime(lastCheckedAt || batch.updated_at)}
                  </p>
                </div>
                <p className="text-sm text-muted-foreground">
                  {generationStageDescription(batch.status)}
                </p>
                <p className="text-sm text-muted-foreground">
                  Backend requested {batch.requested_count} candidate
                  {batch.requested_count === 1 ? '' : 's'}. Validation may
                  reduce how many candidates reach review.
                </p>
                {active && (
                  <p className="text-sm text-muted-foreground">
                    Checking every {Math.round(pollIntervalMs / 1000)} seconds.
                    You can safely run this in the background.
                  </p>
                )}
              </div>

              {error && (
                <div className="border-t pt-3" role="status">
                  <p className="text-sm font-medium">
                    Latest status check failed.
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">{error}</p>
                </div>
              )}

              {batch.status === 'ready_for_review' && (
                <div className="border-t pt-4 space-y-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h2 className="font-medium">Review generated Q&amp;A</h2>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {candidates.length} candidate
                        {candidates.length === 1 ? '' : 's'} passed validation
                        and {candidates.length === 1 ? 'is' : 'are'} shown for
                        teacher review. Answers are visible by default. All
                        candidates are accepted locally until you reject them;
                        the final import sends only accepted candidates to the
                        Question bank.
                      </p>
                    </div>
                    <div className="rounded-md border px-3 py-2 text-sm">
                      <span className="font-medium">
                        {reviewCounts.accepted}
                      </span>{' '}
                      accepted ·{' '}
                      <span className="font-medium">
                        {reviewCounts.rejected}
                      </span>{' '}
                      rejected
                    </div>
                  </div>

                  {candidatesLoading && (
                    <p className="text-sm">Loading generated candidates…</p>
                  )}

                  {!candidatesLoading && candidatesError && (
                    <div role="alert" className="space-y-2">
                      <div>
                        <p className="text-sm font-medium">
                          Candidates could not be loaded.
                        </p>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {candidatesError}
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        onClick={onRetryCandidates}
                      >
                        Try loading candidates again
                      </Button>
                    </div>
                  )}

                  {!candidatesLoading &&
                    !candidatesError &&
                    candidates.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        This batch is ready, but no generated candidates were
                        returned.
                      </p>
                    )}

                  {!candidatesLoading &&
                    !candidatesError &&
                    candidates.length > 0 && (
                      <ul
                        className="max-h-[64vh] overflow-y-auto rounded-md border"
                        aria-label="Generated Q&A candidates"
                      >
                        {candidates.map((candidate) => {
                          const rejected = rejectedCandidateIds.has(
                            candidate.id,
                          );
                          const topics = candidateTopicLabels(candidate);
                          return (
                            <li
                              key={candidate.id}
                              className={`space-y-3 border-b p-4 last:border-b-0 ${
                                rejected ? 'bg-secondary/70' : 'bg-background'
                              }`}
                            >
                              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                <div className="space-y-1">
                                  <p className="font-medium">
                                    {candidateQuestionText(candidate)}
                                  </p>
                                  <p className="text-xs text-muted-foreground">
                                    {candidateTypeLabel(candidate) ||
                                      'Generated candidate'}
                                  </p>
                                </div>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant={rejected ? 'outline' : 'ghost'}
                                  onClick={() => toggleRejected(candidate.id)}
                                >
                                  {rejected ? 'Undo reject' : 'Reject'}
                                </Button>
                              </div>

                              <div className="rounded-md border bg-secondary/50 p-3">
                                <p className="text-xs font-medium text-muted-foreground">
                                  Answer
                                </p>
                                <p className="mt-1 text-sm">
                                  {candidateAnswerText(candidate)}
                                </p>
                              </div>

                              {topics.length > 0 && (
                                <p className="text-sm text-muted-foreground">
                                  Topics: {topics.join(', ')}
                                </p>
                              )}

                              {rejected && (
                                <p
                                  className="text-sm font-medium"
                                  role="status"
                                >
                                  Rejected locally. Use Undo to include this
                                  candidate again.
                                </p>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    )}

                  {acceptError && (
                    <div
                      className="rounded-md border border-destructive/40 bg-destructive/5 p-3"
                      role="alert"
                    >
                      <p className="text-sm font-medium">Import failed.</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {acceptError}
                      </p>
                    </div>
                  )}

                  <div className="sticky bottom-0 -mx-6 border-t bg-background/95 px-6 py-4 shadow-lg backdrop-blur">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <p className="text-sm">
                        <span className="font-medium">
                          {reviewCounts.accepted}
                        </span>{' '}
                        accepted ·{' '}
                        <span className="font-medium">
                          {reviewCounts.rejected}
                        </span>{' '}
                        rejected
                      </p>
                      <Button
                        type="button"
                        onClick={importAcceptedCandidates}
                        disabled={
                          accepting ||
                          candidatesLoading ||
                          Boolean(candidatesError) ||
                          candidates.length === 0 ||
                          reviewCounts.accepted === 0
                        }
                      >
                        {accepting
                          ? 'Importing accepted Q&A…'
                          : 'Import accepted Q&A'}
                      </Button>
                    </div>
                    {reviewCounts.accepted === 0 && candidates.length > 0 && (
                      <p className="mt-2 text-sm text-muted-foreground">
                        Restore at least one candidate to import into the
                        Question bank.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {active && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={onRunInBackground}
                >
                  Run in background
                </Button>
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
                <Button type="button" onClick={onTryAgain}>
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
