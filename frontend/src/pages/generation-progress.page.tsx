import { useEffect, useState } from 'react';
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

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      if (!batchId) return;
      try {
        const next = await fetchGenerationBatch(batchId);
        if (cancelled) return;
        setBatch(next);
        setError('');
        setLoading(false);
        if (!TERMINAL_STATUSES.has(next.status)) {
          timer = setTimeout(poll, POLL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError((err as Error).message);
        setLoading(false);
        timer = setTimeout(poll, POLL_MS);
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [batchId]);

  function backToPaperSetup() {
    navigate('/');
  }

  return (
    <GenerationProgressWorkspace
      batch={batch}
      loading={loading}
      error={error}
      onRunInBackground={backToPaperSetup}
      onTryAgain={backToPaperSetup}
      onBackToPaperSetup={backToPaperSetup}
    />
  );
}
