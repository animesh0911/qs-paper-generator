/**
 * Dashboard — the only authenticated page in Slice 3.
 *
 * Pure orchestration: wires the `useCoverageForm` hook to the
 * `CoverageFormView`, posts to `assemblePaper`, and renders the result via
 * `PaperPreview`. All form state lives in the hook; all render logic lives
 * in the components. The page itself only owns the assemble call, the
 * scroll-into-view nudge, and the error string.
 *
 * Where it fits:
 * - Uses: `lib/api.assemblePaper`, `lib/api.fetchMetadata`,
 *   `lib/api.downloadPaperPdf`, `hooks/useCoverageForm`,
 *   `components/coverage/*`.
 * - Rendered by: `App.tsx` behind a `RequireAuth` guard.
 *
 * @module DashboardPage
 */
import { useEffect, useRef, useState } from 'react';
import { assemblePaper, downloadPaperPdf, fetchMetadata } from '@/lib/api';
import type { Paper } from '@/types';
import { SECTION_TITLES } from '@/constants';
import { useAuth } from '@/hooks/useAuth.hook';
import { useCoverageForm } from '@/hooks/useCoverageForm.hook';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CoverageFormView, PaperPreview } from '@/components/coverage';

export default function Dashboard() {
  const { logout } = useAuth();
  const form = useCoverageForm();

  const [paper, setPaper] = useState<Paper | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sectionTitles, setSectionTitles] =
    useState<Record<string, string>>(SECTION_TITLES);
  const paperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchMetadata()
      .then(({ sections }) =>
        setSectionTitles(
          Object.fromEntries(sections.map((s) => [s.code, s.label])),
        ),
      )
      .catch(() => {
        // fallback to static SECTION_TITLES stays in state
      });
  }, []);

  async function generate() {
    setBusy(true);
    setError('');
    try {
      const next = await assemblePaper(form.toAssemblePayload());
      setPaper(next);
      // Paper card renders below a long chapter list; scroll it into view so
      // the teacher sees the result without hunting for it.
      requestAnimationFrame(() => {
        paperRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
        });
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
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
            <CoverageFormView
              form={form}
              busy={busy}
              onGenerate={generate}
              trailing={
                paper && (
                  <Button
                    variant="outline"
                    onClick={() => downloadPaperPdf(paper.id)}
                  >
                    Download PDF
                  </Button>
                )
              }
            />
            {error && <p className="text-sm text-destructive mt-2">{error}</p>}
          </CardContent>
        </Card>

        {paper && (
          <PaperPreview
            ref={paperRef}
            paper={paper}
            sectionTitles={sectionTitles}
            chapterNameBySlug={form.chapterNameBySlug}
          />
        )}
      </main>
    </div>
  );
}
