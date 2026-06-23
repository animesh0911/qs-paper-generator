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
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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

export default function Dashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const form = useCoverageForm();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [generationBusy, setGenerationBusy] = useState(false);
  const [generationError, setGenerationError] = useState('');
  const [generationChapterSlug, setGenerationChapterSlug] = useState('');
  const [generationTopics, setGenerationTopics] = useState<ChapterTopicNode[]>([]);
  const [generationTopicsLoading, setGenerationTopicsLoading] = useState(false);
  const [generationTopicsError, setGenerationTopicsError] = useState('');
  const [selectedTopicIds, setSelectedTopicIds] = useState<Set<string>>(new Set());
  const [generationDifficulty, setGenerationDifficulty] =
    useState<GenerationDifficultyLabel>('Standard');

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
    try {
      const payload = buildGenerationBatchPayload({
        chapterSlug: generationChapterSlug,
        chapterMapNodeIds: Array.from(selectedTopicIds),
        difficulty: generationDifficulty,
      });
      const batch = await createGenerationBatch(payload);
      navigate(`/generation-batches/${batch.id}`);
    } catch (err) {
      setGenerationError((err as Error).message);
    } finally {
      setGenerationBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-secondary">
      <header className="flex items-center justify-between border-b bg-background px-6 py-3">
        <h1 className="font-semibold">Question Paper Generator</h1>
        <Button variant="ghost" size="sm" onClick={logout}>
          Sign out
        </Button>
      </header>

      <main className="mx-auto max-w-3xl p-6 space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Generate paper</CardTitle>
            <p className="text-sm text-muted-foreground">
              Select chapters and optionally weight them. Difficulty profile
              sets the Remember / Understand / Apply / Analyse mix.
            </p>
          </CardHeader>
          <CardContent>
            <CoverageFormView form={form} busy={busy} onGenerate={generate} />
            {error && <p className="text-sm text-destructive mt-2">{error}</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Generate AI Q&amp;A</CardTitle>
            <p className="text-sm text-muted-foreground">
              Secondary workflow for creating review-only Question-and-answer
              candidates from grounded NCERT topic metadata.
            </p>
          </CardHeader>
          <CardContent>
            <BulkQuestionGenerationSetup
              chapters={form.chapters}
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
              onSelectChapter={selectGenerationChapter}
              onToggleTopic={toggleGenerationTopic}
              onClearTopics={clearGenerationTopics}
              onDifficultyChange={setGenerationDifficulty}
              onStart={startQuestionBankGeneration}
            />
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
