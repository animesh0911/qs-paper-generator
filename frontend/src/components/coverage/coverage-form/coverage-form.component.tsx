/**
 * Paper setup surface for opening the editor in a few deliberate decisions.
 *
 * The component owns no generation state. It renders the selected CoverageForm
 * model in the chosen Review desk treatment without detaching from the real
 * workflow.
 *
 * @module CoverageFormView
 */
import type { ReactNode } from 'react';
import { Check, ChevronDown, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  type ChapterGroup,
  type CoverageForm,
} from '@/hooks/useCoverageForm.hook';
import type { Chapter } from '@/types';
import { cn } from '@/lib/utils';

export interface CoverageFormProps {
  form: CoverageForm;
  busy: boolean;
  onGenerate: () => void;
  trailing?: ReactNode;
}

export function CoverageFormView({
  form,
  busy,
  onGenerate,
  trailing,
}: CoverageFormProps) {
  const {
    formats,
    selectedFormatId,
    selectedSlugs,
    totalMarks,
    hasSelectedChapters,
    setSelectedFormatId,
  } = form;
  const generationDisabled = busy || !selectedFormatId || !hasSelectedChapters;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-background px-4 py-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-semibold">Class 10 · Science</p>
          <a
            href="/ai-qa"
            className="inline-flex h-8 w-fit items-center gap-1.5 rounded-md px-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Sparkles className="size-4" aria-hidden="true" />
            Question bank
          </a>
        </div>
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_11rem]">
          <div className="space-y-2">
            <label
              htmlFor="paper-format"
              className="block text-[0.8125rem] font-medium leading-5"
            >
              PaperFormat
            </label>
            <select
              id="paper-format"
              className="flex h-11 w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground transition-colors hover:bg-secondary/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={selectedFormatId}
              onChange={(event) => setSelectedFormatId(event.target.value)}
              disabled={formats.length === 0}
            >
              {formats.length === 0 ? (
                <option value="">No formats available</option>
              ) : (
                formats.map((format) => (
                  <option key={format.format_id} value={format.format_id}>
                    {format.name}
                  </option>
                ))
              )}
            </select>
            {formats.length === 0 && (
              <p className="text-xs text-destructive">
                No active PaperFormat is available. Ask an admin to seed one.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <label
              htmlFor="paper-total-marks"
              className="block text-[0.8125rem] font-medium leading-5"
            >
              Total marks
            </label>
            <input
              id="paper-total-marks"
              type="number"
              min={1}
              className="flex h-11 w-full rounded-md border bg-secondary/45 px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={totalMarks}
              readOnly
            />
          </div>
        </div>
      </div>

      <PaperStructureSummary form={form} />
      <ReviewDeskVariant form={form} />

      <div className="sticky bottom-0 z-10 flex flex-col gap-2 rounded-lg border bg-background/95 px-4 py-3 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          {hasSelectedChapters
            ? `${selectedSlugs.size} chapter${selectedSlugs.size === 1 ? '' : 's'} selected`
            : 'Chapter selection required'}
        </p>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Button onClick={onGenerate} disabled={generationDisabled}>
            {busy ? 'Generating...' : 'Generate paper'}
          </Button>
          {trailing}
        </div>
      </div>
    </div>
  );
}

function ReviewDeskVariant({ form }: { form: CoverageForm }) {
  return (
    <ChapterSelectionShell
      form={form}
      heading="Chapters"
      description="Pick at least one chapter. Use group controls for faster setup."
    >
      <ChapterGroups form={form} />
    </ChapterSelectionShell>
  );
}

function ChapterSelectionShell({
  form,
  heading,
  description,
  children,
}: {
  form: CoverageForm;
  heading: string;
  description: string;
  children: ReactNode;
}) {
  const {
    chaptersLoading,
    chaptersError,
    chapterGroups,
    hasSelectedChapters,
    selectAllChapters,
    clearAllChapters,
  } = form;

  return (
    <section
      className="rounded-lg border bg-background p-4"
      aria-labelledby="paper-chapters-heading"
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2
            id="paper-chapters-heading"
            className="text-base font-semibold leading-6"
          >
            {heading}
          </h2>
          <p className="text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={chaptersLoading || Boolean(chaptersError)}
            onClick={selectAllChapters}
          >
            Select all Chapters
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={chaptersLoading || Boolean(chaptersError)}
            onClick={clearAllChapters}
          >
            Clear
          </Button>
        </div>
      </div>

      <div className="mt-3">
        {chaptersLoading ? (
          <p className="rounded-lg border bg-background p-3 text-sm text-muted-foreground">
            Loading chapters...
          </p>
        ) : chaptersError ? (
          <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            Could not load chapters: {chaptersError}
          </p>
        ) : chapterGroups.length === 0 ? (
          <p className="rounded-lg border bg-background p-3 text-sm text-muted-foreground">
            No chapters found.
          </p>
        ) : (
          children
        )}
      </div>

      {!hasSelectedChapters && !chaptersLoading && (
        <p className="mt-3 text-sm text-destructive">
          Select at least one Chapter to generate a paper.
        </p>
      )}
    </section>
  );
}

function ChapterGroups({ form }: { form: CoverageForm }) {
  return (
    <div className="space-y-3">
      {form.chapterGroups.map((group) => (
        <ChapterGroupFieldset
          key={group.subjectArea}
          group={group}
          form={form}
        />
      ))}
    </div>
  );
}

function ChapterGroupFieldset({
  group,
  form,
}: {
  group: ChapterGroup;
  form: CoverageForm;
}) {
  const selectedCount = group.chapters.filter((chapter) =>
    form.selectedSlugs.has(chapter.slug),
  ).length;
  const groupSelected = selectedCount === group.chapters.length;

  return (
    <fieldset className="rounded-lg border bg-background p-3">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <legend className="text-sm font-semibold">{group.subjectArea}</legend>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {selectedCount} of {group.chapters.length} selected
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => form.toggleChapterGroup(group.subjectArea)}
        >
          {groupSelected ? 'Clear group' : 'Select group'}
        </Button>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2">
        {group.chapters.map((chapter) => (
          <li key={chapter.slug}>
            <ChapterChoice
              chapter={chapter}
              selected={form.selectedSlugs.has(chapter.slug)}
              onToggle={() => form.toggleChapter(chapter.slug)}
            />
          </li>
        ))}
      </ul>
    </fieldset>
  );
}

function ChapterChoice({
  chapter,
  selected,
  onToggle,
}: {
  chapter: Chapter;
  selected: boolean;
  onToggle: () => void;
}) {
  const chapterInputId = `paper-chapter-${chapter.slug}`;

  return (
    <label
      htmlFor={chapterInputId}
      className={cn(
        'flex h-full cursor-pointer items-start gap-3 rounded-md text-sm leading-5 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring',
        'border px-3 py-3',
        selected
          ? 'border-primary bg-secondary text-foreground'
          : 'border-border bg-background hover:bg-secondary/55',
      )}
    >
      <input
        id={chapterInputId}
        type="checkbox"
        className="sr-only"
        checked={selected}
        onChange={onToggle}
      />
      <span
        className={cn(
          'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md',
          selected
            ? 'bg-primary text-primary-foreground'
            : 'border bg-background text-transparent',
        )}
        aria-hidden="true"
      >
        <Check className="size-3.5" />
      </span>
      <span className="block min-w-0 flex-1">
        <span className="block font-medium">
          {chapter.order}. {chapter.name}
        </span>
      </span>
    </label>
  );
}

function PaperStructureSummary({ form }: { form: CoverageForm }) {
  const { structureSummary, selectedSlugs } = form;

  return (
    <aside className="rounded-lg border bg-background p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[0.8125rem] font-semibold">Paper structure</p>
        <dl className="grid flex-1 grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <SummaryItem
            label="Total marks"
            value={structureSummary.totalMarks}
          />
          <SummaryItem label="Sections" value={structureSummary.sectionCount} />
          <SummaryItem
            label="Questions"
            value={`≈ ${structureSummary.approximateQuestionCount}`}
          />
          <SummaryItem label="Chapters" value={selectedSlugs.size} />
        </dl>
      </div>
      <details className="group mt-3 border-t pt-3">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-xs font-medium text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          Marks by QuestionType
          <ChevronDown
            className="size-3.5 transition-transform group-open:rotate-180"
            aria-hidden="true"
          />
        </summary>
        <ul className="mt-2 grid gap-1.5 text-sm sm:grid-cols-2 lg:grid-cols-5">
          {Object.entries(structureSummary.marksByQuestionType).map(
            ([type, marks]) => (
              <li
                key={type}
                className="flex justify-between gap-3 rounded-md bg-secondary/55 px-2 py-1.5"
              >
                <span>{type}</span>
                <span className="font-medium">{marks}</span>
              </li>
            ),
          )}
        </ul>
      </details>
    </aside>
  );
}

function SummaryItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-md bg-secondary/60 px-2 py-1.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-semibold">{value}</dd>
    </div>
  );
}
