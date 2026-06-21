import type { Chapter, GenerationBatch, GenerationDifficultyLabel } from '@/types';
import { Button } from '@/components/ui/button';
import {
  GENERATION_DIFFICULTIES,
  generationStageDescription,
  generationStageLabel,
  shouldShowNoValidQuestionsMessage,
} from '@/lib/question-generation';

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
  onRunInBackground: () => void;
  onTryAgain: () => void;
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

export function GenerationProgressWorkspace({
  batch,
  loading,
  error,
  lastCheckedAt,
  pollIntervalMs,
  onRunInBackground,
  onTryAgain,
  onBackToPaperSetup,
}: GenerationProgressWorkspaceProps) {
  const noValidQuestions = batch ? shouldShowNoValidQuestionsMessage(batch) : false;
  const active = batch ? isActiveGenerationStatus(batch.status) : false;

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
                <div className="border-t pt-4 space-y-3">
                  <div>
                    <h2 className="font-medium">Ready for review</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {batch.candidate_count} generated Questions and answers are
                      ready. Review is required before they enter the Question bank.
                    </p>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <Button type="button" disabled>
                      Review generated Questions
                    </Button>
                    <p className="text-sm text-muted-foreground">
                      Review workspace is not connected in this release yet.
                    </p>
                  </div>
                </div>
              )}

              {active && (
                <Button type="button" variant="outline" onClick={onRunInBackground}>
                  Run in background
                </Button>
              )}

              {(batch.status === 'accepted' || batch.status === 'expired') && (
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
