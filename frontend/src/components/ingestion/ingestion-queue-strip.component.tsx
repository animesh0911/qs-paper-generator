/**
 * Compact list of uploads sitting beside the one in the detail card: in-flight
 * jobs queued behind it (the drain is serial, one at a time) plus any that
 * failed. Without this a teacher who uploaded several PDFs would only see the
 * newest — and a failed extraction would silently vanish. Failed rows carry
 * Retry (re-queue) and Remove (dismiss) controls.
 *
 * @module IngestionQueueStrip
 */
import { AlertTriangle, LoaderCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { IngestionJob } from '@/types';

interface IngestionQueueStripProps {
  jobs: IngestionJob[];
  onRetry: (jobId: number) => void;
  onDismiss: (jobId: number) => void;
}

function statusLabel(job: IngestionJob): string {
  if (job.status === 'pending') return 'Queued…';
  if (job.status === 'running') {
    return job.total_pages > 0
      ? `Extracting — page ${job.pages_done} of ${job.total_pages}…`
      : 'Extracting…';
  }
  return job.status;
}

export function IngestionQueueStrip({
  jobs,
  onRetry,
  onDismiss,
}: IngestionQueueStripProps) {
  if (jobs.length === 0) return null;

  return (
    <section className="mt-5 space-y-2" aria-label="Other uploads">
      <h2 className="text-xs font-medium leading-4 text-muted-foreground">
        Other uploads
      </h2>
      <ul className="space-y-1.5">
        {jobs.map((job) => {
          const failed = job.status === 'failed';
          return (
            <li
              key={job.id}
              title={failed ? job.error || undefined : undefined}
              className="flex items-center gap-3 rounded-md border border-input bg-background px-3 py-2"
            >
              {failed ? (
                <AlertTriangle
                  className="size-4 shrink-0 text-destructive"
                  aria-hidden="true"
                />
              ) : (
                <LoaderCircle
                  className="size-4 shrink-0 text-muted-foreground motion-safe:animate-spin"
                  aria-hidden="true"
                />
              )}
              <span className="min-w-0 flex-1 truncate text-sm">
                {job.source_file_name || 'Uploaded PDF'}
              </span>
              {failed ? (
                <span className="flex shrink-0 items-center gap-1.5">
                  <span className="text-xs text-destructive">Failed</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 px-2 text-xs"
                    onClick={() => onRetry(job.id)}
                  >
                    Retry
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2 text-xs"
                    onClick={() => onDismiss(job.id)}
                  >
                    Remove
                  </Button>
                </span>
              ) : (
                <span
                  className="shrink-0 truncate text-xs text-muted-foreground"
                  aria-live="polite"
                >
                  {statusLabel(job)}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
