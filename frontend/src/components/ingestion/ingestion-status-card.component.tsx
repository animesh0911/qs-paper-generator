/**
 * Status surface for a queued ingestion job. Renders the polling, done, and
 * failed states with color-independent icons and a clear next step. The
 * extraction runs out-of-request, so the teacher is free to leave and the work
 * continues; this card just reports where the job is.
 *
 * @module IngestionStatusCard
 */
import { useEffect, useId, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  LoaderCircle,
  X,
} from 'lucide-react';
import type { BankQuestion, IngestionJob } from '@/types';
import { Button } from '@/components/ui/button';
import { MathContent } from '@/components/math/math-content.component';

interface IngestionStatusCardProps {
  job: IngestionJob;
  pollError?: string;
  parsedQuestions: BankQuestion[];
  loadingQuestions: boolean;
  onUploadAnother: () => void;
  onGeneratePaper: () => void;
}

interface ChapterGroup {
  key: string;
  label: string;
  order: number;
  subjectArea?: string;
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

function chapterGroupFor(question: BankQuestion): ChapterGroup {
  if (!question.chapter) {
    return {
      key: 'unmapped-chapter',
      label: 'Unmapped chapter',
      order: Number.MAX_SAFE_INTEGER,
      questions: [],
    };
  }
  return {
    key: question.chapter.slug,
    label: question.chapter.name,
    order: question.chapter.order,
    subjectArea: question.chapter.subject_area,
    questions: [],
  };
}

function groupByChapter(questions: BankQuestion[]): ChapterGroup[] {
  const groups = new Map<string, ChapterGroup>();
  for (const question of questions) {
    const next = chapterGroupFor(question);
    const group = groups.get(next.key) ?? next;
    group.questions.push(question);
    groups.set(next.key, group);
  }
  return Array.from(groups.values()).sort((a, b) => {
    if (a.order !== b.order) return a.order - b.order;
    return a.label.localeCompare(b.label);
  });
}

function labelForQuestionType(qtype: string): string {
  return QTYPE_LABELS[qtype] || qtype.replace(/_/g, ' ');
}

function firstTopicName(question: BankQuestion): string | undefined {
  return question.topic_names?.find((topic) => topic.trim())?.trim();
}

function QuestionText({ question }: { question: BankQuestion }) {
  const stem = question.content?.stem;
  if (Array.isArray(stem) && stem.length > 0) {
    return <MathContent items={stem} />;
  }
  return <>{question.text}</>;
}

function questionCountLabel(count: number): string {
  return `${count} ${count === 1 ? 'question' : 'questions'}`;
}

function FeedingToBankIndicator() {
  return (
    <div
      className="mt-2 inline-flex w-fit items-center gap-2 rounded-md border border-input bg-background px-2.5 py-1.5 text-xs font-medium leading-4 text-foreground"
      aria-live="polite"
    >
      <span className="flex items-center gap-1" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="size-1.5 rounded-full bg-foreground/60 motion-safe:animate-pulse"
            style={{ animationDelay: `${index * 140}ms` }}
          />
        ))}
      </span>
      Feeding to question bank
    </div>
  );
}

function ExtractedQuestionsPanel({ questions }: { questions: BankQuestion[] }) {
  const groups = groupByChapter(questions);

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
            Grouped by chapter using the backend’s canonical CBSE tags.
          </p>
        </div>
        <span className="w-fit rounded-md border border-input bg-background px-2 py-1 text-xs font-medium text-foreground">
          {questionCountLabel(questions.length)}
        </span>
      </div>

      <div
        className="max-h-[32rem] overflow-y-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:max-h-[34rem]"
        tabIndex={0}
        aria-label="Extracted questions grouped by chapter"
      >
        {groups.map((group) => (
          <div
            key={group.key}
            className="border-b border-input last:border-b-0"
          >
            <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-input bg-background/95 px-4 py-2 backdrop-blur">
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-foreground">
                  {group.label}
                </p>
                {group.subjectArea && (
                  <p className="text-[0.6875rem] leading-4 text-muted-foreground">
                    {group.subjectArea}
                  </p>
                )}
              </div>
              <span
                className="shrink-0 rounded border border-input bg-secondary px-1.5 py-0.5 text-xs tabular-nums text-secondary-foreground"
                aria-label={`${group.questions.length} questions in ${group.label}`}
              >
                {group.questions.length}
              </span>
            </div>
            <ol
              className="divide-y divide-input"
              aria-label={`${group.label} questions`}
            >
              {group.questions.map((question, index) => (
                <li key={question.id} className="px-4 py-3">
                  <div className="flex gap-3">
                    <span className="mt-0.5 w-7 shrink-0 text-xs tabular-nums text-muted-foreground">
                      {index + 1}.
                    </span>
                    <div className="min-w-0 flex-1 space-y-2">
                      <div className="break-words text-sm leading-6 text-foreground">
                        <QuestionText question={question} />
                      </div>
                      <div className="flex flex-wrap gap-1.5 text-xs leading-5">
                        <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                          Section {question.section}
                        </span>
                        <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                          {question.marks}{' '}
                          {question.marks === 1 ? 'mark' : 'marks'}
                        </span>
                        <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                          {labelForQuestionType(question.qtype)}
                        </span>
                        {firstTopicName(question) && (
                          <span className="max-w-full break-words rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                            Topic: {firstTopicName(question)}
                          </span>
                        )}
                        {question.primary_form !== 'none' && (
                          <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-secondary-foreground">
                            {question.primary_form.replace(/_/g, ' ')}
                          </span>
                        )}
                      </div>
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

function ExtractedQuestionsSummary({
  questions,
  onOpen,
}: {
  questions: BankQuestion[];
  onOpen: () => void;
}) {
  const groups = groupByChapter(questions);
  const firstGroups = groups.slice(0, 3);
  const remainingGroups = groups.length - firstGroups.length;

  return (
    <button
      type="button"
      onClick={onOpen}
      className="group w-full rounded-lg border border-input bg-background px-4 py-3 text-left transition-colors hover:bg-secondary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label="Review extracted questions"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-2">
          <p className="text-sm font-medium leading-5 text-foreground">
            Review extracted questions
          </p>
          <div className="flex flex-wrap gap-1.5">
            {firstGroups.map((group) => (
              <span
                key={group.key}
                className="rounded border border-input bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground"
              >
                {group.label} · {group.questions.length}
              </span>
            ))}
            {remainingGroups > 0 && (
              <span className="rounded border border-input bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground">
                +{remainingGroups} more
              </span>
            )}
          </div>
        </div>
        <span className="inline-flex h-10 shrink-0 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium text-foreground group-hover:bg-background">
          Open review
        </span>
      </div>
    </button>
  );
}

function ExtractedQuestionsDialog({
  questions,
  open,
  onClose,
}: {
  questions: BankQuestion[];
  open: boolean;
  onClose: () => void;
}) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeButtonRef.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      const items = Array.from(focusable ?? []).filter(
        (item) => !item.hasAttribute('disabled'),
      );
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/40 px-3 py-6 sm:px-6 sm:py-10"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex max-h-[calc(100vh-3rem)] w-full max-w-5xl flex-col overflow-hidden rounded-lg border border-input bg-background shadow-lg sm:max-h-[calc(100vh-5rem)]"
      >
        <div className="flex items-center justify-between gap-4 border-b border-input px-4 py-3.5 sm:px-5">
          <div className="min-w-0">
            <h2 id={titleId} className="text-base font-semibold leading-6">
              Extracted question review
            </h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="inline-flex size-10 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Close extracted question review"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-5">
          <ExtractedQuestionsPanel questions={questions} />
        </div>
      </div>
    </div>
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
  const [reviewOpen, setReviewOpen] = useState(false);
  const reviewTriggerRef = useRef<HTMLElement | null>(null);

  function openReview() {
    reviewTriggerRef.current = document.activeElement as HTMLElement | null;
    setReviewOpen(true);
  }

  function closeReview() {
    setReviewOpen(false);
    window.setTimeout(() => reviewTriggerRef.current?.focus(), 0);
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 rounded-lg border border-input bg-background px-4 py-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-secondary text-foreground">
          <FileText className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0 self-center">
          <p className="truncate text-sm font-medium leading-5">{fileName}</p>
        </div>
      </div>

      {inProgress && (
        <div className="flex items-start gap-3 rounded-lg border border-input bg-secondary/50 px-4 py-4">
          <LoaderCircle
            className="mt-0.5 size-5 shrink-0 motion-safe:animate-spin text-foreground"
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
            {job.status === 'running' && <FeedingToBankIndicator />}
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
              {job.skipped_count > 0 && (
                <p className="text-sm text-muted-foreground">
                  {job.skipped_count}{' '}
                  {job.skipped_count === 1
                    ? 'question was'
                    : 'questions were'}{' '}
                  skipped as duplicates or unparseable.
                </p>
              )}
            </div>
          </div>

          {job.created_count > 0 && (
            <div className="space-y-2">
              {loadingQuestions ? (
                <p className="rounded-lg border border-input bg-background px-4 py-3 text-sm text-muted-foreground">
                  Loading the extracted question review…
                </p>
              ) : parsedQuestions.length > 0 ? (
                <>
                  <ExtractedQuestionsSummary
                    questions={parsedQuestions}
                    onOpen={openReview}
                  />
                  <ExtractedQuestionsDialog
                    questions={parsedQuestions}
                    open={reviewOpen}
                    onClose={closeReview}
                  />
                </>
              ) : (
                <p className="rounded-lg border border-input bg-background px-4 py-3 text-sm text-muted-foreground">
                  The questions are in your bank.
                </p>
              )}
            </div>
          )}

          <div className="grid gap-2 sm:flex sm:flex-wrap">
            <Button size="lg" onClick={onGeneratePaper}>
              Generate a paper
            </Button>
            <Button size="lg" variant="outline" onClick={onUploadAnother}>
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
          <Button
            size="lg"
            variant="outline"
            className="w-full sm:w-auto"
            onClick={onUploadAnother}
          >
            Try another upload
          </Button>
        </div>
      )}
    </div>
  );
}
