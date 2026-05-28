/**
 * Renders an assembled `Paper`: report panel + sections + questions.
 *
 * Receives a fully-resolved `Paper` plus the lookup tables it needs
 * (`sectionTitles`, `chapterNameBySlug`). Pure — no fetches, no state
 * beyond the section-grouping memo. The forwarded ref is used by the
 * dashboard to scroll the card into view after generation.
 *
 * @module PaperPreview
 */
import { forwardRef, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { Paper } from '@/types';

export interface PaperPreviewProps {
  paper: Paper;
  sectionTitles: Record<string, string>;
  chapterNameBySlug: Record<string, string>;
}

export const PaperPreview = forwardRef<HTMLDivElement, PaperPreviewProps>(
  function PaperPreview({ paper, sectionTitles, chapterNameBySlug }, ref) {
    const sections = useMemo(() => {
      const groups: { key: string; items: Paper['items'] }[] = [];
      paper.items.forEach((item) => {
        let group = groups.find((s) => s.key === item.section);
        if (!group) {
          group = { key: item.section, items: [] };
          groups.push(group);
        }
        group.items.push(item);
      });
      return groups;
    }, [paper]);

    const { coverage, cog_coverage, unfilled } = paper.report;
    const hasReport = Object.keys(coverage).length > 0 || unfilled.length > 0;

    return (
      <Card ref={ref}>
        <CardHeader>
          <CardTitle>{paper.title}</CardTitle>
          <p className="text-sm text-muted-foreground">
            Class 10 — Science · Maximum Marks: {paper.total_marks}
          </p>
        </CardHeader>
        <CardContent className="space-y-5">
          {hasReport && (
            <div className="space-y-2 rounded border bg-background p-3 text-sm">
              {Object.keys(coverage).length > 0 && (
                <div>
                  <p className="font-medium">Per-chapter coverage</p>
                  <ul className="text-muted-foreground">
                    {Object.entries(coverage)
                      .sort((a, b) => b[1] - a[1])
                      .map(([slug, count]) => (
                        <li key={slug}>
                          {chapterNameBySlug[slug] ?? slug}: {count}
                        </li>
                      ))}
                  </ul>
                </div>
              )}
              {Object.keys(cog_coverage).length > 0 && (
                <div>
                  <p className="font-medium">Cognitive mix</p>
                  <p className="text-muted-foreground">
                    {Object.entries(cog_coverage)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(' · ')}
                  </p>
                </div>
              )}
              {unfilled.length > 0 && (
                <div>
                  <p className="font-medium text-destructive">
                    Unfilled slots ({unfilled.length})
                  </p>
                  <ul className="text-muted-foreground">
                    {unfilled.slice(0, 8).map((u) => (
                      <li key={u.slot_index}>
                        Slot {u.slot_index + 1} · {u.section} · {u.qtype} ·{' '}
                        {u.marks}m — {u.reason}
                      </li>
                    ))}
                    {unfilled.length > 8 && (
                      <li>…and {unfilled.length - 8} more</li>
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
    );
  },
);
