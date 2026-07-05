/**
 * PDF dropzone: drag-and-drop or click-to-browse, with a selected-file summary
 * and a clear control. Validation lives in the hook; this surface just reports
 * the chosen file and any rejection reason.
 *
 * @module PdfDropzone
 */
import { useId, useState } from 'react';
import { FileText, UploadCloud, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatFileSize } from '@/lib/ingestion';

interface PdfDropzoneProps {
  file: File | null;
  onSelect: (file: File | null) => void;
  validationError?: string;
  disabled?: boolean;
}

export function PdfDropzone({
  file,
  onSelect,
  validationError,
  disabled = false,
}: PdfDropzoneProps) {
  const [dragging, setDragging] = useState(false);
  const describedById = useId();

  return (
    <div className="space-y-2">
      {file ? (
        <div className="flex items-center gap-3 rounded-lg border border-input bg-background px-4 py-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-secondary text-foreground">
            <FileText className="size-5" aria-hidden="true" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">
              {file.name}
            </span>
            <span className="block text-xs text-muted-foreground">
              {formatFileSize(file.size)} · PDF
            </span>
          </span>
          <button
            type="button"
            onClick={() => onSelect(null)}
            disabled={disabled}
            className="inline-flex size-11 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 sm:size-10"
            aria-label={`Remove ${file.name}`}
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
      ) : (
        <div className="relative">
          {/*
            The real <input type="file"> is laid over the whole dropzone at zero
            opacity, so a click lands directly on the native control — the only
            approach that reliably opens the picker in every browser. Do NOT
            revert to a button/label that calls inputRef.click() or relies on
            label→input activation of a hidden input: Safari and some other
            browsers silently refuse to open the dialog, so nothing happens.
            The input also receives drops natively; `peer` drives the focus ring.
          */}
          <input
            type="file"
            accept="application/pdf,.pdf"
            aria-label="Choose PDF to extract"
            aria-describedby={validationError ? describedById : undefined}
            aria-invalid={Boolean(validationError)}
            disabled={disabled}
            className="peer absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
            onChange={(event) => {
              onSelect(event.target.files?.[0] ?? null);
              // Allow re-selecting the same file after a clear/retry.
              event.target.value = '';
            }}
            onDragEnter={() => {
              if (!disabled) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={() => setDragging(false)}
          />
          <div
            aria-hidden="true"
            className={cn(
              'pointer-events-none flex min-h-40 w-full flex-col items-center justify-center gap-2.5 rounded-lg border border-dashed px-6 py-8 text-center transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-ring',
              disabled && 'opacity-50',
              dragging
                ? 'border-primary bg-secondary'
                : 'border-input bg-background peer-hover:bg-secondary/60',
            )}
          >
            <span className="flex size-11 items-center justify-center rounded-full bg-secondary text-foreground">
              <UploadCloud className="size-5" aria-hidden="true" />
            </span>
            <span className="text-sm font-medium leading-5">
              Drop a PDF here, or{' '}
              <span className="text-primary underline underline-offset-2">
                browse
              </span>
            </span>
            <span className="text-xs leading-5 text-muted-foreground">
              PDF only · up to 25 MB
            </span>
          </div>
        </div>
      )}

      {validationError && (
        <p id={describedById} className="text-sm text-destructive">
          {validationError}
        </p>
      )}
    </div>
  );
}
