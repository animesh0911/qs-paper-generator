import type { GenerationBatch, GenerationDifficultyLabel, Chapter } from '@/types';
import { Button } from '@/components/ui/button';
import {
  GENERATION_DIFFICULTIES,
  generationStageLabel,
  shouldShowNoValidQuestionsMessage,
} from '@/lib/question-generation';

export interface BulkQuestionGenerationSetupProps {
  chapters: Chapter[];
  selectedSlugs: Set<string>;
  topicNamesByChapter: Record<string, string>;
  difficulty: GenerationDifficultyLabel;
  busy: boolean;
  error: string;
  onToggleChapter: (slug: string) => void;
  onSelectAllChapters: () => void;
  onTopicNamesChange: (slug: string, value: string) => void;
  onDifficultyChange: (difficulty: GenerationDifficultyLabel) => void;
  onStart: () => void;
}

export function BulkQuestionGenerationSetup({
  chapters,
  selectedSlugs,
  topicNamesByChapter,
  difficulty,
  busy,
  error,
  onToggleChapter,
  onSelectAllChapters,
  onTopicNamesChange,
  onDifficultyChange,
  onStart,
}: BulkQuestionGenerationSetupProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-md border bg-background p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="font-medium">Generate Question bank</h3>
            <p className="text-sm text-muted-foreground">
              Pick canonical Chapters, optional Topic hints, and difficulty.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={onSelectAllChapters}>
            Select all Chapters
          </Button>
        </div>

        <div>
          <p className="text-sm font-medium mb-2">Difficulty</p>
          <div className="flex flex-wrap gap-2">
            {GENERATION_DIFFICULTIES.map((label) => (
              <Button
                key={label}
                type="button"
                size="sm"
                variant={difficulty === label ? 'default' : 'outline'}
                onClick={() => onDifficultyChange(label)}
              >
                {label}
              </Button>
            ))}
          </div>
        </div>

        <div>
          <p className="text-sm font-medium mb-2">Chapters</p>
          <ul className="space-y-3">
            {chapters.map((chapter) => {
              const selected = selectedSlugs.has(chapter.slug);
              return (
                <li key={chapter.slug} className="rounded-md border p-3">
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
                    <label className="mt-2 block text-sm">
                      Optional Topics under {chapter.name}
                      <textarea
                        className="mt-1 flex min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        placeholder="Comma or newline separated Topic names"
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
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="button" onClick={onStart} disabled={busy}>
          {busy ? 'Starting generation…' : 'Generate Question bank'}
        </Button>
      </div>
    </div>
  );
}

export interface GenerationProgressWorkspaceProps {
  batch: GenerationBatch | null;
  loading: boolean;
  error: string;
  onRunInBackground: () => void;
  onTryAgain: () => void;
  onBackToPaperSetup: () => void;
}

function isActiveGenerationStatus(status: GenerationBatch['status']): boolean {
  return ['queued', 'generating_questions', 'validating'].includes(status);
}

export function GenerationProgressWorkspace({
  batch,
  loading,
  error,
  onRunInBackground,
  onTryAgain,
  onBackToPaperSetup,
}: GenerationProgressWorkspaceProps) {
  const noValidQuestions = batch ? shouldShowNoValidQuestionsMessage(batch) : false;

  return (
    <div className="min-h-screen bg-secondary">
      <main className="mx-auto max-w-3xl p-6 space-y-4">
        <div className="rounded-lg border bg-background p-6 space-y-4">
          <div>
            <p className="text-sm text-muted-foreground">GenerationBatch</p>
            <h1 className="text-2xl font-semibold">Question bank generation</h1>
          </div>

          {loading && <p className="text-sm">Loading generation status…</p>}
          {error && <p className="text-sm text-destructive">{error}</p>}

          {batch && !noValidQuestions && (
            <div className="space-y-3">
              <div className="rounded-md border p-4">
                <p className="text-sm text-muted-foreground">Current stage</p>
                <p className="text-lg font-medium">
                  {generationStageLabel(batch.status)}
                </p>
              </div>

              {batch.status === 'ready_for_review' && (
                <div className="rounded-md border p-4 space-y-2">
                  <h2 className="font-medium">Ready for review</h2>
                  <p className="text-sm text-muted-foreground">
                    {batch.candidate_count} generated Questions and answers are ready.
                  </p>
                  <Button type="button">Review generated Questions</Button>
                </div>
              )}

              {isActiveGenerationStatus(batch.status) && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={onRunInBackground}
                >
                  Run in background
                </Button>
              )}

              {(batch.status === 'accepted' || batch.status === 'expired') && (
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
            <div className="rounded-md border p-4 space-y-3">
              <p className="text-sm">
                AI generation did not produce any Questions and answers. Try again
                later.
              </p>
              <div className="flex gap-2">
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
