/**
 * PDF dropzone: drag-and-drop or click-to-browse, with a selected-file summary
 * and a clear control. Validation lives in the hook; this surface just reports
 * the chosen file and any rejection reason.
 *
 * @module PdfDropzone
 */
import { useId, useRef, useState } from 'react';
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
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const describedById = useId();

  function openPicker() {
    if (disabled) return;
    inputRef.current?.click();
  }

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) onSelect(dropped);
  }

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        aria-label="Choose PDF to extract"
        className="sr-only"
        disabled={disabled}
        onChange={(event) => {
          onSelect(event.target.files?.[0] ?? null);
          // Allow re-selecting the same file after a clear/retry.
          event.target.value = '';
        }}
      />

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
        <button
          type="button"
          onClick={openPicker}
          disabled={disabled}
          aria-describedby={validationError ? describedById : undefined}
          aria-invalid={Boolean(validationError)}
          onDragOver={(event) => {
            event.preventDefault();
            if (!disabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={cn(
            'flex min-h-40 w-full flex-col items-center justify-center gap-2.5 rounded-lg border border-dashed px-6 py-8 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
            dragging
              ? 'border-primary bg-secondary'
              : 'border-input bg-background hover:bg-secondary/60',
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
        </button>
      )}

      {validationError && (
        <p id={describedById} className="text-sm text-destructive">
          {validationError}
        </p>
      )}
    </div>
  );
}
