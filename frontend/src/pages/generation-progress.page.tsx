import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { GenerationBatch } from '@/types';
import { fetchGenerationBatch } from '@/lib/api';
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

  function tryAgain() {
    setError('');
    setRetryTick((current) => current + 1);
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
      onRunInBackground={backToPaperSetup}
      onTryAgain={tryAgain}
      onBackToPaperSetup={backToPaperSetup}
    />
  );
}
