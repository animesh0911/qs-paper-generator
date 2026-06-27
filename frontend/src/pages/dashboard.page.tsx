/**
 * Dashboard — the only authenticated page.
 *
 * Pure orchestration: wires the `useCoverageForm` hook to the
 * `CoverageFormView`, posts to `assemblePaper`, and opens the persisted result
 * in the editor. All form state lives in the hook; all render logic lives in
 * the components.
 *
 * @module DashboardPage
 */
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronUp, ListChecks, Sparkles } from 'lucide-react';
import {
  assemblePaper,
  createGenerationBatch,
  fetchChapterTopics,
} from '@/lib/api';
import { generatedPaperEditorPath } from '@/lib/editor-routes';
import { useAuth } from '@/hooks/useAuth.hook';
import { useCoverageForm } from '@/hooks/useCoverageForm.hook';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CoverageFormView } from '@/components/coverage';
import { BulkQuestionGenerationSetup } from '@/components/question-generation';
import { buildGenerationBatchPayload } from '@/lib/question-generation';
import type { ChapterTopicNode, GenerationDifficultyLabel } from '@/types';

const MVP_GENERATION_CHAPTER_SLUG = 'carbon-and-its-compounds';

interface GenerationPrefill {
  chapterSlug: string;
  topicIds: string[];
  difficulty: GenerationDifficultyLabel;
}

export default function Dashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const form = useCoverageForm();
  const location = useLocation();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [generationBusy, setGenerationBusy] = useState(false);
  const [generationError, setGenerationError] = useState('');
  const [activeGenerationBatchId, setActiveGenerationBatchId] = useState<
    number | null
  >(null);
  const [generationChapterSlug, setGenerationChapterSlug] = useState('');
  const [generationTopics, setGenerationTopics] = useState<ChapterTopicNode[]>(
    [],
  );
  const [generationTopicsLoading, setGenerationTopicsLoading] = useState(false);
  const [generationTopicsError, setGenerationTopicsError] = useState('');
  const [selectedTopicIds, setSelectedTopicIds] = useState<Set<string>>(
    new Set(),
  );
  const [generationPanelOpen, setGenerationPanelOpen] = useState(false);
  const [generationDifficulty, setGenerationDifficulty] =
    useState<GenerationDifficultyLabel>('Standard');
  const generationChapters = useMemo(
    () =>
      form.chapters.filter(
        (chapter) => chapter.slug === MVP_GENERATION_CHAPTER_SLUG,
      ),
    [form.chapters],
  );

  useEffect(() => {
    if (!generationChapterSlug) {
      setGenerationTopics([]);
      setGenerationTopicsError('');
      setGenerationTopicsLoading(false);
      return;
    }

    let cancelled = false;
    setGenerationTopicsLoading(true);
    setGenerationTopicsError('');
    fetchChapterTopics(generationChapterSlug)
      .then((response) => {
        if (cancelled) return;
        setGenerationTopics(response.topics);
      })
      .catch((err) => {
        if (cancelled) return;
        setGenerationTopics([]);
        setGenerationTopicsError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setGenerationTopicsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [generationChapterSlug]);

  // Pre-fill the generation setup when arriving from "Generate another batch"
  // on the progress page, so the teacher can tweak and regenerate in place.
  useEffect(() => {
    const prefill = (
      location.state as { generationPrefill?: GenerationPrefill }
    )?.generationPrefill;
    if (!prefill) return;
    setGenerationChapterSlug(prefill.chapterSlug);
    setSelectedTopicIds(new Set(prefill.topicIds));
    setGenerationDifficulty(prefill.difficulty);
    setGenerationPanelOpen(true);
    // Clear the navigation state so a refresh doesn't re-apply the prefill.
    navigate('.', { replace: true, state: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  async function generate() {
    setBusy(true);
    setError('');
    try {
      const next = await assemblePaper(form.toAssemblePayload());
      navigate(generatedPaperEditorPath(next.paper.id));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function selectGenerationChapter(slug: string) {
    setGenerationChapterSlug(slug);
    setSelectedTopicIds(new Set());
    setGenerationError('');
    setActiveGenerationBatchId(null);
  }

  function toggleGenerationTopic(nodeId: string) {
    setSelectedTopicIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }

  function clearGenerationTopics() {
    setSelectedTopicIds(new Set());
  }

  async function startQuestionBankGeneration() {
    setGenerationBusy(true);
    setGenerationError('');
    setActiveGenerationBatchId(null);
    try {
      const payload = buildGenerationBatchPayload({
        chapterSlug: generationChapterSlug,
        chapterMapNodeIds: Array.from(selectedTopicIds),
        difficulty: generationDifficulty,
      });
      const batch = await createGenerationBatch(payload);
      navigate(`/generation-batches/${batch.id}`);
    } catch (err) {
      // Batches now queue freely; a 409 here means the per-teacher queue cap is
      // reached, so surface the message rather than blocking on one active batch.
      setGenerationError((err as Error).message);
    } finally {
      setGenerationBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-secondary">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b bg-background/95 px-6 py-3 backdrop-blur">
        <div>
          <p className="text-xs font-medium text-muted-foreground">
            CBSE Class 10 Science
          </p>
          <h1 className="font-semibold">Question Paper Generator</h1>
        </div>
        <Button variant="ghost" size="sm" onClick={logout}>
          Sign out
        </Button>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:py-10">
        <Card className="overflow-hidden rounded-lg border-white/70 bg-white/80 shadow-none backdrop-blur-2xl">
          <CardHeader className="border-b border-white/70 bg-white/60 px-5 py-5 sm:px-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1.5">
                <CardTitle className="text-xl leading-7">
                  Generate paper
                </CardTitle>
                <p className="max-w-2xl text-[0.9375rem] leading-6 text-muted-foreground">
                  Select chapters — they are distributed equally. Difficulty
                  profile sets the Remember / Understand / Apply / Analyse mix.
                </p>
              </div>
              <span className="inline-flex w-fit items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs font-medium text-secondary-foreground">
                <ListChecks className="size-3.5" aria-hidden="true" />
                Review workspace
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-7 bg-white/45 px-5 py-6 sm:px-6">
            <section aria-labelledby="paper-generation-heading">
              <h2 id="paper-generation-heading" className="sr-only">
                Paper generation setup
              </h2>
              <CoverageFormView form={form} busy={busy} onGenerate={generate} />
            </section>
            {error && <p className="text-sm text-destructive mt-2">{error}</p>}

            <section
              className="border-t border-white/70 pt-6"
              aria-labelledby="generation-section-heading"
            >
              <button
                type="button"
                className="flex w-full items-start justify-between gap-4 rounded-lg border border-white/70 bg-white/70 px-4 py-3.5 text-left transition-colors hover:bg-white/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-expanded={generationPanelOpen}
                aria-controls="generation-panel"
                onClick={() => setGenerationPanelOpen((open) => !open)}
              >
                <span className="flex min-w-0 items-start gap-3">
                  <span className="mt-0.5 flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
                    <Sparkles className="size-4" aria-hidden="true" />
                  </span>
                  <span className="min-w-0 space-y-1">
                    <span
                      id="generation-section-heading"
                      className="block text-sm font-semibold"
                    >
                      Generate AI Q&amp;A
                    </span>
                    <span className="block text-[0.8125rem] leading-5 text-muted-foreground sm:text-sm">
                      {selectedTopicIds.size > 0
                        ? `${selectedTopicIds.size} topic${selectedTopicIds.size === 1 ? '' : 's'} selected`
                        : 'Pick Chapter 4, then choose topics'}
                    </span>
                  </span>
                </span>
                <span className="mt-2 flex items-center gap-3">
                  <span className="hidden items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs font-medium text-secondary-foreground sm:inline-flex">
                    <ListChecks className="size-3.5" aria-hidden="true" />
                    Topic scoped
                  </span>
                  {generationPanelOpen ? (
                    <ChevronUp className="size-4" aria-hidden="true" />
                  ) : (
                    <ChevronDown className="size-4" aria-hidden="true" />
                  )}
                </span>
              </button>

              <div
                id="generation-panel"
                className={generationPanelOpen ? 'pt-4' : 'hidden'}
              >
                <BulkQuestionGenerationSetup
                  chapters={generationChapters}
                  chaptersLoading={form.chaptersLoading}
                  chaptersError={form.chaptersError}
                  selectedChapterSlug={generationChapterSlug}
                  topics={generationTopics}
                  topicsLoading={generationTopicsLoading}
                  topicsError={generationTopicsError}
                  selectedTopicIds={selectedTopicIds}
                  difficulty={generationDifficulty}
                  busy={generationBusy}
                  error={generationError}
                  activeBatchId={activeGenerationBatchId}
                  onSelectChapter={selectGenerationChapter}
                  onToggleTopic={toggleGenerationTopic}
                  onClearTopics={clearGenerationTopics}
                  onDifficultyChange={setGenerationDifficulty}
                  onStart={startQuestionBankGeneration}
                  onOpenActiveBatch={() => {
                    if (activeGenerationBatchId) {
                      navigate(
                        `/generation-batches/${activeGenerationBatchId}`,
                      );
                    }
                  }}
                />
              </div>
            </section>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
