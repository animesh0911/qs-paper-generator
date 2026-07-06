/**
 * Owns the PDF upload + extraction lifecycle for the Upload Papers page.
 *
 * Flow: a teacher picks a PDF (validated client-side), then `upload()` POSTs it
 * and receives a queued `IngestionJob` (HTTP 202). The
 * extraction runs out-of-request (cron), so the hook polls the job until it
 * settles `done` / `failed`. Returning to this route restores only active
 * extraction work, so a completed upload does not block the next PDF.
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

export interface ExtractedPaperReviewState {
  job: IngestionJob;
  parsedQuestions: BankQuestion[];
  loadingQuestions: boolean;
  answerJob: AnswerGenerationJob | null;
  generatedAnswers: GeneratedAnswer[];
  loadingAnswers: boolean;
  generatingAnswers: boolean;
  answerGenerationError: string;
}

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
  recentExtractedPapers: ExtractedPaperReviewState[];
  generateAnswers: () => Promise<void>;
  generateAnswersForJob: (jobId: number) => Promise<void>;
  selectFile: (file: File | null) => void;
  upload: () => Promise<void>;
  /** Remove a failed job from the queue strip. */
  dismissJob: (jobId: number) => Promise<void>;
  /** Re-queue a failed job so extraction runs again. */
  retryJob: (jobId: number) => Promise<void>;
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
  const [extractedPaperRecords, setExtractedPaperRecords] = useState<
    Record<
      number,
      Omit<ExtractedPaperReviewState, 'job'> & {
        questionsLoaded: boolean;
        answersLoaded: boolean;
      }
    >
  >({});
  const [generatingAnswerJobIds, setGeneratingAnswerJobIds] = useState<
    Set<number>
  >(new Set());
  const jobId = job?.id;
  const settled = job ? isIngestionTerminal(job.status) : false;
  const polling = job != null && !settled;

  // Restore active extraction when the teacher returns to Upload PDF. Completed
  // jobs have already landed in the bank, so they should not take over the page
  // on refresh; the upload form is the right default once no extraction is live.
  useEffect(() => {
    if (job) return;
    let cancelled = false;
    fetchIngestionJobs()
      .then((jobs) => {
        if (cancelled) return;
        setRecentJobs(jobs);
        const active = jobs.find(
          (candidate) => !isIngestionTerminal(candidate.status),
        );
        if (active) setJob(active);
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
  const recentExtractedJobs = [
    ...(job?.status === 'done' ? [job] : []),
    ...recentJobs.filter((candidate) => candidate.status === 'done'),
  ]
    .filter(
      (candidate, index, all) =>
        all.findIndex((item) => item.id === candidate.id) === index,
    )
    .slice(0, 3);
  const recentExtractedJobIds = recentExtractedJobs
    .map((candidate) => candidate.id)
    .join(',');

  useEffect(() => {
    if (jobId == null || !isDone) return;
    let cancelled = false;
    setParsedQuestions([]);
    setAnswerJob(null);
    setGeneratedAnswers([]);
    setAnswerGenerationError('');
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
    const jobsToLoad = recentExtractedJobs.filter((candidate) => {
      const record = extractedPaperRecords[candidate.id];
      return !record?.questionsLoaded || !record?.answersLoaded;
    });
    if (jobsToLoad.length === 0) return;

    let cancelled = false;
    for (const extractedJob of jobsToLoad) {
      setExtractedPaperRecords((current) => ({
        ...current,
        [extractedJob.id]: {
          parsedQuestions: current[extractedJob.id]?.parsedQuestions ?? [],
          loadingQuestions: !current[extractedJob.id]?.questionsLoaded,
          answerJob: current[extractedJob.id]?.answerJob ?? null,
          generatedAnswers: current[extractedJob.id]?.generatedAnswers ?? [],
          loadingAnswers: !current[extractedJob.id]?.answersLoaded,
          generatingAnswers: generatingAnswerJobIds.has(extractedJob.id),
          answerGenerationError:
            current[extractedJob.id]?.answerGenerationError ?? '',
          questionsLoaded: current[extractedJob.id]?.questionsLoaded ?? false,
          answersLoaded: current[extractedJob.id]?.answersLoaded ?? false,
        },
      }));

      Promise.resolve(fetchIngestionJobQuestions(extractedJob.id))
        .then((questions) => {
          if (cancelled) return;
          setExtractedPaperRecords((current) => ({
            ...current,
            [extractedJob.id]: {
              ...(current[extractedJob.id] ?? {
                answerJob: null,
                generatedAnswers: [],
                loadingAnswers: false,
                generatingAnswers: generatingAnswerJobIds.has(extractedJob.id),
                answerGenerationError: '',
                answersLoaded: false,
              }),
              parsedQuestions: questions ?? [],
              loadingQuestions: false,
              questionsLoaded: true,
            },
          }));
        })
        .catch(() => {
          if (cancelled) return;
          setExtractedPaperRecords((current) => ({
            ...current,
            [extractedJob.id]: {
              ...(current[extractedJob.id] ?? {
                answerJob: null,
                generatedAnswers: [],
                loadingAnswers: false,
                generatingAnswers: generatingAnswerJobIds.has(extractedJob.id),
                answerGenerationError: '',
                answersLoaded: false,
              }),
              parsedQuestions: [],
              loadingQuestions: false,
              questionsLoaded: true,
            },
          }));
        });

      Promise.resolve(fetchIngestionJobAnswers(extractedJob.id))
        .then((answerState) => {
          if (cancelled) return;
          setExtractedPaperRecords((current) => ({
            ...current,
            [extractedJob.id]: {
              ...(current[extractedJob.id] ?? {
                parsedQuestions: [],
                loadingQuestions: false,
                questionsLoaded: false,
              }),
              answerJob: answerState?.job ?? null,
              generatedAnswers: answerState?.answers ?? [],
              loadingAnswers: false,
              generatingAnswers: generatingAnswerJobIds.has(extractedJob.id),
              answerGenerationError: '',
              answersLoaded: true,
            },
          }));
        })
        .catch((err) => {
          if (cancelled) return;
          setExtractedPaperRecords((current) => ({
            ...current,
            [extractedJob.id]: {
              ...(current[extractedJob.id] ?? {
                parsedQuestions: [],
                loadingQuestions: false,
                questionsLoaded: false,
              }),
              answerJob: null,
              generatedAnswers: [],
              loadingAnswers: false,
              generatingAnswers: generatingAnswerJobIds.has(extractedJob.id),
              answerGenerationError: (err as Error).message,
              answersLoaded: true,
            },
          }));
        });
    }

    return () => {
      cancelled = true;
    };
  }, [recentExtractedJobIds]);

  const recentAnswerPollJobIds = Object.entries(extractedPaperRecords)
    .filter(([, record]) => {
      const status = record.answerJob?.status;
      return status === 'pending' || status === 'running';
    })
    .map(([id]) => id)
    .join(',');

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

  useEffect(() => {
    const ids = recentAnswerPollJobIds
      .split(',')
      .filter(Boolean)
      .map((id) => Number(id));
    if (ids.length === 0) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function pollRecentAnswers() {
      await Promise.all(
        ids.map(async (id) => {
          try {
            const next = await fetchIngestionJobAnswers(id);
            if (cancelled) return;
            setExtractedPaperRecords((current) => ({
              ...current,
              [id]: {
                parsedQuestions: current[id]?.parsedQuestions ?? [],
                loadingQuestions: current[id]?.loadingQuestions ?? false,
                questionsLoaded: current[id]?.questionsLoaded ?? false,
                answerJob: next.job,
                generatedAnswers: next.answers,
                loadingAnswers:
                  next.job?.status === 'pending' || next.job?.status === 'running',
                generatingAnswers: generatingAnswerJobIds.has(id),
                answerGenerationError: '',
                answersLoaded: true,
              },
            }));
          } catch (err) {
            if (cancelled) return;
            setExtractedPaperRecords((current) => ({
              ...current,
              [id]: {
                parsedQuestions: current[id]?.parsedQuestions ?? [],
                loadingQuestions: current[id]?.loadingQuestions ?? false,
                questionsLoaded: current[id]?.questionsLoaded ?? false,
                answerJob: current[id]?.answerJob ?? null,
                generatedAnswers: current[id]?.generatedAnswers ?? [],
                loadingAnswers: false,
                generatingAnswers: generatingAnswerJobIds.has(id),
                answerGenerationError: (err as Error).message,
                answersLoaded: current[id]?.answersLoaded ?? false,
              },
            }));
          }
        }),
      );
      if (!cancelled) timer = setTimeout(pollRecentAnswers, pollIntervalMs);
    }

    timer = setTimeout(pollRecentAnswers, pollIntervalMs);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [recentAnswerPollJobIds, pollIntervalMs]);

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

  async function generateAnswersForJob(targetJobId: number) {
    if (generatingAnswerJobIds.has(targetJobId)) return;
    setGeneratingAnswerJobIds((current) => new Set(current).add(targetJobId));
    setExtractedPaperRecords((current) => ({
      ...current,
      [targetJobId]: {
        parsedQuestions: current[targetJobId]?.parsedQuestions ?? [],
        loadingQuestions: current[targetJobId]?.loadingQuestions ?? false,
        answerJob: current[targetJobId]?.answerJob ?? null,
        generatedAnswers: current[targetJobId]?.generatedAnswers ?? [],
        loadingAnswers: true,
        generatingAnswers: true,
        answerGenerationError: '',
        questionsLoaded: current[targetJobId]?.questionsLoaded ?? false,
        answersLoaded: current[targetJobId]?.answersLoaded ?? false,
      },
    }));
    if (targetJobId === jobId) {
      setGeneratingAnswers(true);
      setAnswerGenerationError('');
    }
    try {
      const queued = await generateIngestionJobAnswers(targetJobId);
      setExtractedPaperRecords((current) => ({
        ...current,
        [targetJobId]: {
          parsedQuestions: current[targetJobId]?.parsedQuestions ?? [],
          loadingQuestions: current[targetJobId]?.loadingQuestions ?? false,
          answerJob: queued,
          generatedAnswers: current[targetJobId]?.generatedAnswers ?? [],
          loadingAnswers: true,
          generatingAnswers: true,
          answerGenerationError: '',
          questionsLoaded: current[targetJobId]?.questionsLoaded ?? false,
          answersLoaded: current[targetJobId]?.answersLoaded ?? false,
        },
      }));
      if (targetJobId === jobId) setAnswerJob(queued);
      const answerState = await fetchIngestionJobAnswers(targetJobId);
      setExtractedPaperRecords((current) => ({
        ...current,
        [targetJobId]: {
          parsedQuestions: current[targetJobId]?.parsedQuestions ?? [],
          loadingQuestions: current[targetJobId]?.loadingQuestions ?? false,
          answerJob: answerState.job,
          generatedAnswers: answerState.answers,
          loadingAnswers: false,
          generatingAnswers: false,
          answerGenerationError: '',
          questionsLoaded: current[targetJobId]?.questionsLoaded ?? false,
          answersLoaded: true,
        },
      }));
      if (targetJobId === jobId) {
        setAnswerJob(answerState.job);
        setGeneratedAnswers(answerState.answers);
      }
    } catch (err) {
      const message = (err as Error).message;
      setExtractedPaperRecords((current) => ({
        ...current,
        [targetJobId]: {
          parsedQuestions: current[targetJobId]?.parsedQuestions ?? [],
          loadingQuestions: current[targetJobId]?.loadingQuestions ?? false,
          answerJob: current[targetJobId]?.answerJob ?? null,
          generatedAnswers: current[targetJobId]?.generatedAnswers ?? [],
          loadingAnswers: false,
          generatingAnswers: false,
          answerGenerationError: message,
          questionsLoaded: current[targetJobId]?.questionsLoaded ?? false,
          answersLoaded: current[targetJobId]?.answersLoaded ?? false,
        },
      }));
      if (targetJobId === jobId) setAnswerGenerationError(message);
    } finally {
      setGeneratingAnswerJobIds((current) => {
        const next = new Set(current);
        next.delete(targetJobId);
        return next;
      });
      if (targetJobId === jobId) setGeneratingAnswers(false);
    }
  }

  async function generateAnswers() {
    if (jobId == null) return;
    await generateAnswersForJob(jobId);
  }

  async function upload() {
    if (!file || uploading) return;
    setUploading(true);
    setUploadError('');
    setPollError('');
    try {
      const queued = await uploadIngestionPdf(file);
      setParsedQuestions([]);
      setAnswerJob(null);
      setGeneratedAnswers([]);
      setLoadingQuestions(false);
      setLoadingAnswers(false);
      setGeneratingAnswers(false);
      setAnswerGenerationError('');
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
      // A retry is active extraction again, so promote it into the detail card
      // and clear any completed-job review state from the previous upload.
      setParsedQuestions([]);
      setAnswerJob(null);
      setGeneratedAnswers([]);
      setLoadingQuestions(false);
      setLoadingAnswers(false);
      setGeneratingAnswers(false);
      setAnswerGenerationError('');
      setJob(requeued);
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

  // Everything still in flight except the job already shown in the detail card.
  const queuedJobs = recentJobs.filter(
    (candidate) =>
      candidate.id !== job?.id &&
      // In-flight jobs queue behind the current one; `failed` ones stay listed
      // so a failed extraction doesn't silently vanish (the teacher sees it
      // failed + why). `done` jobs already landed in the bank — no need to nag.
      (!isIngestionTerminal(candidate.status) || candidate.status === 'failed'),
  );
  const recentExtractedPapers: ExtractedPaperReviewState[] = recentExtractedJobs.map(
    (extractedJob) => {
      const record = extractedPaperRecords[extractedJob.id];
      return {
        job: extractedJob,
        parsedQuestions: record?.parsedQuestions ?? [],
        loadingQuestions: record?.loadingQuestions ?? true,
        answerJob: record?.answerJob ?? null,
        generatedAnswers: record?.generatedAnswers ?? [],
        loadingAnswers: record?.loadingAnswers ?? true,
        generatingAnswers: generatingAnswerJobIds.has(extractedJob.id),
        answerGenerationError: record?.answerGenerationError ?? '',
      };
    },
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
    recentExtractedPapers,
    generateAnswers,
    generateAnswersForJob,
    selectFile,
    upload,
    dismissJob,
    retryJob,
  };
}
