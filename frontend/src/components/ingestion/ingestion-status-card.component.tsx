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

interface TopicGroup {
  key: string;
  label: string;
  questions: BankQuestion[];
}

const QTYPE_LABELS: Record<string, string> = {
  mcq: 'MCQ',
  assertion_reason: 'Assertion–reason',
  very_short_answer: 'Very short',
  short_answer: 'Short answer',
  long_answer: 'Long answer',
  case_based: 'Case-based',
};

const COGNITIVE_LABELS: Record<string, string> = {
  R: 'Remember',
  U: 'Understand',
  Ap: 'Apply',
  An: 'Analyse',
};

function questionTopic(question: BankQuestion): string {
  return (
    question.topic_names?.find((topic) => topic.trim()) ||
    question.chapter?.name ||
    'Unmapped topic'
  );
}

function groupByTopic(questions: BankQuestion[]): TopicGroup[] {
  const groups = new Map<string, TopicGroup>();
  for (const question of questions) {
    const label = questionTopic(question);
    const key = label.toLowerCase();
    const group = groups.get(key) ?? { key, label, questions: [] };
    group.questions.push(question);
    groups.set(key, group);
  }
  return Array.from(groups.values()).sort((a, b) =>
    a.label.localeCompare(b.label),
  );
}

function labelForQuestionType(qtype: string): string {
  return QTYPE_LABELS[qtype] || qtype.replace(/_/g, ' ');
}

function labelForCognitiveLevel(level: string): string {
  return COGNITIVE_LABELS[level] || level;
}

function qualityClass(question: BankQuestion): string {
  if (question.parse_quality === 'clean') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-900';
  }
  if (question.parse_quality === 'broken' || question.review_flags?.length) {
    return 'border-amber-200 bg-amber-50 text-amber-950';
  }
  return 'border-slate-200 bg-slate-50 text-slate-700';
}

function ExtractedQuestionsPanel({
  questions,
}: {
  questions: BankQuestion[];
}) {
  const groups = groupByTopic(questions);

  return (
    <section
      className="overflow-hidden rounded-lg border border-input bg-background"
      aria-labelledby="extracted-questions-heading"
    >
      <div className="flex flex-col gap-2 border-b border-input bg-secondary/50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 id="extracted-questions-heading" className="text-sm font-medium">
            Extracted question review
          </h3>
          <p className="text-xs text-muted-foreground">
            Grouped by topic so you can quickly spot weak tags or missing labels.
          </p>
        </div>
        <span className="w-fit rounded-md border border-input bg-background px-2 py-1 text-xs font-medium text-muted-foreground">
          {questions.length} {questions.length === 1 ? 'question' : 'questions'}
        </span>
      </div>

      <div className="max-h-[28rem] overflow-y-auto" tabIndex={0}>
        {groups.map((group) => (
          <div key={group.key} className="border-b border-input last:border-b-0">
            <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-input bg-background/95 px-4 py-2 backdrop-blur">
              <p className="truncate text-xs font-semibold text-foreground">
                {group.label}
              </p>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {group.questions.length}
              </span>
            </div>
            <ol className="divide-y divide-input" aria-label={`${group.label} questions`}>
              {group.questions.map((question, index) => (
                <li key={question.id} className="px-4 py-3">
                  <div className="flex gap-3">
                    <span className="mt-0.5 w-7 shrink-0 text-xs tabular-nums text-muted-foreground">
                      {index + 1}.
                    </span>
                    <div className="min-w-0 flex-1 space-y-2">
                      <p className="text-sm leading-5 text-foreground">
                        {question.text}
                      </p>
                      <div className="flex flex-wrap gap-1.5 text-xs">
                        <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                          Section {question.section}
                        </span>
                        <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                          {question.marks} {question.marks === 1 ? 'mark' : 'marks'}
                        </span>
                        <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                          {labelForQuestionType(question.qtype)}
                        </span>
                        <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                          {labelForCognitiveLevel(question.cognitive_level)}
                        </span>
                        {question.chapter && (
                          <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                            {question.chapter.name}
                          </span>
                        )}
                        <span
                          className={`rounded border px-1.5 py-0.5 ${qualityClass(question)}`}
                        >
                          {question.parse_quality}
                        </span>
                        {question.primary_form !== 'none' && (
                          <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                            {question.primary_form.replace(/_/g, ' ')}
                          </span>
                        )}
                      </div>
                      {question.review_flags?.length > 0 && (
                        <p className="text-xs text-amber-950">
                          Review: {question.review_flags.join(', ')}
                        </p>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>
    </section>
  );
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
              {loadingQuestions ? (
                <p className="rounded-lg border border-input bg-background px-4 py-3 text-sm text-muted-foreground">
                  Loading the extracted question review…
                </p>
              ) : parsedQuestions.length > 0 ? (
                <ExtractedQuestionsPanel questions={parsedQuestions} />
              ) : (
                <p className="rounded-lg border border-input bg-background px-4 py-3 text-sm text-muted-foreground">
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
