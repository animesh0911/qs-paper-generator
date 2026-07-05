/**
 * Owns the PDF upload + extraction lifecycle for the Upload Papers page.
 *
 * Flow: a teacher picks a PDF (validated client-side), then `upload()` POSTs it
 * and receives a queued `IngestionJob` (HTTP 202). The
 * extraction runs out-of-request (cron), so the hook polls the job until it
 * settles `done` / `failed`. `reset()` returns to the idle picker so the
 * teacher can upload another.
 *
 * @module useIngestionUpload.hook
 */
import { useEffect, useRef, useState } from 'react';
import type {
  AnswerGenerationJob,
  BankQuestion,
  GeneratedAnswer,
  IngestionJob,
} from '@/types';
import {
  dismissIngestionJob,
  fetchIngestionJob,
  fetchIngestionJobAnswers,
  fetchIngestionJobQuestions,
  fetchIngestionJobs,
  generateIngestionJobAnswers,
  retryIngestionJob,
  uploadIngestionPdf,
} from '@/lib/api';
import { isIngestionTerminal, validatePdfFile } from '@/lib/ingestion';

export interface IngestionUploadState {
  file: File | null;
  validationError: string;
  uploading: boolean;
  uploadError: string;
  job: IngestionJob | null;
  /**
   * Other uploads worth surfacing beside the detail card: in-flight
   * (pending/running) jobs queued behind the current one, plus `failed` ones so
   * a failed extraction doesn't silently disappear. Excludes the card's own job
   * and successful `done` jobs (those already landed in the bank).
   */
  queuedJobs: IngestionJob[];
  /** True while a non-terminal job is being polled. */
  polling: boolean;
  pollError: string;
  /** Questions a finished job added to the bank (empty until it's `done`). */
  parsedQuestions: BankQuestion[];
  /** True while the parsed-questions list is loading after the job settles. */
  loadingQuestions: boolean;
  answerJob: AnswerGenerationJob | null;
  generatedAnswers: GeneratedAnswer[];
  loadingAnswers: boolean;
  generatingAnswers: boolean;
  answerGenerationError: string;
  generateAnswers: () => Promise<void>;
  selectFile: (file: File | null) => void;
  upload: () => Promise<void>;
  /** Remove a failed job from the queue strip. */
  dismissJob: (jobId: number) => Promise<void>;
  /** Re-queue a failed job so extraction runs again. */
  retryJob: (jobId: number) => Promise<void>;
  reset: () => void;
}

export function useIngestionUpload(
  pollIntervalMs = 3000,
): IngestionUploadState {
  const [file, setFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [recentJobs, setRecentJobs] = useState<IngestionJob[]>([]);
  const [pollError, setPollError] = useState('');
  const [parsedQuestions, setParsedQuestions] = useState<BankQuestion[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [answerJob, setAnswerJob] = useState<AnswerGenerationJob | null>(null);
  const [generatedAnswers, setGeneratedAnswers] = useState<GeneratedAnswer[]>(
    [],
  );
  const [loadingAnswers, setLoadingAnswers] = useState(false);
  const [generatingAnswers, setGeneratingAnswers] = useState(false);
  const [answerGenerationError, setAnswerGenerationError] = useState('');
  const jobId = job?.id;
  const settled = job ? isIngestionTerminal(job.status) : false;
  const polling = job != null && !settled;

  // Restore the latest upload when the teacher returns to this page, including
  // completed jobs. The header activity pill links back here after extraction;
  // if we discard `done` jobs on mount, the teacher loses the extracted-question
  // review and answer-generation actions. `reset()` suppresses this restore for
  // the explicit "Upload another" escape hatch.
  const suppressRestoreRef = useRef(false);
  useEffect(() => {
    if (job || suppressRestoreRef.current) return;
    let cancelled = false;
    fetchIngestionJobs()
      .then((jobs) => {
        if (cancelled) return;
        setRecentJobs(jobs);
        const latest = jobs[0];
        if (latest) setJob(latest);
      })
      .catch(() => {
        // Non-fatal: the empty upload form still works if the recent-job list
        // cannot be loaded.
      });
    return () => {
      cancelled = true;
    };
  }, [job]);

  // Poll the queued job until it settles. Keyed on the job id so a fresh upload
  // restarts the loop; the loop reschedules itself off each fetched status.
  const initialStatusRef = useRef(job?.status);
  initialStatusRef.current = job?.status;
  useEffect(() => {
    if (jobId == null) return;
    if (
      initialStatusRef.current &&
      isIngestionTerminal(initialStatusRef.current)
    )
      return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const next = await fetchIngestionJob(jobId as number);
        if (cancelled) return;
        setJob(next);
        setPollError('');
        if (!isIngestionTerminal(next.status)) {
          timer = setTimeout(poll, pollIntervalMs);
        }
      } catch (err) {
        if (cancelled) return;
        setPollError((err as Error).message);
        timer = setTimeout(poll, pollIntervalMs);
      }
    }

    timer = setTimeout(poll, pollIntervalMs);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, pollIntervalMs]);

  // Keep the recent-jobs list fresh while anything is still in flight, so the
  // queue strip reflects every pending/running upload — not just the one in the
  // detail card. Independent of the single-job poll above: that drives the card;
  // this drives the "also in queue" list. Stops once nothing is in flight.
  const hasInflightInList = recentJobs.some(
    (candidate) => !isIngestionTerminal(candidate.status),
  );
  useEffect(() => {
    if (!hasInflightInList) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const jobs = await fetchIngestionJobs();
        if (cancelled) return;
        setRecentJobs(jobs);
        if (jobs.some((candidate) => !isIngestionTerminal(candidate.status))) {
          timer = setTimeout(poll, pollIntervalMs);
        }
      } catch {
        // Non-fatal: the strip keeps its last-known statuses and retries.
        if (!cancelled) timer = setTimeout(poll, pollIntervalMs);
      }
    }

    timer = setTimeout(poll, pollIntervalMs);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [hasInflightInList, pollIntervalMs]);

  // Once a job lands `done`, fetch the questions it added so the status card
  // can show exactly what was parsed (after extraction + validation finished).
  const isDone = job?.status === 'done';
  const answerJobStatus = answerJob?.status;
  useEffect(() => {
    if (jobId == null || !isDone) return;
    let cancelled = false;
    setLoadingQuestions(true);
    setLoadingAnswers(true);

    fetchIngestionJobQuestions(jobId)
      .then((questions) => {
        if (!cancelled) setParsedQuestions(questions);
      })
      .catch(() => {
        // Non-fatal: the counts in the status card still tell the story.
        if (!cancelled) setParsedQuestions([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingQuestions(false);
      });

    fetchIngestionJobAnswers(jobId)
      .then((answerState) => {
        if (cancelled) return;
        setAnswerJob(answerState.job);
        setGeneratedAnswers(answerState.answers);
        setAnswerGenerationError('');
      })
      .catch((err) => {
        // Answers are optional; a failure here must not hide the extracted list
        // or the "Generate answers" action.
        if (!cancelled) {
          setGeneratedAnswers([]);
          setAnswerGenerationError((err as Error).message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingAnswers(false);
      });

    return () => {
      cancelled = true;
    };
  }, [jobId, isDone]);

  useEffect(() => {
    if (jobId == null || !answerJobStatus) return;
    if (answerJobStatus !== 'pending' && answerJobStatus !== 'running') return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function pollAnswers() {
      try {
        const next = await fetchIngestionJobAnswers(jobId as number);
        if (cancelled) return;
        setAnswerJob(next.job);
        setGeneratedAnswers(next.answers);
        setAnswerGenerationError('');
        if (next.job?.status === 'pending' || next.job?.status === 'running') {
          timer = setTimeout(pollAnswers, pollIntervalMs);
        }
      } catch (err) {
        if (cancelled) return;
        setAnswerGenerationError((err as Error).message);
        timer = setTimeout(pollAnswers, pollIntervalMs);
      }
    }

    timer = setTimeout(pollAnswers, pollIntervalMs);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [answerJobStatus, jobId, pollIntervalMs]);

  function selectFile(next: File | null) {
    setUploadError('');
    if (!next) {
      setFile(null);
      setValidationError('');
      return;
    }
    const reason = validatePdfFile(next);
    if (reason) {
      setFile(null);
      setValidationError(reason);
      return;
    }
    setValidationError('');
    setFile(next);
  }

  async function generateAnswers() {
    if (jobId == null || generatingAnswers) return;
    setGeneratingAnswers(true);
    setAnswerGenerationError('');
    try {
      const queued = await generateIngestionJobAnswers(jobId);
      setAnswerJob(queued);
      const answerState = await fetchIngestionJobAnswers(jobId);
      setAnswerJob(answerState.job);
      setGeneratedAnswers(answerState.answers);
    } catch (err) {
      setAnswerGenerationError((err as Error).message);
    } finally {
      setGeneratingAnswers(false);
    }
  }

  async function upload() {
    if (!file || uploading) return;
    setUploading(true);
    setUploadError('');
    setPollError('');
    try {
      const queued = await uploadIngestionPdf(file);
      setJob(queued);
      // Refresh the list so any earlier upload still draining shows in the queue
      // strip (and the list poller restarts on the new in-flight job).
      fetchIngestionJobs()
        .then(setRecentJobs)
        .catch(() => {
          /* strip is best-effort; the detail card still works */
        });
    } catch (err) {
      setUploadError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function dismissJob(targetId: number) {
    // Optimistic: drop it from the strip immediately, then persist. The list
    // poller re-syncs on its next tick regardless.
    setRecentJobs((current) => current.filter((j) => j.id !== targetId));
    try {
      await dismissIngestionJob(targetId);
    } catch {
      // Restore truth on failure so the row doesn't vanish on a no-op.
      fetchIngestionJobs()
        .then(setRecentJobs)
        .catch(() => {});
    }
  }

  async function retryJob(targetId: number) {
    try {
      const requeued = await retryIngestionJob(targetId);
      // Reflect the pending status at once; the list poller restarts on it.
      setRecentJobs((current) =>
        current.map((j) => (j.id === targetId ? requeued : j)),
      );
    } catch {
      fetchIngestionJobs()
        .then(setRecentJobs)
        .catch(() => {});
    }
  }

  function reset() {
    suppressRestoreRef.current = true;
    setFile(null);
    setValidationError('');
    setUploadError('');
    setPollError('');
    setJob(null);
    setParsedQuestions([]);
    setLoadingQuestions(false);
    setAnswerJob(null);
    setGeneratedAnswers([]);
    setLoadingAnswers(false);
    setGeneratingAnswers(false);
    setAnswerGenerationError('');
  }

  // Everything still in flight except the job already shown in the detail card.
  const queuedJobs = recentJobs.filter(
    (candidate) =>
      candidate.id !== job?.id &&
      // In-flight jobs queue behind the current one; `failed` ones stay listed
      // so a failed extraction doesn't silently vanish (the teacher sees it
      // failed + why). `done` jobs already landed in the bank — no need to nag.
      (!isIngestionTerminal(candidate.status) || candidate.status === 'failed'),
  );

  return {
    file,
    validationError,
    uploading,
    uploadError,
    job,
    queuedJobs,
    polling,
    pollError,
    parsedQuestions,
    loadingQuestions,
    answerJob,
    generatedAnswers,
    loadingAnswers,
    generatingAnswers,
    answerGenerationError,
    generateAnswers,
    selectFile,
    upload,
    dismissJob,
    retryJob,
    reset,
  };
}
