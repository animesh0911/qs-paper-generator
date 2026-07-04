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
import type { BankQuestion, IngestionJob } from '@/types';
import {
  fetchIngestionJob,
  fetchIngestionJobQuestions,
  fetchIngestionJobs,
  uploadIngestionPdf,
} from '@/lib/api';
import { isIngestionTerminal, validatePdfFile } from '@/lib/ingestion';

export interface IngestionUploadState {
  file: File | null;
  validationError: string;
  uploading: boolean;
  uploadError: string;
  job: IngestionJob | null;
  /** True while a non-terminal job is being polled. */
  polling: boolean;
  pollError: string;
  /** Questions a finished job added to the bank (empty until it's `done`). */
  parsedQuestions: BankQuestion[];
  /** True while the parsed-questions list is loading after the job settles. */
  loadingQuestions: boolean;
  selectFile: (file: File | null) => void;
  upload: () => Promise<void>;
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
  const [pollError, setPollError] = useState('');
  const [parsedQuestions, setParsedQuestions] = useState<BankQuestion[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const jobId = job?.id;
  const settled = job ? isIngestionTerminal(job.status) : false;
  const polling = job != null && !settled;

  // Restore the latest upload when the teacher returns to this page. Ingestion is
  // single-flight, so the latest job is the one whose progress or extracted list
  // the teacher expects to see after navigating away. Do not guard this with a
  // one-shot ref: React StrictMode intentionally replays mount effects in dev,
  // and a premature guard can cancel the only fetch that would hydrate the card.
  const suppressRestoreRef = useRef(false);
  useEffect(() => {
    if (job || suppressRestoreRef.current) return;
    let cancelled = false;
    fetchIngestionJobs()
      .then((jobs) => {
        if (!cancelled && jobs[0]) setJob(jobs[0]);
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

  // Once a job lands `done`, fetch the questions it added so the status card
  // can show exactly what was parsed (after extraction + validation finished).
  const isDone = job?.status === 'done';
  useEffect(() => {
    if (jobId == null || !isDone) return;
    let cancelled = false;
    setLoadingQuestions(true);
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
    return () => {
      cancelled = true;
    };
  }, [jobId, isDone]);

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

  async function upload() {
    if (!file || uploading) return;
    setUploading(true);
    setUploadError('');
    setPollError('');
    try {
      const queued = await uploadIngestionPdf(file);
      setJob(queued);
    } catch (err) {
      setUploadError((err as Error).message);
    } finally {
      setUploading(false);
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
  }

  return {
    file,
    validationError,
    uploading,
    uploadError,
    job,
    polling,
    pollError,
    parsedQuestions,
    loadingQuestions,
    selectFile,
    upload,
    reset,
  };
}
