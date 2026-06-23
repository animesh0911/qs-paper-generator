/**
 * Renders the Slice 3 coverage form: difficulty buttons, chapter checklist
 * with per-chapter weight inputs, and the Generate button.
 *
 * Owns no state — the parent owns `useCoverageForm` and threads its API
 * through `props.form`. The `trailing` slot lets the parent add a
 * Download-PDF button next to Generate without bleeding paper concerns
 * into this view.
 *
 * @module CoverageFormView
 */
import type { ReactNode } from 'react';
import { Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
    chapters,
    formats,
    selectedFormatId,
    selectedSlugs,
    weights,
    difficulty,
    toggleChapter,
    setWeight,
    setDifficulty,
    setSelectedFormatId,
  } = form;

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <label
          htmlFor="paper-format"
          className="block text-[0.8125rem] font-medium leading-5"
        >
          Format
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
      </div>

      <fieldset className="space-y-2">
        <legend className="text-[0.8125rem] font-medium leading-5">
          Difficulty
        </legend>
        <div
          className="inline-flex flex-wrap gap-1 rounded-lg border border-white/70 bg-white/55 p-1"
          role="group"
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
              aria-pressed={difficulty === d}
              onClick={() => setDifficulty(d)}
            >
              {d}
            </button>
          ))}
        </div>
      </fieldset>

      <section className="space-y-3" aria-labelledby="paper-chapters-heading">
        <p
          id="paper-chapters-heading"
          className="text-[0.8125rem] font-medium leading-5"
        >
          Chapters{' '}
          <span className="text-muted-foreground font-normal">
            (leave empty to use all)
          </span>
        </p>
        <ul className="grid gap-2 sm:grid-cols-2">
          {chapters.map((ch) => {
            const selected = selectedSlugs.has(ch.slug);
            const chapterInputId = `paper-chapter-${ch.slug}`;
            return (
              <li key={ch.slug}>
                <div
                  className={
                    selected
                      ? 'h-full rounded-lg border border-primary bg-white/80 px-3 py-3 text-sm leading-5 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring'
                      : 'h-full rounded-lg border border-white/70 bg-white/55 px-3 py-3 text-sm leading-5 transition-colors hover:bg-white/85 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring'
                  }
                >
                  <label
                    htmlFor={chapterInputId}
                    className="flex cursor-pointer items-start gap-3"
                  >
                    <input
                      id={chapterInputId}
                      type="checkbox"
                      className="sr-only"
                      checked={selected}
                      onChange={() => toggleChapter(ch.slug)}
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
                      {ch.order}. {ch.name}
                    </span>
                  </label>
                  {selected && (
                    <div className="mt-3 pl-8">
                      <label
                        htmlFor={`${chapterInputId}-weight`}
                        className="mb-1 block text-xs font-medium text-muted-foreground"
                      >
                        Weight
                      </label>
                      <Input
                        id={`${chapterInputId}-weight`}
                        type="number"
                        min={0}
                        step="0.1"
                        placeholder="weight"
                        className="h-9 w-28 bg-white/80"
                        value={weights[ch.slug] ?? ''}
                        onChange={(e) => setWeight(ch.slug, e.target.value)}
                      />
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <div className="flex flex-col gap-2 border-t border-white/70 pt-4 sm:flex-row sm:items-center">
        <Button onClick={onGenerate} disabled={busy || !selectedFormatId}>
          {busy ? 'Generating…' : 'Generate paper'}
        </Button>
        {trailing}
      </div>
    </div>
  );
}
