/**
 * Question Bank — a teacher browses every question extracted into their bank.
 *
 * Read-only view: filter by chapter, section, question type, and source, search
 * the question text, and page through the results. The `useQuestionBank` hook
 * owns the fetch + filter + pagination lifecycle; this page is presentation.
 *
 * @module QuestionBankPage
 */
import { useMemo } from 'react';
import { Library } from 'lucide-react';
import { useQuestionBank } from '@/hooks/useQuestionBank.hook';
import { SOURCE_TYPE_OPTIONS, sourceTypeLabel } from '@/lib/ingestion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { AppHeader } from '@/components/app-nav';
import { MathContent } from '@/components/math/math-content.component';
import type { BankQuestion, SourceType } from '@/types';

type LabelMap = Record<string, string>;

/**
 * Render a question's stem with KaTeX when it carries structured `content`,
 * falling back to the plain `text` when there are no content items (e.g. older
 * rows ingested before structured content was captured).
 */
function QuestionText({ question }: { question: BankQuestion }) {
  const stem = question.content?.stem;
  if (Array.isArray(stem) && stem.length > 0) {
    return <MathContent items={stem} />;
  }
  return <>{question.text}</>;
}

/**
 * One bank question rendered as a full card — mirrors the AI Q&A candidate
 * cards: the complete question text up top, MCQ options laid out, and a quiet
 * metadata line (chapter · section · type · marks · source) below. Reading the
 * actual question is the point, so nothing is truncated.
 */
function QuestionCard({
  question,
  typeLabels,
}: {
  question: BankQuestion;
  typeLabels: LabelMap;
}) {
  const meta = [
    question.chapter?.name,
    question.section ? `Section ${question.section}` : null,
    typeLabels[question.qtype] ?? question.qtype,
    `${question.marks} mark${question.marks === 1 ? '' : 's'}`,
    question.source_type ? sourceTypeLabel(question.source_type) : null,
  ].filter((part): part is string => Boolean(part));

  return (
    <li className="space-y-3 rounded-md border border-white/70 bg-white/70 p-4">
      <p className="text-sm leading-6 text-foreground">
        <QuestionText question={question} />
      </p>

      {question.options.length > 0 && (
        <ul className="space-y-1 pl-1 text-sm text-foreground">
          {question.options.map((option, index) => (
            <li key={option.label || index} className="flex gap-2">
              {option.label && (
                <span className="font-medium">{option.label}.</span>
              )}
              <span>{option.text}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        {meta.map((part, index) => (
          <span key={index} className="flex items-center gap-2">
            {index > 0 && <span aria-hidden="true">·</span>}
            {part}
          </span>
        ))}
      </div>
    </li>
  );
}

const selectClass =
  'h-10 w-full rounded-md border border-input bg-background px-3 text-sm ' +
  'ring-offset-background focus-visible:outline-none focus-visible:ring-2 ' +
  'focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50';

export default function QuestionBankPage() {
  const bank = useQuestionBank();
  const { filters, metadata } = bank;

  const typeLabels = useMemo<LabelMap>(
    () =>
      Object.fromEntries(
        (metadata?.question_types ?? []).map((t) => [t.code, t.label]),
      ),
    [metadata],
  );

  const pageStart = bank.count === 0 ? 0 : bank.offset + 1;
  const pageEnd = Math.min(bank.offset + bank.pageSize, bank.count);
  const canPrev = bank.offset > 0;
  const canNext = bank.offset + bank.pageSize < bank.count;

  return (
    <div className="min-h-screen bg-secondary">
      <AppHeader />

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:py-10">
        <Card className="overflow-hidden rounded-lg border-white/70 bg-white/80 shadow-none backdrop-blur-2xl">
          <CardHeader className="border-b border-white/70 bg-white/60 px-5 py-5 sm:px-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1.5">
                <CardTitle className="text-xl leading-7">
                  Question bank
                </CardTitle>
                <p className="max-w-xl text-[0.9375rem] leading-6 text-muted-foreground">
                  Every question extracted into your bank. Filter, search, and
                  review what’s available before you generate a paper.
                </p>
              </div>
              <span className="inline-flex w-fit items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs font-medium text-secondary-foreground">
                <Library className="size-3.5" aria-hidden="true" />
                {bank.count} {bank.count === 1 ? 'question' : 'questions'}
              </span>
            </div>
          </CardHeader>

          <CardContent className="space-y-5 bg-white/45 px-5 py-6 sm:px-6">
            {/* Filters */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <label className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">
                  Chapter
                </span>
                <select
                  className={selectClass}
                  value={filters.chapter}
                  onChange={(e) => bank.setFilter('chapter', e.target.value)}
                >
                  <option value="">All chapters</option>
                  {bank.chapters.map((chapter) => (
                    <option key={chapter.slug} value={chapter.slug}>
                      {chapter.order}. {chapter.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">
                  Section
                </span>
                <select
                  className={selectClass}
                  value={filters.section}
                  onChange={(e) => bank.setFilter('section', e.target.value)}
                >
                  <option value="">All sections</option>
                  {(metadata?.sections ?? []).map((s) => (
                    <option key={s.code} value={s.code}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">
                  Type
                </span>
                <select
                  className={selectClass}
                  value={filters.qtype}
                  onChange={(e) => bank.setFilter('qtype', e.target.value)}
                >
                  <option value="">All types</option>
                  {(metadata?.question_types ?? []).map((t) => (
                    <option key={t.code} value={t.code}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">
                  Source
                </span>
                <select
                  className={selectClass}
                  value={filters.source_type}
                  onChange={(e) =>
                    bank.setFilter('source_type', e.target.value as SourceType)
                  }
                >
                  <option value="">All sources</option>
                  {SOURCE_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Input
                placeholder="Search question text…"
                value={filters.search}
                onChange={(e) => bank.setFilter('search', e.target.value)}
                className="bg-background"
              />
              {bank.hasActiveFilters && (
                <Button
                  variant="outline"
                  onClick={bank.resetFilters}
                  className="shrink-0"
                >
                  Clear filters
                </Button>
              )}
            </div>

            {/* Results */}
            {bank.error ? (
              <p className="text-sm text-destructive" role="alert">
                {bank.error}
              </p>
            ) : bank.loading ? (
              <p className="py-10 text-center text-sm text-muted-foreground">
                Loading questions…
              </p>
            ) : bank.questions.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">
                {bank.hasActiveFilters
                  ? 'No questions match these filters.'
                  : 'No questions in the bank yet. Upload a paper to extract some.'}
              </p>
            ) : (
              <ul className="space-y-3" aria-label="Bank questions">
                {bank.questions.map((q) => (
                  <QuestionCard
                    key={q.id}
                    question={q}
                    typeLabels={typeLabels}
                  />
                ))}
              </ul>
            )}

            {/* Pagination */}
            {bank.count > 0 && (
              <div className="flex items-center justify-between border-t border-white/70 pt-4">
                <p className="text-xs text-muted-foreground">
                  Showing {pageStart}–{pageEnd} of {bank.count}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    disabled={!canPrev || bank.loading}
                    onClick={() =>
                      bank.goToPage(Math.max(0, bank.offset - bank.pageSize))
                    }
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    disabled={!canNext || bank.loading}
                    onClick={() => bank.goToPage(bank.offset + bank.pageSize)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
