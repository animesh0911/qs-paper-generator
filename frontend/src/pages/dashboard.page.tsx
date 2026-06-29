/**
 * Generate Paper — the default authenticated page.
 *
 * Pure orchestration: wires the `useCoverageForm` hook to the
 * `CoverageFormView`, posts to `assemblePaper`, and opens the persisted result
 * in the editor. AI Q&A generation and PDF upload each live on their own route
 * (see `AppHeader`); this page is now just paper assembly.
 *
 * @module DashboardPage
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ListChecks } from 'lucide-react';
import { assemblePaper } from '@/lib/api';
import { generatedPaperEditorPath } from '@/lib/editor-routes';
import { useCoverageForm } from '@/hooks/useCoverageForm.hook';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AppHeader } from '@/components/app-nav';
import { CoverageFormView } from '@/components/coverage';

export default function Dashboard() {
  const navigate = useNavigate();
  const form = useCoverageForm();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function generate() {
    if (!form.hasSelectedChapters) {
      setError('Select at least one Chapter to generate a paper.');
      return;
    }
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

  return (
    <div className="min-h-screen bg-secondary">
      <AppHeader />

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
        <Card className="overflow-hidden rounded-lg border-white/70 bg-white/80 shadow-none backdrop-blur-2xl">
          <CardHeader className="border-b border-white/70 bg-white/60 px-5 py-5 sm:px-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1.5">
                <CardTitle className="text-xl leading-7">
                  Generate paper
                </CardTitle>
                <p className="max-w-2xl text-[0.9375rem] leading-6 text-muted-foreground">
                  Set up a CBSE Class 10 Science paper, choose chapters, then
                  open the editor for review, swaps, answers, and export.
                </p>
              </div>
              <span className="inline-flex w-fit items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs font-medium text-secondary-foreground">
                <ListChecks className="size-3.5" aria-hidden="true" />
                Review workspace
              </span>
            </div>
          </CardHeader>
          <CardContent className="bg-white/45 px-5 py-6 sm:px-6">
            <section aria-labelledby="paper-generation-heading">
              <h2 id="paper-generation-heading" className="sr-only">
                Paper generation setup
              </h2>
              <CoverageFormView form={form} busy={busy} onGenerate={generate} />
            </section>
            {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
