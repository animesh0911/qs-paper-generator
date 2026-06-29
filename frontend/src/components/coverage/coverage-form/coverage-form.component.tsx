/**
 * Minimal paper setup surface for opening the editor in a few decisions.
 *
 * Basic mode keeps CBSE Class 10 Science fixed, exposes backend-owned format,
 * total marks, explicit chapter selection, a live structure summary, and a
 * persistent Generate paper action. Advanced settings stay collapsed.
 *
 * @module CoverageFormView
 */
import type { ReactNode } from 'react';
import { Check, ChevronDown, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { type CoverageForm, DIFFICULTIES } from '@/hooks/useCoverageForm.hook';

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
    chaptersLoading,
    chaptersError,
    chapterGroups,
    formats,
    selectedFormatId,
    selectedSlugs,
    difficulty,
    totalMarks,
    structureSummary,
    hasSelectedChapters,
    toggleChapter,
    toggleChapterGroup,
    selectAllChapters,
    clearAllChapters,
    setDifficulty,
    setSelectedFormatId,
  } = form;
  const generationDisabled = busy || !selectedFormatId || !hasSelectedChapters;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/70 bg-white/55 px-4 py-3">
        <div>
          <p className="text-[0.6875rem] font-medium uppercase tracking-wide text-muted-foreground">
            Fixed context
          </p>
          <p className="text-base font-semibold">Class 10 · Science</p>
        </div>
        <a
          href="/ai-qa"
          className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-white/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Sparkles className="size-4" aria-hidden="true" />
          Generate Question bank
        </a>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label
                htmlFor="paper-format"
                className="block text-[0.8125rem] font-medium leading-5"
              >
                PaperFormat
              </label>
              <select
                id="paper-format"
                className="flex h-11 w-full rounded-lg border border-white/70 bg-white/75 px-3 py-2 text-sm text-foreground transition-colors hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
                className="flex h-11 w-full rounded-lg border border-white/70 bg-white/60 px-3 py-2 text-sm text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={totalMarks}
                readOnly
                aria-describedby="paper-total-marks-note"
              />
              <p id="paper-total-marks-note" className="text-xs text-muted-foreground">
                Set by the selected PaperFormat for this slice.
              </p>
            </div>
          </div>

          <section className="space-y-3" aria-labelledby="paper-chapters-heading">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <p
                  id="paper-chapters-heading"
                  className="text-[0.8125rem] font-medium leading-5"
                >
                  Chapters
                </p>
                <p className="text-xs text-muted-foreground">
                  Pick at least one chapter. Use group controls for faster setup.
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="ghost"
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

            {chaptersLoading ? (
              <p className="rounded-lg border border-white/70 bg-white/55 p-3 text-sm text-muted-foreground">
                Loading chapters…
              </p>
            ) : chaptersError ? (
              <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                Could not load chapters: {chaptersError}
              </p>
            ) : chapterGroups.length === 0 ? (
              <p className="rounded-lg border border-white/70 bg-white/55 p-3 text-sm text-muted-foreground">
                No chapters found.
              </p>
            ) : (
              <div className="space-y-3">
                {chapterGroups.map((group) => {
                  const groupSelected = group.chapters.every((chapter) =>
                    selectedSlugs.has(chapter.slug),
                  );
                  return (
                    <fieldset
                      key={group.subjectArea}
                      className="rounded-lg border border-white/70 bg-white/45 p-3"
                    >
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <legend className="text-sm font-semibold">
                          {group.subjectArea}
                        </legend>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleChapterGroup(group.subjectArea)}
                        >
                          {groupSelected ? 'Clear group' : 'Select group'}
                        </Button>
                      </div>
                      <ul className="grid gap-2 sm:grid-cols-2">
                        {group.chapters.map((chapter) => {
                          const selected = selectedSlugs.has(chapter.slug);
                          const chapterInputId = `paper-chapter-${chapter.slug}`;
                          return (
                            <li key={chapter.slug}>
                              <label
                                htmlFor={chapterInputId}
                                className={
                                  selected
                                    ? 'flex h-full cursor-pointer items-start gap-3 rounded-lg border border-primary bg-white/80 px-3 py-3 text-sm leading-5 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring'
                                    : 'flex h-full cursor-pointer items-start gap-3 rounded-lg border border-white/70 bg-white/55 px-3 py-3 text-sm leading-5 transition-colors hover:bg-white/85 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring'
                                }
                              >
                                <input
                                  id={chapterInputId}
                                  type="checkbox"
                                  className="sr-only"
                                  checked={selected}
                                  onChange={() => toggleChapter(chapter.slug)}
                                />
                                <span
                                  className={
                                    selected
                                      ? 'mt-0.5 flex size-5 items-center justify-center rounded-md bg-primary text-primary-foreground'
                                      : 'mt-0.5 flex size-5 items-center justify-center rounded-md border bg-white text-transparent'
                                  }
                                  aria-hidden="true"
                                >
                                  <Check className="size-3.5" />
                                </span>
                                <span className="block min-w-0 flex-1 font-medium">
                                  {chapter.order}. {chapter.name}
                                </span>
                              </label>
                            </li>
                          );
                        })}
                      </ul>
                    </fieldset>
                  );
                })}
              </div>
            )}
            {!hasSelectedChapters && !chaptersLoading && (
              <p className="text-sm text-destructive">
                Select at least one Chapter to generate a paper.
              </p>
            )}
          </section>

          <details className="rounded-lg border border-white/70 bg-white/45 p-3">
            <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium">
              Advanced settings
              <ChevronDown className="size-4" aria-hidden="true" />
            </summary>
            <fieldset className="mt-3 space-y-2">
              <legend className="text-[0.8125rem] font-medium leading-5">
                Difficulty
              </legend>
              <div
                className="inline-flex flex-wrap gap-1 rounded-lg border border-white/70 bg-white/55 p-1"
                role="radiogroup"
                aria-label="Paper difficulty"
              >
                {DIFFICULTIES.map((d) => (
                  <button
                    key={d}
                    type="button"
                    className={
                      difficulty === d
                        ? 'rounded-md bg-primary px-3 py-1.5 text-[0.8125rem] font-medium leading-5 text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
                        : 'rounded-md px-3 py-1.5 text-[0.8125rem] font-medium leading-5 text-muted-foreground transition-colors hover:bg-white/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
                    }
                    role="radio"
                    aria-checked={difficulty === d}
                    onClick={() => setDifficulty(d)}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </fieldset>
          </details>
        </div>

        <aside className="h-fit rounded-lg border border-white/70 bg-white/65 p-4">
          <p className="text-[0.8125rem] font-semibold">Paper structure</p>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <SummaryItem label="Total marks" value={structureSummary.totalMarks} />
            <SummaryItem label="Sections" value={structureSummary.sectionCount} />
            <SummaryItem
              label="Questions"
              value={`≈ ${structureSummary.approximateQuestionCount}`}
            />
            <SummaryItem label="Chapters" value={selectedSlugs.size} />
          </dl>
          <div className="mt-4 border-t border-white/70 pt-3">
            <p className="text-xs font-medium text-muted-foreground">
              Marks by QuestionType
            </p>
            <ul className="mt-2 space-y-1.5 text-sm">
              {Object.entries(structureSummary.marksByQuestionType).map(
                ([type, marks]) => (
                  <li key={type} className="flex justify-between gap-3">
                    <span>{type}</span>
                    <span className="font-medium">{marks}</span>
                  </li>
                ),
              )}
            </ul>
          </div>
        </aside>
      </div>

      <div className="sticky bottom-0 z-10 -mx-5 flex flex-col gap-2 border-t border-white/70 bg-white/90 px-5 py-3 backdrop-blur sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p className="text-xs text-muted-foreground">
          {hasSelectedChapters
            ? `${selectedSlugs.size} chapter${selectedSlugs.size === 1 ? '' : 's'} selected`
            : 'Chapter selection required'}
        </p>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Button onClick={onGenerate} disabled={generationDisabled}>
            {busy ? 'Generating…' : 'Generate paper'}
          </Button>
          {trailing}
        </div>
      </div>
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-md bg-secondary/70 p-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-semibold">{value}</dd>
    </div>
  );
}
