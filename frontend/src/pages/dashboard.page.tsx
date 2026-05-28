import { useEffect, useMemo, useState } from 'react';
import {
  assemblePaper,
  downloadPaperPdf,
  fetchChapters,
  fetchMetadata,
} from '@/lib/api';
import type { AssembleRequest, Chapter, Paper } from '@/types';
import { SECTION_TITLES } from '@/constants';
import { useAuth } from '@/hooks/useAuth.hook';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

type Difficulty = NonNullable<AssembleRequest['difficulty']>;
const DIFFICULTIES: Difficulty[] = ['easy', 'standard', 'hard'];

export default function Dashboard() {
  const { logout } = useAuth();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sectionTitles, setSectionTitles] =
    useState<Record<string, string>>(SECTION_TITLES);

  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(new Set());
  const [weights, setWeights] = useState<Record<string, string>>({});
  const [difficulty, setDifficulty] = useState<Difficulty>('standard');

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
    fetchChapters()
      .then(setChapters)
      .catch(() => setChapters([]));
  }, []);

  function toggleChapter(slug: string) {
    setSelectedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  async function generate() {
    setBusy(true);
    setError('');
    try {
      const payload: AssembleRequest = {
        difficulty,
        chapter_slugs: Array.from(selectedSlugs),
        weights: Object.fromEntries(
          Array.from(selectedSlugs).flatMap((slug) => {
            const raw = weights[slug];
            const value = raw === undefined || raw === '' ? 1 : Number(raw);
            return Number.isFinite(value) ? [[slug, value]] : [];
          }),
        ),
      };
      setPaper(await assemblePaper(payload));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const sections = useMemo(() => {
    const groups: { key: string; items: Paper['items'] }[] = [];
    paper?.items.forEach((item) => {
      let group = groups.find((s) => s.key === item.section);
      if (!group) {
        group = { key: item.section, items: [] };
        groups.push(group);
      }
      group.items.push(item);
    });
    return groups;
  }, [paper]);

  const chapterNameBySlug = useMemo(
    () => Object.fromEntries(chapters.map((c) => [c.slug, c.name])),
    [chapters],
  );

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
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium mb-2">Difficulty</p>
              <div className="flex gap-2">
                {DIFFICULTIES.map((d) => (
                  <Button
                    key={d}
                    type="button"
                    size="sm"
                    variant={difficulty === d ? 'default' : 'outline'}
                    onClick={() => setDifficulty(d)}
                  >
                    {d}
                  </Button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-sm font-medium mb-2">
                Chapters{' '}
                <span className="text-muted-foreground font-normal">
                  (leave empty to use all)
                </span>
              </p>
              <ul className="space-y-1">
                {chapters.map((ch) => {
                  const selected = selectedSlugs.has(ch.slug);
                  return (
                    <li
                      key={ch.slug}
                      className="flex items-center gap-3 text-sm"
                    >
                      <label className="flex items-center gap-2 flex-1">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleChapter(ch.slug)}
                        />
                        <span>
                          {ch.order}. {ch.name}
                        </span>
                      </label>
                      {selected && (
                        <Input
                          type="number"
                          min={0}
                          step="0.1"
                          placeholder="weight"
                          className="w-24 h-8"
                          value={weights[ch.slug] ?? ''}
                          onChange={(e) =>
                            setWeights((prev) => ({
                              ...prev,
                              [ch.slug]: e.target.value,
                            }))
                          }
                        />
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>

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
          </CardContent>
        </Card>

        {paper && (
          <Card>
            <CardHeader>
              <CardTitle>{paper.title}</CardTitle>
              <p className="text-sm text-muted-foreground">
                Class 10 — Science · Maximum Marks: {paper.total_marks}
              </p>
            </CardHeader>
            <CardContent className="space-y-5">
              {(Object.keys(paper.coverage).length > 0 ||
                paper.unfilled.length > 0) && (
                <div className="space-y-2 rounded border bg-background p-3 text-sm">
                  {Object.keys(paper.coverage).length > 0 && (
                    <div>
                      <p className="font-medium">Per-chapter coverage</p>
                      <ul className="text-muted-foreground">
                        {Object.entries(paper.coverage)
                          .sort((a, b) => b[1] - a[1])
                          .map(([slug, count]) => (
                            <li key={slug}>
                              {chapterNameBySlug[slug] ?? slug}: {count}
                            </li>
                          ))}
                      </ul>
                    </div>
                  )}
                  {Object.keys(paper.cog_coverage).length > 0 && (
                    <div>
                      <p className="font-medium">Cognitive mix</p>
                      <p className="text-muted-foreground">
                        {Object.entries(paper.cog_coverage)
                          .map(([k, v]) => `${k}: ${v}`)
                          .join(' · ')}
                      </p>
                    </div>
                  )}
                  {paper.unfilled.length > 0 && (
                    <div>
                      <p className="font-medium text-destructive">
                        Unfilled slots ({paper.unfilled.length})
                      </p>
                      <ul className="text-muted-foreground">
                        {paper.unfilled.slice(0, 8).map((u) => (
                          <li key={u.slot_index}>
                            Slot {u.slot_index + 1} · {u.section} · {u.qtype} ·{' '}
                            {u.marks}m — {u.reason}
                          </li>
                        ))}
                        {paper.unfilled.length > 8 && (
                          <li>…and {paper.unfilled.length - 8} more</li>
                        )}
                      </ul>
                    </div>
                  )}
                </div>
              )}

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
