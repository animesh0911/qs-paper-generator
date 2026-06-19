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
import { assemblePaper } from '@/lib/api';
import { generatedPaperEditorPath } from '@/lib/editor-routes';
import { useAuth } from '@/hooks/useAuth.hook';
import { useCoverageForm } from '@/hooks/useCoverageForm.hook';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CoverageFormView } from '@/components/coverage';

export default function Dashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const form = useCoverageForm();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

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
      </main>
    </div>
  );
}
