import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { GeneratedQuestionCandidate, GenerationBatch } from '@/types';
import {
  acceptGenerationCandidates,
  fetchGenerationBatch,
  fetchGenerationCandidates,
} from '@/lib/api';
import { GenerationProgressWorkspace } from '@/components/question-generation';

const POLL_MS = 3000;
const TERMINAL_STATUSES = new Set(['ready_for_review', 'accepted', 'failed', 'expired']);

export default function GenerationProgressPage() {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const [batch, setBatch] = useState<GenerationBatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastCheckedAt, setLastCheckedAt] = useState('');
  const [retryTick, setRetryTick] = useState(0);
  const [candidates, setCandidates] = useState<GeneratedQuestionCandidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [candidatesError, setCandidatesError] = useState('');
  const [candidatesRetryTick, setCandidatesRetryTick] = useState(0);
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState('');
  const hasLoadedBatch = useRef(false);

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
          timer = setTimeout(poll, POLL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError((err as Error).message);
        setLastCheckedAt(new Date().toISOString());
        setLoading(false);
        if (hasLoadedBatch.current) {
          timer = setTimeout(poll, POLL_MS);
        }
      }
    }

    setLoading(true);
    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [batchId, retryTick]);

  useEffect(() => {
    if (!batchId || batch?.status !== 'ready_for_review') {
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
  }, [batchId, batch?.status, candidatesRetryTick]);

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
      setCandidates([]);
    } catch (err) {
      setAcceptError((err as Error).message);
    } finally {
      setAccepting(false);
    }
  }

  function backToPaperSetup() {
    navigate('/');
  }

  return (
    <GenerationProgressWorkspace
      batch={batch}
      loading={loading}
      error={error}
      lastCheckedAt={lastCheckedAt}
      pollIntervalMs={POLL_MS}
      candidates={candidates}
      candidatesLoading={candidatesLoading}
      candidatesError={candidatesError}
      accepting={accepting}
      acceptError={acceptError}
      onRunInBackground={backToPaperSetup}
      onTryAgain={tryAgain}
      onAcceptCandidates={acceptCandidates}
      onRetryCandidates={retryCandidates}
      onBackToPaperSetup={backToPaperSetup}
    />
  );
}
