/**
 * Owns the PDF upload + extraction lifecycle for the Upload Papers page.
 *
 * Flow: a teacher picks a PDF (validated client-side) and a source type, then
 * `upload()` POSTs it and receives a queued `IngestionJob` (HTTP 202). The
 * extraction runs out-of-request (cron), so the hook polls the job until it
 * settles `done` / `failed`. `reset()` returns to the idle picker so the
 * teacher can upload another.
 *
 * @module useIngestionUpload.hook
 */
import { useEffect, useRef, useState } from 'react';
import type { BankQuestion, IngestionJob, SourceType } from '@/types';
import {
  fetchIngestionJob,
  fetchIngestionJobQuestions,
  uploadIngestionPdf,
} from '@/lib/api';
import {
  DEFAULT_SOURCE_TYPE,
  isIngestionTerminal,
  validatePdfFile,
} from '@/lib/ingestion';

export interface IngestionUploadState {
  file: File | null;
  sourceType: SourceType;
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
  setSourceType: (sourceType: SourceType) => void;
  upload: () => Promise<void>;
  reset: () => void;
}

export function useIngestionUpload(
  pollIntervalMs = 3000,
): IngestionUploadState {
  const [file, setFile] = useState<File | null>(null);
  const [sourceType, setSourceType] = useState<SourceType>(DEFAULT_SOURCE_TYPE);
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
      const queued = await uploadIngestionPdf(file, sourceType);
      setJob(queued);
    } catch (err) {
      setUploadError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  function reset() {
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
    sourceType,
    validationError,
    uploading,
    uploadError,
    job,
    polling,
    pollError,
    parsedQuestions,
    loadingQuestions,
    selectFile,
    setSourceType,
    upload,
    reset,
  };
}
