import { useNavigate, useParams } from 'react-router-dom';
import { GenerationProgressWorkspace } from '@/components/question-generation';
import { useGenerationProgress } from '@/hooks/useGenerationProgress.hook';

const POLL_MS = 3000;

export default function GenerationProgressPage() {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const progress = useGenerationProgress(batchId, POLL_MS);

  function backToPaperSetup() {
    navigate('/');
  }

  return (
    <GenerationProgressWorkspace
      batch={progress.batch}
      loading={progress.loading}
      error={progress.error}
      lastCheckedAt={progress.lastCheckedAt}
      pollIntervalMs={POLL_MS}
      candidates={progress.candidates}
      candidatesLoading={progress.candidatesLoading}
      candidatesError={progress.candidatesError}
      accepting={progress.accepting}
      acceptError={progress.acceptError}
      onRunInBackground={backToPaperSetup}
      onTryAgain={progress.tryAgain}
      onAcceptCandidates={progress.acceptCandidates}
      onRetryCandidates={progress.retryCandidates}
      onBackToPaperSetup={backToPaperSetup}
    />
  );
}
