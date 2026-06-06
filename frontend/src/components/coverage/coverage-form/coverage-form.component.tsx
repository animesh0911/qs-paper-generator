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
    <div className="space-y-4">
      <div>
        <label htmlFor="paper-format" className="text-sm font-medium mb-2 block">
          Format
        </label>
        <select
          id="paper-format"
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
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
              <li key={ch.slug} className="flex items-center gap-3 text-sm">
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
                    onChange={(e) => setWeight(ch.slug, e.target.value)}
                  />
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={onGenerate} disabled={busy || !selectedFormatId}>
          {busy ? 'Generating…' : 'Generate paper'}
        </Button>
        {trailing}
      </div>
    </div>
  );
}
