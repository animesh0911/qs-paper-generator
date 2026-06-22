import { useState } from 'react';
import type {
  Chapter,
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
  selectedSlugs: Set<string>;
  topicNamesByChapter: Record<string, string>;
  difficulty: GenerationDifficultyLabel;
  busy: boolean;
  error: string;
  onToggleChapter: (slug: string) => void;
  onSelectAllChapters: () => void;
  onClearChapters: () => void;
  onTopicNamesChange: (slug: string, value: string) => void;
  onDifficultyChange: (difficulty: GenerationDifficultyLabel) => void;
  onStart: () => void;
}

export function BulkQuestionGenerationSetup({
  chapters,
  chaptersLoading,
  chaptersError,
  selectedSlugs,
  topicNamesByChapter,
  difficulty,
  busy,
  error,
  onToggleChapter,
  onSelectAllChapters,
  onClearChapters,
  onTopicNamesChange,
  onDifficultyChange,
  onStart,
}: BulkQuestionGenerationSetupProps) {
  const selectedCount = selectedSlugs.size;
  const canStart = selectedCount > 0 && !busy;

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <p className="text-sm font-medium">Generation setup</p>
        <p className="max-w-prose text-sm text-muted-foreground">
          Choose the Chapter scope for the request. Topic hints are optional and
          only guide the generated Question-and-answer candidates.
        </p>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Difficulty</legend>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Difficulty">
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

      <section className="space-y-3" aria-labelledby="generation-chapters-heading">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <p id="generation-chapters-heading" className="text-sm font-medium">
              Chapters and Topic hints
            </p>
            <p className="text-sm text-muted-foreground">
              {selectedCount === 0
                ? 'Select at least one Chapter before starting generation.'
                : `${selectedCount} Chapter${selectedCount === 1 ? '' : 's'} selected.`}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onSelectAllChapters}
              disabled={chapters.length === 0 || selectedCount === chapters.length}
            >
              Select all Chapters
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onClearChapters}
              disabled={selectedCount === 0}
            >
              Clear selection
            </Button>
          </div>
        </div>

        {chaptersLoading && (
          <p className="border-t pt-3 text-sm">Loading Chapters…</p>
        )}

        {!chaptersLoading && chaptersError && (
          <div className="border-t pt-3" role="alert">
            <p className="text-sm font-medium">Chapters could not be loaded.</p>
            <p className="mt-1 text-sm text-muted-foreground">{chaptersError}</p>
          </div>
        )}

        {!chaptersLoading && !chaptersError && chapters.length === 0 && (
          <p className="border-t pt-3 text-sm">
            No Chapters are available for generation yet.
          </p>
        )}

        {chapters.length > 0 && (
          <ul className="divide-y">
            {chapters.map((chapter) => {
              const selected = selectedSlugs.has(chapter.slug);
              const topicFieldId = `topic-hints-${chapter.slug}`;
              return (
                <li key={chapter.slug} className="py-3 first:pt-0 last:pb-0">
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => onToggleChapter(chapter.slug)}
                    />
                    <span>
                      {chapter.order}. {chapter.name}
                    </span>
                  </label>
                  {selected && (
                    <label htmlFor={topicFieldId} className="mt-2 block text-sm">
                      Optional Topic hints for {chapter.name}
                      <textarea
                        id={topicFieldId}
                        className="mt-1 flex min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                        placeholder="Example: Magnetic effects, domestic electric circuits"
                        value={topicNamesByChapter[chapter.slug] ?? ''}
                        onChange={(event) =>
                          onTopicNamesChange(chapter.slug, event.target.value)
                        }
                      />
                    </label>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {error && (
        <div className="border-t pt-3" role="alert">
          <p className="text-sm font-medium">Generation could not start.</p>
          <p className="mt-1 text-sm text-muted-foreground">{error}</p>
        </div>
      )}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <Button type="button" onClick={onStart} disabled={!canStart}>
          {busy ? 'Starting generation…' : 'Generate Question bank'}
        </Button>
        {selectedCount === 0 && (
          <p className="text-sm text-muted-foreground">
            Select at least one Chapter to enable generation.
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
  const noValidQuestions = batch ? shouldShowNoValidQuestionsMessage(batch) : false;
  const active = batch ? isActiveGenerationStatus(batch.status) : false;
  const reviewCounts = candidateReviewCounts(candidates, rejectedCandidateIds);

  function toggleRejected(candidateId: number) {
    setRejectedCandidateIds((current) => toggleRejectedCandidate(current, candidateId));
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
            <p className="text-sm text-muted-foreground">Question generation status</p>
            <h1 className="text-2xl font-semibold">Question bank generation</h1>
            <p className="max-w-prose text-sm text-muted-foreground">
              Generated candidates stay separate from the Question bank until a
              teacher reviews and accepts them.
            </p>
          </div>

          {loading && !batch && <p className="text-sm">Loading generation status…</p>}

          {error && !batch && (
            <div className="border-t pt-4 space-y-3" role="alert">
              <div>
                <p className="text-sm font-medium">We could not load this generation job.</p>
                <p className="mt-1 text-sm text-muted-foreground">{error}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={onTryAgain} disabled={loading}>
                  {loading ? 'Trying again…' : 'Try again'}
                </Button>
                <Button type="button" variant="outline" onClick={onBackToPaperSetup}>
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
                    <p className="text-sm text-muted-foreground">Current stage</p>
                    <p className="text-lg font-medium">
                      {generationStageLabel(batch.status)}
                    </p>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Last checked {formatStatusTime(lastCheckedAt || batch.updated_at)}
                  </p>
                </div>
                <p className="text-sm text-muted-foreground">
                  {generationStageDescription(batch.status)}
                </p>
                {active && (
                  <p className="text-sm text-muted-foreground">
                    Checking every {Math.round(pollIntervalMs / 1000)} seconds. You
                    can safely run this in the background.
                  </p>
                )}
              </div>

              {error && (
                <div className="border-t pt-3" role="status">
                  <p className="text-sm font-medium">Latest status check failed.</p>
                  <p className="mt-1 text-sm text-muted-foreground">{error}</p>
                </div>
              )}

              {batch.status === 'ready_for_review' && (
                <div className="border-t pt-4 space-y-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h2 className="font-medium">Review generated Q&amp;A</h2>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Answers are visible by default. All candidates are accepted
                        locally until you reject them; the final import sends only
                        accepted candidates to the Question bank.
                      </p>
                    </div>
                    <div className="rounded-md border px-3 py-2 text-sm">
                      <span className="font-medium">{reviewCounts.accepted}</span> accepted ·{' '}
                      <span className="font-medium">{reviewCounts.rejected}</span> rejected
                    </div>
                  </div>

                  {candidatesLoading && (
                    <p className="text-sm">Loading generated candidates…</p>
                  )}

                  {!candidatesLoading && candidatesError && (
                    <div role="alert" className="space-y-2">
                      <div>
                        <p className="text-sm font-medium">Candidates could not be loaded.</p>
                        <p className="mt-1 text-sm text-muted-foreground">{candidatesError}</p>
                      </div>
                      <Button type="button" size="sm" onClick={onRetryCandidates}>
                        Try loading candidates again
                      </Button>
                    </div>
                  )}

                  {!candidatesLoading && !candidatesError && candidates.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      This batch is ready, but no generated candidates were returned.
                    </p>
                  )}

                  {!candidatesLoading && !candidatesError && candidates.length > 0 && (
                    <ul className="max-h-[64vh] overflow-y-auto rounded-md border" aria-label="Generated Q&A candidates">
                      {candidates.map((candidate) => {
                        const rejected = rejectedCandidateIds.has(candidate.id);
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
                                <p className="font-medium">{candidateQuestionText(candidate)}</p>
                                <p className="text-xs text-muted-foreground">
                                  {candidateTypeLabel(candidate) || 'Generated candidate'}
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
                              <p className="text-xs font-medium text-muted-foreground">Answer</p>
                              <p className="mt-1 text-sm">{candidateAnswerText(candidate)}</p>
                            </div>

                            {topics.length > 0 && (
                              <p className="text-sm text-muted-foreground">
                                Topics: {topics.join(', ')}
                              </p>
                            )}


                            {rejected && (
                              <p className="text-sm font-medium" role="status">
                                Rejected locally. Use Undo to include this candidate again.
                              </p>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}

                  {acceptError && (
                    <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3" role="alert">
                      <p className="text-sm font-medium">Import failed.</p>
                      <p className="mt-1 text-sm text-muted-foreground">{acceptError}</p>
                    </div>
                  )}

                  <div className="sticky bottom-0 -mx-6 border-t bg-background/95 px-6 py-4 shadow-lg backdrop-blur">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <p className="text-sm">
                        <span className="font-medium">{reviewCounts.accepted}</span> accepted ·{' '}
                        <span className="font-medium">{reviewCounts.rejected}</span> rejected
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
                        {accepting ? 'Importing accepted Q&A…' : 'Import accepted Q&A'}
                      </Button>
                    </div>
                    {reviewCounts.accepted === 0 && candidates.length > 0 && (
                      <p className="mt-2 text-sm text-muted-foreground">
                        Restore at least one candidate to import into the Question bank.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {active && (
                <Button type="button" variant="outline" onClick={onRunInBackground}>
                  Run in background
                </Button>
              )}

              {batch.status === 'accepted' && (
                <div className="border-t pt-4 space-y-3">
                  <div>
                    <h2 className="font-medium">Generation batch accepted</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Accepted Q&amp;A candidates have been imported into the Question bank.
                    </p>
                  </div>
                  <Button type="button" variant="outline" onClick={onBackToPaperSetup}>
                    Back to paper setup
                  </Button>
                </div>
              )}

              {batch.status === 'expired' && (
                <Button type="button" variant="outline" onClick={onBackToPaperSetup}>
                  Back to paper setup
                </Button>
              )}
            </div>
          )}

          {noValidQuestions && (
            <div className="border-t pt-4 space-y-3">
              <div>
                <h2 className="font-medium">No valid Questions were produced</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {batch?.error ||
                    'The generation job finished, but no candidates passed validation.'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={onTryAgain}>
                  Try again
                </Button>
                <Button type="button" variant="outline" onClick={onBackToPaperSetup}>
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
