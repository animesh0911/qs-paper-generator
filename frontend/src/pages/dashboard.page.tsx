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
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { assemblePaper, createGenerationBatch } from '@/lib/api';
import { generatedPaperEditorPath } from '@/lib/editor-routes';
import { useAuth } from '@/hooks/useAuth.hook';
import { useCoverageForm } from '@/hooks/useCoverageForm.hook';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CoverageFormView } from '@/components/coverage';
import { BulkQuestionGenerationSetup } from '@/components/question-generation';
import { buildGenerationBatchPayload } from '@/lib/question-generation';
import type { GenerationDifficultyLabel } from '@/types';

export default function Dashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const form = useCoverageForm();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [generationBusy, setGenerationBusy] = useState(false);
  const [generationError, setGenerationError] = useState('');
  const [generationSelectedSlugs, setGenerationSelectedSlugs] = useState<Set<string>>(
    new Set(),
  );
  const [topicNamesByChapter, setTopicNamesByChapter] = useState<Record<string, string>>(
    {},
  );
  const [generationDifficulty, setGenerationDifficulty] =
    useState<GenerationDifficultyLabel>('Standard');

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

  function toggleGenerationChapter(slug: string) {
    setGenerationSelectedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  function selectAllGenerationChapters() {
    setGenerationSelectedSlugs(new Set(form.chapters.map((chapter) => chapter.slug)));
  }

  async function startQuestionBankGeneration() {
    setGenerationBusy(true);
    setGenerationError('');
    try {
      const payload = buildGenerationBatchPayload({
        chapterSlugs: Array.from(generationSelectedSlugs),
        topicNamesByChapter,
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
            <CardTitle>Coverage</CardTitle>
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
            <CardTitle>Question bank</CardTitle>
            <p className="text-sm text-muted-foreground">
              Generate Question-and-answer candidates for later review without
              changing this paper setup.
            </p>
          </CardHeader>
          <CardContent>
            <BulkQuestionGenerationSetup
              chapters={form.chapters}
              selectedSlugs={generationSelectedSlugs}
              topicNamesByChapter={topicNamesByChapter}
              difficulty={generationDifficulty}
              busy={generationBusy}
              error={generationError}
              onToggleChapter={toggleGenerationChapter}
              onSelectAllChapters={selectAllGenerationChapters}
              onTopicNamesChange={(slug, value) =>
                setTopicNamesByChapter((prev) => ({ ...prev, [slug]: value }))
              }
              onDifficultyChange={setGenerationDifficulty}
              onStart={startQuestionBankGeneration}
            />
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
