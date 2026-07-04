/**
 * Question Bank — a teacher browses every question extracted into their bank.
 *
 * Read-only view: filter by chapter, section, question type, and source, search
 * the question text, and page through the results. The `useQuestionBank` hook
 * owns the fetch + filter + pagination lifecycle; this page is presentation.
 *
 * Layout follows the "Exam Desk" system: quiet app chrome, a flat filter panel,
 * and a hairline-divided list where each question reads like the final paper —
 * a stable index and marks label frame the serif question body, mirroring the
 * editor's locked slot.
 *
 * @module QuestionBankPage
 */
import { useMemo, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Library, Search, Upload } from 'lucide-react';
import { useQuestionBank } from '@/hooks/useQuestionBank.hook';
import { SOURCE_TYPE_OPTIONS, sourceTypeLabel } from '@/lib/ingestion';
import { Button, buttonVariants } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, type SelectOption } from '@/components/ui/select';
import { AppHeader } from '@/components/app-nav';
import { QuestionRegions } from '@/components/question/question-regions.component';
import type { BankQuestion, DocQuestionContent, SourceType } from '@/types';

type LabelMap = Record<string, string>;

/**
 * One question as a divided list row: a stable index on the left, the serif
 * question body in the middle (rendered exactly as the editor's locked slot),
 * and the marks label on the right. A quiet metadata line — type chip, chapter,
 * section, source — sits below. Marks appear once (the right label), never
 * doubled into the metadata, per the One-Mark rule.
 */
function QuestionRow({
  question,
  index,
  typeLabels,
}: {
  question: BankQuestion;
  index: number;
  typeLabels: LabelMap;
}) {
  const meta = [
    question.chapter?.name,
    question.section ? `Section ${question.section}` : null,
    question.source_type ? sourceTypeLabel(question.source_type) : null,
  ].filter((part): part is string => Boolean(part));

  return (
    <li className="grid grid-cols-[1.75rem_minmax(0,1fr)_auto] gap-x-3 px-4 py-4 transition-colors hover:bg-secondary/50 sm:gap-x-4 sm:px-6">
      <span className="qpg-bank-index pt-px text-right" aria-hidden="true">
        {index}.
      </span>

      <div className="min-w-0 space-y-2">
        <QuestionRegions
          content={question.content as DocQuestionContent}
          fallbackText={question.text}
          fallbackOptions={question.options}
        />

        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center rounded bg-secondary px-1.5 py-0.5 text-[0.6875rem] font-medium text-secondary-foreground">
            {typeLabels[question.qtype] ?? question.qtype}
          </span>
          {meta.map((part, partIndex) => (
            <span key={part} className="inline-flex items-center gap-2">
              {partIndex > 0 && <span aria-hidden="true">·</span>}
              <span className={partIndex === 0 ? 'text-foreground/80' : ''}>
                {part}
              </span>
            </span>
          ))}
        </div>
      </div>

      <span className="qpg-bank-marks pt-px text-right">
        {question.marks} mark{question.marks === 1 ? '' : 's'}
      </span>
    </li>
  );
}

/** A skeleton row matching the real row's three-column rhythm. */
function SkeletonRow() {
  return (
    <li className="grid grid-cols-[1.75rem_minmax(0,1fr)_auto] gap-x-3 px-4 py-4 sm:gap-x-4 sm:px-6">
      <div className="h-4 w-4 justify-self-end rounded bg-muted motion-safe:animate-pulse" />
      <div className="space-y-2">
        <div className="h-4 w-11/12 rounded bg-muted motion-safe:animate-pulse" />
        <div className="h-4 w-3/5 rounded bg-muted motion-safe:animate-pulse" />
        <div className="h-3 w-40 rounded bg-muted motion-safe:animate-pulse" />
      </div>
      <div className="h-4 w-12 rounded bg-muted motion-safe:animate-pulse" />
    </li>
  );
}

/** Centered empty / error state that teaches the next action. */
function StatusPanel({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
      <div className="flex size-11 items-center justify-center rounded-full bg-secondary text-muted-foreground">
        {icon}
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mx-auto max-w-sm text-sm text-muted-foreground">
          {children}
        </p>
      </div>
      {action}
    </div>
  );
}

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

  const chapterOptions = useMemo<SelectOption[]>(
    () => [
      { value: '', label: 'All chapters' },
      ...bank.chapters.map((c) => ({
        value: c.slug,
        label: `${c.order}. ${c.name}`,
      })),
    ],
    [bank.chapters],
  );

  const sectionOptions = useMemo<SelectOption[]>(
    () => [
      { value: '', label: 'All sections' },
      ...(metadata?.sections ?? []).map((s) => ({
        value: s.code,
        label: s.label,
      })),
    ],
    [metadata],
  );

  const typeOptions = useMemo<SelectOption[]>(
    () => [
      { value: '', label: 'All types' },
      ...(metadata?.question_types ?? []).map((t) => ({
        value: t.code,
        label: t.label,
      })),
    ],
    [metadata],
  );

  const sourceTypeOptions = useMemo<SelectOption[]>(
    () => [
      { value: '', label: 'All sources' },
      ...SOURCE_TYPE_OPTIONS.map((o) => ({ value: o.value, label: o.label })),
    ],
    [],
  );

  const paperOptions = useMemo<SelectOption[]>(
    () => [
      { value: '', label: 'All papers' },
      ...bank.sources.map((s) => ({
        value: s.value,
        label: s.label,
        count: s.count,
      })),
    ],
    [bank.sources],
  );

  const pageStart = bank.count === 0 ? 0 : bank.offset + 1;
  const pageEnd = Math.min(bank.offset + bank.pageSize, bank.count);
  const canPrev = bank.offset > 0;
  const canNext = bank.offset + bank.pageSize < bank.count;

  return (
    <div className="min-h-screen bg-secondary">
      <AppHeader />

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:py-10">
        {/* Page header — on the chrome, above the working panel. */}
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-1">
            <h1 className="text-xl font-semibold leading-7 text-foreground">
              Question bank
            </h1>
            <p className="max-w-xl text-sm leading-6 text-muted-foreground">
              Every question extracted into your bank. Filter, search, and
              review what’s available before you generate a paper.
            </p>
          </div>
          <span
            className="inline-flex w-fit items-center gap-1.5 rounded-md bg-background px-2.5 py-1 text-xs font-medium text-foreground shadow-sm ring-1 ring-border"
            role="status"
          >
            <Library
              className="size-3.5 text-muted-foreground"
              aria-hidden="true"
            />
            {bank.count.toLocaleString()}{' '}
            {bank.count === 1 ? 'question' : 'questions'}
          </span>
        </div>

        <div className="overflow-hidden rounded-lg border bg-background shadow-sm">
          {/* Filters */}
          <div className="space-y-3 border-b bg-secondary/30 px-4 py-4 sm:px-6">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Select
                label="Chapter"
                value={filters.chapter}
                options={chapterOptions}
                onChange={(v) => bank.setFilter('chapter', v)}
              />
              <Select
                label="Section"
                value={filters.section}
                options={sectionOptions}
                onChange={(v) => bank.setFilter('section', v)}
              />
              <Select
                label="Type"
                value={filters.qtype}
                options={typeOptions}
                onChange={(v) => bank.setFilter('qtype', v)}
              />
              <Select
                label="Source"
                value={filters.source_type}
                options={sourceTypeOptions}
                onChange={(v) => bank.setFilter('source_type', v as SourceType)}
              />
              <Select
                label="Paper"
                value={filters.source}
                options={paperOptions}
                onChange={(v) => bank.setFilter('source', v)}
              />
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="relative flex-1">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />
                <Input
                  placeholder="Search question text…"
                  aria-label="Search question text"
                  value={filters.search}
                  onChange={(e) => bank.setFilter('search', e.target.value)}
                  className="pl-9"
                />
              </div>
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
          </div>

          {/* Results */}
          {bank.error ? (
            <StatusPanel
              icon={<Library className="size-5" />}
              title="Couldn’t load questions"
            >
              {bank.error}
            </StatusPanel>
          ) : bank.loading ? (
            <ul aria-hidden="true" className="divide-y">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonRow key={i} />
              ))}
            </ul>
          ) : bank.questions.length === 0 ? (
            bank.hasActiveFilters ? (
              <StatusPanel
                icon={<Search className="size-5" />}
                title="No matches"
                action={
                  <Button variant="outline" onClick={bank.resetFilters}>
                    Clear filters
                  </Button>
                }
              >
                No questions match these filters. Try widening or clearing them.
              </StatusPanel>
            ) : (
              <StatusPanel
                icon={<Upload className="size-5" />}
                title="Your bank is empty"
                action={
                  <Link to="/upload" className={buttonVariants()}>
                    Upload papers
                  </Link>
                }
              >
                Upload a question paper and we’ll extract its questions into
                your bank.
              </StatusPanel>
            )
          ) : (
            <ul className="divide-y" aria-label="Bank questions">
              {bank.questions.map((q, i) => (
                <QuestionRow
                  key={q.id}
                  question={q}
                  index={bank.offset + i + 1}
                  typeLabels={typeLabels}
                />
              ))}
            </ul>
          )}

          {/* Pagination */}
          {bank.count > 0 && !bank.error && (
            <div className="flex items-center justify-between gap-3 border-t bg-secondary/30 px-4 py-3 sm:px-6">
              <p className="text-xs text-muted-foreground">
                Showing{' '}
                <span className="font-medium text-foreground">
                  {pageStart.toLocaleString()}–{pageEnd.toLocaleString()}
                </span>{' '}
                of {bank.count.toLocaleString()}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!canPrev || bank.loading}
                  onClick={() =>
                    bank.goToPage(Math.max(0, bank.offset - bank.pageSize))
                  }
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!canNext || bank.loading}
                  onClick={() => bank.goToPage(bank.offset + bank.pageSize)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
