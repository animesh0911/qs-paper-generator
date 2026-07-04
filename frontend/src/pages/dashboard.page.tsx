/**
 * Generate Paper — the authenticated paper-assembly workflow.
 *
 * Pure orchestration: wires the `useCoverageForm` hook to the
 * `CoverageFormView`, posts to `assemblePaper`, and opens the persisted result
 * in the editor. The welcome screen links here as the Generate workflow; AI Q&A
 * generation and PDF upload each live on their own route (see `AppHeader`).
 *
 * @module DashboardPage
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { assemblePaper } from '@/lib/api';
import { generatedPaperEditorPath } from '@/lib/editor-routes';
import { useCoverageForm } from '@/hooks/useCoverageForm.hook';
import { AppHeader } from '@/components/app-nav';
import { CoverageFormView } from '@/components/coverage';

export default function Dashboard() {
  const navigate = useNavigate();
  const form = useCoverageForm();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function generate() {
    if (!form.hasSelectedChapters && form.selectedSourceKeys.size === 0) {
      setError('Choose chapters or sources to generate a paper.');
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

      <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
        <section aria-labelledby="paper-generation-heading">
          <div className="mb-5">
            <h1
              id="paper-generation-heading"
              className="text-xl font-semibold leading-7"
            >
              Generate paper
            </h1>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
              Set the paper format, then open chapters or sources only when you
              need to adjust the first draft scope.
            </p>
          </div>
          <CoverageFormView form={form} busy={busy} onGenerate={generate} />
        </section>
        {error && (
          <p className="mt-3 text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
      </main>
    </div>
  );
}
