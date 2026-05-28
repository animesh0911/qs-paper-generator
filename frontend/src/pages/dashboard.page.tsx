import { useEffect, useState } from 'react';
import { assemblePaper, downloadPaperPdf, fetchMetadata } from '@/lib/api';
import type { Paper } from '@/types';
import { SECTION_TITLES } from '@/constants';
import { useAuth } from '@/hooks/useAuth.hook';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function Dashboard() {
  const { logout } = useAuth();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sectionTitles, setSectionTitles] =
    useState<Record<string, string>>(SECTION_TITLES);

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
      setPaper(await assemblePaper());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // Group items by section, preserving order.
  const sections: { key: string; items: Paper['items'] }[] = [];
  paper?.items.forEach((item) => {
    let group = sections.find((s) => s.key === item.section);
    if (!group) {
      group = { key: item.section, items: [] };
      sections.push(group);
    }
    group.items.push(item);
  });

  return (
    <div className="min-h-screen bg-secondary">
      <header className="flex items-center justify-between border-b bg-background px-6 py-3">
        <h1 className="font-semibold">Question Paper Generator</h1>
        <Button variant="ghost" size="sm" onClick={logout}>
          Sign out
        </Button>
      </header>

      <main className="mx-auto max-w-3xl p-6 space-y-4">
        <div className="flex items-center gap-3">
          <Button onClick={generate} disabled={busy}>
            {busy ? 'Generating…' : 'Generate paper'}
          </Button>
          {paper && (
            <Button
              variant="outline"
              onClick={() => downloadPaperPdf(paper.id)}
            >
              Download PDF
            </Button>
          )}
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}

        {paper && (
          <Card>
            <CardHeader>
              <CardTitle>{paper.title}</CardTitle>
              <p className="text-sm text-muted-foreground">
                Class 10 — Science · Maximum Marks: {paper.total_marks}
              </p>
            </CardHeader>
            <CardContent className="space-y-5">
              {sections.map((section) => (
                <div key={section.key}>
                  <h2 className="font-semibold mb-2">
                    {sectionTitles[section.key] ?? `Section ${section.key}`}
                  </h2>
                  <ol className="space-y-3">
                    {section.items.map((item) => (
                      <li key={item.order} className="text-sm">
                        <span className="font-medium">Q{item.order}.</span>{' '}
                        {item.question.text}{' '}
                        <span className="text-muted-foreground">
                          ({item.question.marks} mark
                          {item.question.marks !== 1 ? 's' : ''})
                        </span>
                        {item.question.options.length > 0 && (
                          <ul className="ml-6 mt-1 space-y-0.5 text-muted-foreground">
                            {item.question.options.map((o) => (
                              <li key={o.label}>
                                ({o.label}) {o.text}
                              </li>
                            ))}
                          </ul>
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
