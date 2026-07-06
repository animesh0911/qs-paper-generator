import { useEffect, useRef, useState } from 'react';
import type { GeneratedQuestionCandidate, GenerationBatch } from '@/types';
import {
  acceptGenerationCandidates,
  discardGenerationBatch,
  fetchGenerationBatch,
  fetchGenerationCandidates,
} from '@/lib/api';

const TERMINAL_STATUSES = new Set([
  'ready_for_review',
  'accepted',
  'failed',
  'expired',
  'discarded',
]);

const CANDIDATE_REVIEW_STATUSES = new Set(['ready_for_review', 'accepted']);

export interface GenerationProgressState {
  batch: GenerationBatch | null;
  loading: boolean;
  error: string;
  lastCheckedAt: string;
  candidates: GeneratedQuestionCandidate[];
  candidatesLoading: boolean;
  candidatesError: string;
  accepting: boolean;
  acceptError: string;
  discarding: boolean;
  discardError: string;
  tryAgain: () => void;
  retryCandidates: () => void;
  acceptCandidates: (acceptedCandidateIds: number[]) => Promise<void>;
  generateAnother: () => Promise<GenerationBatch | null>;
}

export function useGenerationProgress(
  batchId: string | undefined,
  pollIntervalMs: number,
): GenerationProgressState {
  const [batch, setBatch] = useState<GenerationBatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastCheckedAt, setLastCheckedAt] = useState('');
  const [retryTick, setRetryTick] = useState(0);
  const [candidates, setCandidates] = useState<GeneratedQuestionCandidate[]>(
    [],
  );
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [candidatesError, setCandidatesError] = useState('');
  const [candidatesRetryTick, setCandidatesRetryTick] = useState(0);
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState('');
  const [discarding, setDiscarding] = useState(false);
  const [discardError, setDiscardError] = useState('');
  const hasLoadedBatch = useRef(false);
  const previousBatchId = useRef<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      if (!batchId) return;
      try {
        const next = await fetchGenerationBatch(batchId);
        if (cancelled) return;
        setBatch(next);
        hasLoadedBatch.current = true;
        setError('');
        setLastCheckedAt(new Date().toISOString());
        setLoading(false);
        if (!TERMINAL_STATUSES.has(next.status)) {
          timer = setTimeout(poll, pollIntervalMs);
        }
      } catch (err) {
        if (cancelled) return;
        setError((err as Error).message);
        setLastCheckedAt(new Date().toISOString());
        setLoading(false);
        if (hasLoadedBatch.current) {
          timer = setTimeout(poll, pollIntervalMs);
        }
      }
    }

    if (previousBatchId.current !== batchId) {
      previousBatchId.current = batchId;
      hasLoadedBatch.current = false;
      setBatch(null);
      setCandidates([]);
      setCandidatesError('');
      setCandidatesLoading(false);
    }

    setLoading(true);
    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [batchId, pollIntervalMs, retryTick]);

  useEffect(() => {
    const batchStatus = batch?.status;
    if (
      !batchId ||
      !batchStatus ||
      String(batch?.id) !== batchId ||
      !CANDIDATE_REVIEW_STATUSES.has(batchStatus)
    ) {
      setCandidates([]);
      setCandidatesError('');
      setCandidatesLoading(false);
      return;
    }

    let cancelled = false;
    setCandidatesLoading(true);
    setCandidatesError('');
    fetchGenerationCandidates(batchId)
      .then((nextCandidates) => {
        if (cancelled) return;
        setCandidates(nextCandidates);
      })
      .catch((err) => {
        if (cancelled) return;
        setCandidates([]);
        setCandidatesError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setCandidatesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [batchId, batch?.id, batch?.status, candidatesRetryTick]);

  function tryAgain() {
    setError('');
    setRetryTick((current) => current + 1);
  }

  function retryCandidates() {
    setCandidatesError('');
    setCandidatesRetryTick((current) => current + 1);
  }

  async function acceptCandidates(acceptedCandidateIds: number[]) {
    if (!batchId || acceptedCandidateIds.length === 0 || accepting) return;
    setAccepting(true);
    setAcceptError('');
    try {
      const acceptedBatch = await acceptGenerationCandidates(
        batchId,
        acceptedCandidateIds,
      );
      setBatch(acceptedBatch);
    } catch (err) {
      setAcceptError((err as Error).message);
    } finally {
      setAccepting(false);
    }
  }

  async function generateAnother(): Promise<GenerationBatch | null> {
    // A review-ready batch is still "active" and blocks a new one, so discard
    // it first; settled batches (accepted/failed/expired/discarded) already
    // free their queue slot and only need the return to setup.
    if (!batchId || discarding) return batch;
    if (batch?.status !== 'ready_for_review') return batch;
    setDiscarding(true);
    setDiscardError('');
    try {
      return await discardGenerationBatch(batchId);
    } catch (err) {
      setDiscardError((err as Error).message);
      return null;
    } finally {
      setDiscarding(false);
    }
  }

  return {
    batch,
    loading,
    error,
    lastCheckedAt,
    candidates,
    candidatesLoading,
    candidatesError,
    accepting,
    acceptError,
    discarding,
    discardError,
    tryAgain,
    retryCandidates,
    acceptCandidates,
    generateAnother,
  };
}
