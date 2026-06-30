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
import type { BankQuestion, IngestionJob } from '@/types';
import { Button } from '@/components/ui/button';
import { sourceTypeLabel } from '@/lib/ingestion';

interface IngestionStatusCardProps {
  job: IngestionJob;
  pollError?: string;
  parsedQuestions: BankQuestion[];
  loadingQuestions: boolean;
  onUploadAnother: () => void;
  onGeneratePaper: () => void;
}

export function IngestionStatusCard({
  job,
  pollError,
  parsedQuestions,
  loadingQuestions,
  onUploadAnother,
  onGeneratePaper,
}: IngestionStatusCardProps) {
  const fileName = job.source_file_name || 'Uploaded PDF';
  const inProgress = job.status === 'pending' || job.status === 'running';
  // Show page progress once the drainer has planned the PDF (total_pages > 0).
  const hasProgress = job.status === 'running' && job.total_pages > 0;
  const progressPct = hasProgress
    ? Math.min(100, Math.round((job.pages_done / job.total_pages) * 100))
    : 0;

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
          <div className="flex-1 space-y-1">
            <p className="text-sm font-medium" aria-live="polite">
              {job.status === 'pending'
                ? 'Queued for extraction…'
                : hasProgress
                  ? `Extracting questions — page ${job.pages_done} of ${job.total_pages}…`
                  : 'Extracting questions…'}
            </p>
            <p className="text-sm text-muted-foreground">
              This runs in the background — you can leave this page and the
              questions will be added to your bank when it finishes.
            </p>
            {hasProgress && (
              <div
                className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-secondary"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={job.total_pages}
                aria-valuenow={job.pages_done}
                aria-label="Extraction progress"
              >
                <div
                  className="h-full rounded-full bg-foreground/70 transition-[width] duration-500"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            )}
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

          {job.created_count > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">
                Questions added to your bank
              </p>
              {loadingQuestions ? (
                <p className="text-sm text-muted-foreground">
                  Loading the parsed questions…
                </p>
              ) : parsedQuestions.length > 0 ? (
                <ul className="divide-y divide-input overflow-hidden rounded-lg border border-input bg-background">
                  {parsedQuestions.map((question, index) => (
                    <li key={question.id} className="flex gap-3 px-4 py-3">
                      <span className="w-6 shrink-0 text-sm tabular-nums text-muted-foreground">
                        {index + 1}.
                      </span>
                      <div className="min-w-0 space-y-1">
                        <p className="text-sm leading-5">{question.text}</p>
                        <p className="flex flex-wrap gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                          <span>Section {question.section}</span>
                          <span aria-hidden="true">·</span>
                          <span>
                            {question.marks}{' '}
                            {question.marks === 1 ? 'mark' : 'marks'}
                          </span>
                          {question.chapter && (
                            <>
                              <span aria-hidden="true">·</span>
                              <span className="truncate">
                                {question.chapter.name}
                              </span>
                            </>
                          )}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">
                  The questions are in your bank, ready to use in a paper.
                </p>
              )}
            </div>
          )}

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
