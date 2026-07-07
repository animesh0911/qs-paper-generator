/**
 * Paper setup surface for opening the editor in a few deliberate decisions.
 *
 * The component owns no generation state. It renders the selected CoverageForm
 * model in the chosen Review desk treatment without detaching from the real
 * workflow.
 *
 * @module CoverageFormView
 */
import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react';
import {
  ArrowUpRight,
  Bot,
  Check,
  ChevronDown,
  FileText,
  Library,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { sourceReviewHref } from '@/lib/source-review';
import {
  type ChapterGroup,
  type CoverageForm,
} from '@/hooks/useCoverageForm.hook';
import type { Chapter, PaperSourceSummary } from '@/types';
import { cn } from '@/lib/utils';

export interface CoverageFormProps {
  form: CoverageForm;
  busy: boolean;
  onGenerate: () => void;
  trailing?: ReactNode;
}

/** Teacher-facing labels for the contract QuestionType codes. */
const QUESTION_TYPE_LABELS: Record<string, string> = {
  mcq: 'MCQ',
  assertion_reason: 'Assertion-Reason',
  very_short_answer: 'Very short answer',
  short_answer: 'Short answer',
  long_answer: 'Long answer',
  case_based: 'Case-based',
};

export function CoverageFormView({
  form,
  busy,
  onGenerate,
  trailing,
}: CoverageFormProps) {
  const hasSelectedSources = form.selectedSourceKeys.size > 0;
  const hasGenerationScope = form.hasSelectedChapters || hasSelectedSources;
  const generationDisabled =
    busy || !form.selectedFormatId || !hasGenerationScope;

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
      <div className="min-w-0 space-y-4">
        <PaperSetupHeader form={form} />
        <PaperStructureSummary form={form} />
        <ScopeSelectionList form={form} />
      </div>

      <PaperScopePanel
        form={form}
        busy={busy}
        generationDisabled={generationDisabled}
        onGenerate={onGenerate}
      >
        {trailing}
      </PaperScopePanel>
    </div>
  );
}

function PaperSetupHeader({ form }: { form: CoverageForm }) {
  const { formats, selectedFormatId, totalMarks, setSelectedFormatId } = form;

  return (
    <div className="rounded-lg border bg-background p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">Class 10 · Science</p>
          <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
            Board-style paper setup
          </p>
        </div>
        <a
          href="/question-bank"
          className="inline-flex h-9 w-fit items-center gap-1.5 rounded-md border bg-background px-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Library className="size-4" aria-hidden="true" />
          Question bank
        </a>
      </div>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_11rem]">
        <div className="space-y-2">
          <label
            htmlFor="paper-format"
            className="block text-[0.8125rem] font-medium leading-5"
          >
            Paper format
          </label>
          <select
            id="paper-format"
            className="flex h-11 w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground transition-colors hover:bg-secondary/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
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
            <p className="text-xs text-destructive" role="alert">
              No active paper format is available. Ask an admin to seed one.
            </p>
          )}
        </div>

        <div className="space-y-2">
          <p
            id="paper-total-marks-label"
            className="block text-[0.8125rem] font-medium leading-5"
          >
            Total marks
          </p>
          <output
            aria-labelledby="paper-total-marks-label"
            className="flex h-11 w-full items-center rounded-md border bg-secondary/45 px-3 py-2 text-sm font-semibold text-foreground"
          >
            {totalMarks}
          </output>
        </div>
      </div>
    </div>
  );
}

function ScopeSelectionList({ form }: { form: CoverageForm }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <ChapterSelectionShell
        form={form}
        heading="Choose chapters"
        description="Open a focused chapter screen. Approve to apply the strict paper filter."
      />
      <SourceSelectionSection form={form} />
    </div>
  );
}

function PaperScopePanel({
  form,
  busy,
  generationDisabled,
  onGenerate,
  children,
}: {
  form: CoverageForm;
  busy: boolean;
  generationDisabled: boolean;
  onGenerate: () => void;
  children?: ReactNode;
}) {
  const selectedChapterNames = Array.from(form.selectedSlugs).map((slug) => {
    const chapter = form.chapters.find((item) => item.slug === slug);
    return form.chapterNameBySlug[slug] || chapter?.name || slug;
  });
  const sourceTitleByKey = Object.fromEntries(
    form.sources.map((source) => [source.key, source.title]),
  );
  const selectedSourceTitles = Array.from(form.selectedSourceKeys).map(
    (key) => sourceTitleByKey[key] || key,
  );
  const hasChapters = selectedChapterNames.length > 0;
  const hasSources = selectedSourceTitles.length > 0;

  return (
    <aside
      className="space-y-3 rounded-lg border bg-background p-4 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-auto"
      aria-labelledby="paper-scope-heading"
    >
      <div>
        <p className="text-xs font-medium text-muted-foreground">Scope</p>
        <h2 id="paper-scope-heading" className="mt-1 text-base font-semibold">
          Paper scope
        </h2>
      </div>

      <ScopeBlock
        title="Chapters"
        badge="Filter"
        empty="None selected yet"
        items={selectedChapterNames}
        moreCount={Math.max(0, selectedChapterNames.length - 4)}
      />

      <ScopeBlock
        title="Sources"
        badge="Priority"
        empty="Automatic balance"
        items={selectedSourceTitles}
        moreCount={Math.max(0, selectedSourceTitles.length - 4)}
      />

      <p className="border-t pt-3 text-xs leading-5 text-muted-foreground">
        {readinessMessage(hasChapters, hasSources)}
      </p>

      <div className="space-y-2 border-t pt-4">
        <Button
          className="w-full"
          onClick={onGenerate}
          disabled={generationDisabled}
        >
          {busy ? 'Generating…' : 'Generate paper'}
        </Button>
        {children}
      </div>
    </aside>
  );
}

function ScopeBlock({
  title,
  badge,
  empty,
  items,
  moreCount,
}: {
  title: string;
  badge: string;
  empty: string;
  items: string[];
  moreCount: number;
}) {
  const visibleItems = items.slice(0, 4);

  return (
    <section className="border-t pt-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">{title}</h3>
        <span className="rounded-md border bg-secondary/35 px-2 py-0.5 text-xs font-medium text-muted-foreground">
          {badge}
        </span>
      </div>
      {visibleItems.length > 0 ? (
        <ul className="mt-2 flex flex-wrap gap-1.5 text-xs">
          {visibleItems.map((item) => (
            <li
              key={item}
              className="max-w-full truncate rounded-md border bg-background px-2 py-1 text-foreground/85"
            >
              {item}
            </li>
          ))}
          {moreCount > 0 && (
            <li className="rounded-md border bg-background px-2 py-1 text-muted-foreground">
              +{moreCount} more
            </li>
          )}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">{empty}</p>
      )}
    </section>
  );
}

function readinessMessage(hasChapters: boolean, hasSources: boolean) {
  if (hasChapters && hasSources) return 'Ready: chapters + source priority.';
  if (hasChapters) return 'Ready: selected chapters.';
  if (hasSources) return 'Ready: source priority.';
  return 'Choose chapters or sources to generate.';
}

function SelectionLauncher({
  title,
  description,
  summary,
  onOpen,
}: {
  title: string;
  description: string;
  summary: string;
  onOpen: () => void;
}) {
  return (
    <section className="rounded-lg border bg-background p-4">
      <div className="flex h-full flex-col gap-4">
        <div className="min-w-0">
          <h2 className="text-base font-semibold leading-6">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        </div>
        <div className="mt-auto flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="rounded-md bg-secondary/70 px-2 py-1.5 text-sm font-medium">
            {summary}
          </p>
          <Button type="button" variant="outline" onClick={onOpen}>
            {title}
          </Button>
        </div>
      </div>
    </section>
  );
}

function SelectionDialog({
  title,
  description,
  children,
  onCancel,
  onApprove,
}: {
  title: string;
  description: string;
  children: ReactNode;
  onCancel: () => void;
  onApprove: () => void;
}) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previousActiveElement = document.activeElement;
    document.body.style.overflow = 'hidden';
    dialogRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      if (previousActiveElement instanceof HTMLElement) {
        previousActiveElement.focus();
      }
    };
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key !== 'Tab') return;

    const focusable = getFocusableElements(dialogRef.current);
    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-stretch bg-background p-0 sm:items-center sm:bg-foreground/20 sm:p-6">
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="flex h-dvh w-full flex-col overflow-hidden bg-background focus:outline-none sm:mx-auto sm:h-[min(42rem,calc(100vh-3rem))] sm:max-w-4xl sm:rounded-lg sm:border"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        onKeyDown={handleKeyDown}
      >
        <div className="flex items-start justify-between gap-3 border-b p-4 sm:p-5">
          <div className="min-w-0">
            <h2 id={titleId} className="text-lg font-semibold leading-7">
              {title}
            </h2>
            <p
              id={descriptionId}
              className="mt-1 text-sm leading-6 text-muted-foreground"
            >
              {description}
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="-mr-2 -mt-2 shrink-0"
            aria-label="Close selection dialog"
            onClick={onCancel}
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
          {children}
        </div>
        <div className="flex flex-col-reverse gap-2 border-t bg-background p-4 sm:flex-row sm:justify-end">
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" onClick={onApprove}>
            Approve selection
          </Button>
        </div>
      </div>
    </div>
  );
}

function SourceSelectionSection({ form }: { form: CoverageForm }) {
  const [open, setOpen] = useState(false);
  const [draftKeys, setDraftKeys] = useState<Set<string>>(
    () => new Set(form.selectedSourceKeys),
  );
  const selectedCount = form.selectedSourceKeys.size;
  const hasChapterFilter = form.selectedSlugs.size > 0;
  const matchingQuestionCount = form.sources.reduce(
    (sum, source) => sum + sourceMatchingCount(source, hasChapterFilter),
    0,
  );
  const totalQuestionCount = form.sources.reduce(
    (sum, source) => sum + source.question_count,
    0,
  );
  const sourceSummary = selectedCount
    ? `${selectedCount} selected`
    : form.sourcesLoading
      ? 'Loading sources'
      : form.sources.length > 0
        ? 'Automatic balance'
        : 'No sources yet';

  function openDialog() {
    setDraftKeys(new Set(form.selectedSourceKeys));
    setOpen(true);
  }

  function toggleDraftSource(key: string) {
    setDraftKeys((current) => toggleSetValue(current, key));
  }

  function approveSources() {
    reconcileSelection(form.selectedSourceKeys, draftKeys, form.toggleSource);
    setOpen(false);
  }

  return (
    <>
      <SelectionLauncher
        title="Choose sources"
        description="Optional priority for the first draft. Alternatives stay wider."
        summary={sourceSummary}
        onOpen={openDialog}
      />
      {open && (
        <SelectionDialog
          title="Choose sources"
          description={
            hasChapterFilter
              ? 'These sources will be tried first for the selected chapters.'
              : 'Select sources to generate without chapter filters, or cancel to keep automatic balance.'
          }
          onCancel={() => setOpen(false)}
          onApprove={approveSources}
        >
          <div className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-6 text-muted-foreground">
                {draftKeys.size > 0
                  ? `${draftKeys.size} source${draftKeys.size === 1 ? '' : 's'} selected for first picks.`
                  : hasChapterFilter
                    ? 'Leave empty to let the picker balance across compatible questions.'
                    : 'Select sources to generate without chapter filters.'}
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={form.sourcesLoading || form.sources.length === 0}
                  onClick={() =>
                    setDraftKeys(
                      new Set(form.sources.map((source) => source.key)),
                    )
                  }
                >
                  Select all shown
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={form.sourcesLoading || draftKeys.size === 0}
                  onClick={() => setDraftKeys(new Set())}
                >
                  Clear
                </Button>
              </div>
            </div>

            <div className="grid gap-2 text-sm sm:grid-cols-3">
              <SummaryItem
                label="Match count"
                value={`${matchingQuestionCount}/${totalQuestionCount}`}
              />
              <SummaryItem label="Sources shown" value={form.sources.length} />
              <SummaryItem
                label="Questions in sources"
                value={totalQuestionCount}
              />
            </div>

            {form.sourcesLoading && form.sources.length === 0 ? (
              <p className="rounded-lg border bg-background p-3 text-sm text-muted-foreground">
                Loading sources…
              </p>
            ) : form.sourcesError && form.sources.length === 0 ? (
              <p
                className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
                role="alert"
              >
                Could not load sources: {form.sourcesError}
              </p>
            ) : form.sources.length === 0 ? (
              <p className="rounded-lg border bg-secondary/45 p-3 text-sm leading-6 text-muted-foreground">
                No tagged sources are available yet. Choose chapters to generate
                from the wider bank, or upload a paper first.
              </p>
            ) : (
              <div className="space-y-2">
                {form.sourcesError && (
                  <p
                    className="rounded-md border bg-secondary/35 px-3 py-2 text-xs leading-5 text-muted-foreground"
                    role="status"
                  >
                    Showing last loaded sources.
                  </p>
                )}
                <ul className="divide-y rounded-lg border">
                  {form.sources.map((source) => (
                    <SourceChoice
                      key={source.key}
                      source={source}
                      selected={draftKeys.has(source.key)}
                      hasChapterFilter={hasChapterFilter}
                      reviewHref={sourceReviewHref(source.key)}
                      onToggle={() => toggleDraftSource(source.key)}
                    />
                  ))}
                </ul>
              </div>
            )}
          </div>
        </SelectionDialog>
      )}
    </>
  );
}

function SourceChoice({
  source,
  selected,
  hasChapterFilter,
  reviewHref,
  onToggle,
}: {
  source: PaperSourceSummary;
  selected: boolean;
  hasChapterFilter: boolean;
  reviewHref: string | null;
  onToggle: () => void;
}) {
  const sourceInputId = `paper-source-${source.key.replace(/[^a-z0-9_-]/gi, '-')}`;
  const matchingCount = sourceMatchingCount(source, hasChapterFilter);

  return (
    <li
      className={cn(
        'grid gap-2 px-3 py-3 text-sm transition-colors sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center',
        selected ? 'bg-secondary text-foreground' : 'bg-background',
      )}
    >
      <label
        htmlFor={sourceInputId}
        className="grid min-w-0 cursor-pointer grid-cols-[auto_minmax(0,1fr)_auto] gap-3 rounded-md focus-within:ring-2 focus-within:ring-ring sm:items-center"
      >
        <input
          id={sourceInputId}
          type="checkbox"
          className="sr-only"
          checked={selected}
          onChange={onToggle}
        />
        <span
          className={cn(
            'mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md sm:mt-0',
            selected
              ? 'bg-primary text-primary-foreground'
              : 'border bg-background text-muted-foreground',
          )}
          aria-hidden="true"
        >
          {source.kind === 'ai_session' ? (
            <Bot className="size-4" />
          ) : (
            <FileText className="size-4" />
          )}
        </span>
        <span className="min-w-0">
          <span className="block truncate font-medium">{source.title}</span>
          <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">
            {source.detail || 'Tagged source'} ·{' '}
            {formatSourceDate(source.created_at)}
          </span>
        </span>
        <span
          className={cn(
            'mt-1 flex size-5 shrink-0 items-center justify-center justify-self-end rounded-md sm:mt-0',
            selected
              ? 'bg-primary text-primary-foreground'
              : 'border bg-background text-transparent',
          )}
          aria-hidden="true"
        >
          <Check className="size-3.5" />
        </span>
      </label>

      <div className="flex flex-wrap items-center gap-1.5 pl-11 sm:justify-end sm:pl-0">
        <span className="rounded-md bg-secondary/70 px-2.5 py-1 text-xs font-medium tabular-nums text-foreground">
          {matchingCount}/{source.question_count} match count
        </span>
        {reviewHref && (
          <a
            href={reviewHref}
            className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Review
            <ArrowUpRight className="size-3" aria-hidden="true" />
          </a>
        )}
      </div>
    </li>
  );
}

function sourceMatchingCount(
  source: PaperSourceSummary,
  hasChapterFilter: boolean,
) {
  if (!hasChapterFilter) return 0;
  return source.matching_question_count ?? source.question_count;
}

function ChapterSelectionShell({
  form,
  heading,
  description,
}: {
  form: CoverageForm;
  heading: string;
  description: string;
}) {
  const [open, setOpen] = useState(false);
  const [draftSlugs, setDraftSlugs] = useState<Set<string>>(
    () => new Set(form.selectedSlugs),
  );
  const { chaptersLoading, chaptersError, chapterGroups, chapters } = form;
  const selectedCount = form.selectedSlugs.size;
  const chapterSummary = selectedCount
    ? `${selectedCount} selected`
    : chaptersLoading
      ? 'Loading chapters'
      : chapterGroups.length > 0
        ? 'Any chapter'
        : 'No chapters yet';

  function openDialog() {
    setDraftSlugs(new Set(form.selectedSlugs));
    setOpen(true);
  }

  function approveChapters() {
    reconcileSelection(form.selectedSlugs, draftSlugs, form.toggleChapter);
    setOpen(false);
  }

  return (
    <>
      <SelectionLauncher
        title={heading}
        description={description}
        summary={chapterSummary}
        onOpen={openDialog}
      />
      {open && (
        <SelectionDialog
          title={heading}
          description="Select the chapters that should restrict the paper and swap alternatives. Approve applies the changes; cancel keeps the current scope."
          onCancel={() => setOpen(false)}
          onApprove={approveChapters}
        >
          <div className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-6 text-muted-foreground">
                {draftSlugs.size > 0
                  ? `${draftSlugs.size} chapter${draftSlugs.size === 1 ? '' : 's'} selected as a strict filter.`
                  : 'Select at least one chapter here, or cancel and choose sources instead.'}
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={chaptersLoading || Boolean(chaptersError)}
                  onClick={() =>
                    setDraftSlugs(
                      new Set(chapters.map((chapter) => chapter.slug)),
                    )
                  }
                >
                  Select all chapters
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={
                    chaptersLoading ||
                    Boolean(chaptersError) ||
                    draftSlugs.size === 0
                  }
                  onClick={() => setDraftSlugs(new Set())}
                >
                  Clear
                </Button>
              </div>
            </div>

            {chaptersLoading ? (
              <p className="rounded-lg border bg-background p-3 text-sm text-muted-foreground">
                Loading chapters…
              </p>
            ) : chaptersError ? (
              <p
                className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
                role="alert"
              >
                Could not load chapters: {chaptersError}
              </p>
            ) : chapterGroups.length === 0 ? (
              <p className="rounded-lg border bg-background p-3 text-sm text-muted-foreground">
                No chapters found.
              </p>
            ) : (
              <ChapterGroups
                form={form}
                selectedSlugs={draftSlugs}
                onToggleChapter={(slug) =>
                  setDraftSlugs((current) => toggleSetValue(current, slug))
                }
                onToggleGroup={(subjectArea) => {
                  const groupSlugs =
                    chapterGroups
                      .find((group) => group.subjectArea === subjectArea)
                      ?.chapters.map((chapter) => chapter.slug) || [];
                  setDraftSlugs((current) =>
                    toggleSetValues(current, groupSlugs),
                  );
                }}
              />
            )}
          </div>
        </SelectionDialog>
      )}
    </>
  );
}

function ChapterGroups({
  form,
  selectedSlugs,
  onToggleChapter,
  onToggleGroup,
}: {
  form: CoverageForm;
  selectedSlugs: Set<string>;
  onToggleChapter: (slug: string) => void;
  onToggleGroup: (subjectArea: string) => void;
}) {
  return (
    <div className="space-y-3">
      {form.chapterGroups.map((group) => (
        <ChapterGroupFieldset
          key={group.subjectArea}
          group={group}
          selectedSlugs={selectedSlugs}
          onToggleChapter={onToggleChapter}
          onToggleGroup={onToggleGroup}
        />
      ))}
    </div>
  );
}

function ChapterGroupFieldset({
  group,
  selectedSlugs,
  onToggleChapter,
  onToggleGroup,
}: {
  group: ChapterGroup;
  selectedSlugs: Set<string>;
  onToggleChapter: (slug: string) => void;
  onToggleGroup: (subjectArea: string) => void;
}) {
  const selectedCount = group.chapters.filter((chapter) =>
    selectedSlugs.has(chapter.slug),
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
          onClick={() => onToggleGroup(group.subjectArea)}
        >
          {groupSelected ? 'Clear group' : 'Select group'}
        </Button>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2">
        {group.chapters.map((chapter) => (
          <li key={chapter.slug}>
            <ChapterChoice
              chapter={chapter}
              selected={selectedSlugs.has(chapter.slug)}
              onToggle={() => onToggleChapter(chapter.slug)}
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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[0.8125rem] font-semibold">Paper structure</p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            The selected paper format controls section and marks distribution.
          </p>
        </div>
        <dl className="grid min-w-0 flex-1 grid-cols-2 gap-2 text-sm lg:grid-cols-4">
          <SummaryItem
            label="Total marks"
            value={structureSummary.totalMarks}
          />
          <SummaryItem label="Sections" value={structureSummary.sectionCount} />
          <SummaryItem
            label="Questions"
            value={`≈ ${structureSummary.approximateQuestionCount}`}
          />
          <SummaryItem
            label="Chapters"
            value={selectedSlugs.size || 'None yet'}
          />
        </dl>
      </div>
      <details className="group mt-3 border-t pt-3">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 rounded-sm text-xs font-medium text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          Marks by question type
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
                <span>{QUESTION_TYPE_LABELS[type] ?? type}</span>
                <span className="font-medium">{marks}</span>
              </li>
            ),
          )}
        </ul>
      </details>
    </aside>
  );
}

function getFocusableElements(root: HTMLElement | null): HTMLElement[] {
  if (!root) return [];
  return Array.from(
    root.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => !element.hasAttribute('aria-hidden'));
}

function toggleSetValue(current: Set<string>, value: string): Set<string> {
  const next = new Set(current);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

function toggleSetValues(current: Set<string>, values: string[]): Set<string> {
  const next = new Set(current);
  const allSelected = values.every((value) => next.has(value));
  for (const value of values) {
    if (allSelected) next.delete(value);
    else next.add(value);
  }
  return next;
}

function reconcileSelection(
  current: Set<string>,
  next: Set<string>,
  toggle: (value: string) => void,
) {
  for (const value of current) {
    if (!next.has(value)) toggle(value);
  }
  for (const value of next) {
    if (!current.has(value)) toggle(value);
  }
}

function formatSourceDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'recent';
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
  }).format(date);
}

function SummaryItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0 rounded-md bg-secondary/60 px-2 py-1.5">
      <dt className="truncate text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 truncate font-semibold">{value}</dd>
    </div>
  );
}
