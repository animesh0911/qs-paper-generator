/**
 * Source-type picker for an upload: a small segmented radio group tagging the
 * provenance stored on every extracted question. Restrained, keyboard-operable,
 * never color-only (the selected option carries a primary border + check).
 *
 * @module SourceTypeField
 */
import { Check } from 'lucide-react';
import type { SourceType } from '@/types';
import { cn } from '@/lib/utils';
import { SOURCE_TYPE_OPTIONS } from '@/lib/ingestion';

interface SourceTypeFieldProps {
  value: SourceType;
  onChange: (value: SourceType) => void;
  disabled?: boolean;
}

export function SourceTypeField({
  value,
  onChange,
  disabled = false,
}: SourceTypeFieldProps) {
  const activeHint = SOURCE_TYPE_OPTIONS.find(
    (option) => option.value === value,
  )?.hint;

  return (
    <fieldset disabled={disabled} className="space-y-2">
      <legend className="text-sm font-medium">Source type</legend>
      <div
        role="radiogroup"
        aria-label="Source type"
        className="grid gap-2 sm:grid-cols-3"
      >
        {SOURCE_TYPE_OPTIONS.map((option) => {
          const selected = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(option.value)}
              className={cn(
                'flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
                selected
                  ? 'border-primary bg-secondary text-foreground'
                  : 'border-input bg-background text-muted-foreground hover:bg-secondary/70 hover:text-foreground',
              )}
            >
              <span>{option.label}</span>
              {selected && (
                <Check
                  className="size-4 shrink-0 text-primary"
                  aria-hidden="true"
                />
              )}
            </button>
          );
        })}
      </div>
      {activeHint && (
        <p className="text-xs text-muted-foreground">{activeHint}</p>
      )}
    </fieldset>
  );
}
