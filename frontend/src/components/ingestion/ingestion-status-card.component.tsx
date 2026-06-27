/**
 * Status surface for a queued ingestion job. Renders the polling, done, and
 * failed states with color-independent icons and a clear next step. The
 * extraction runs out-of-request, so the teacher is free to leave and the work
 * continues; this card just reports where the job is.
 *
 * @module IngestionStatusCard
 */
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  LoaderCircle,
} from 'lucide-react';
import type { IngestionJob } from '@/types';
import { Button } from '@/components/ui/button';
import { sourceTypeLabel } from '@/lib/ingestion';

interface IngestionStatusCardProps {
  job: IngestionJob;
  pollError?: string;
  onUploadAnother: () => void;
  onGeneratePaper: () => void;
}

export function IngestionStatusCard({
  job,
  pollError,
  onUploadAnother,
  onGeneratePaper,
}: IngestionStatusCardProps) {
  const fileName = job.source_file_name || 'Uploaded PDF';
  const inProgress = job.status === 'pending' || job.status === 'running';

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 rounded-lg border border-input bg-background px-4 py-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-secondary text-foreground">
          <FileText className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{fileName}</p>
          <p className="text-xs text-muted-foreground">
            {sourceTypeLabel(job.source_type)}
          </p>
        </div>
      </div>

      {inProgress && (
        <div className="flex items-start gap-3 rounded-lg border border-input bg-secondary/50 px-4 py-4">
          <LoaderCircle
            className="mt-0.5 size-5 shrink-0 animate-spin text-foreground"
            aria-hidden="true"
          />
          <div className="space-y-1">
            <p className="text-sm font-medium" aria-live="polite">
              {job.status === 'pending'
                ? 'Queued for extraction…'
                : 'Extracting questions…'}
            </p>
            <p className="text-sm text-muted-foreground">
              This runs in the background — you can leave this page and the
              questions will be added to your bank when it finishes.
            </p>
            {pollError && (
              <p className="text-xs text-muted-foreground">
                Couldn’t refresh status just now — retrying. ({pollError})
              </p>
            )}
          </div>
        </div>
      )}

      {job.status === 'done' && (
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-lg border border-input bg-secondary/50 px-4 py-4">
            <CheckCircle2
              className="mt-0.5 size-5 shrink-0 text-foreground"
              aria-hidden="true"
            />
            <div className="space-y-1">
              <p className="text-sm font-medium" aria-live="polite">
                {job.created_count === 1
                  ? 'Added 1 question to your bank'
                  : `Added ${job.created_count} questions to your bank`}
              </p>
              <p className="text-sm text-muted-foreground">
                {job.skipped_count > 0
                  ? `${job.skipped_count} ${
                      job.skipped_count === 1
                        ? 'question was'
                        : 'questions were'
                    } skipped as duplicates or unparseable. The rest are ready to use in a paper.`
                  : 'They’re ready to use when you generate a paper.'}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={onGeneratePaper}>Generate a paper</Button>
            <Button variant="outline" onClick={onUploadAnother}>
              Upload another
            </Button>
          </div>
        </div>
      )}

      {job.status === 'failed' && (
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-4">
            <AlertTriangle
              className="mt-0.5 size-5 shrink-0 text-destructive"
              aria-hidden="true"
            />
            <div className="space-y-1">
              <p className="text-sm font-medium" aria-live="polite">
                Extraction failed
              </p>
              <p className="text-sm text-muted-foreground">
                {job.error ||
                  'Something went wrong while reading this PDF. Check the file and try uploading it again.'}
              </p>
            </div>
          </div>
          <Button variant="outline" onClick={onUploadAnother}>
            Try another upload
          </Button>
        </div>
      )}
    </div>
  );
}
