import { useNavigate, useParams } from 'react-router-dom';
import { GenerationProgressWorkspace } from '@/components/question-generation';
import { useGenerationProgress } from '@/hooks/useGenerationProgress.hook';
import { difficultyLabelFromPreset } from '@/lib/question-generation';

const POLL_MS = 3000;

export default function GenerationProgressPage() {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const progress = useGenerationProgress(batchId, POLL_MS);

  function backToPaperSetup() {
    navigate('/ai-qa');
  }

  async function generateAnother() {
    const settled = await progress.generateAnother();
    if (settled === null) return; // discard failed; stay so the error shows
    const batch = progress.batch;
    // Pre-fill setup with this batch's selections so the teacher can tweak and
    // regenerate without re-picking the chapter/topics/difficulty.
    navigate('/ai-qa', {
      state: batch
        ? {
            generationPrefill: {
              chapterSlug: batch.chapter_slugs[0] ?? '',
              topicIds: batch.chapter_map_node_ids,
              difficulty: difficultyLabelFromPreset(batch.difficulty_preset),
            },
          }
        : undefined,
    });
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
      discarding={progress.discarding}
      discardError={progress.discardError}
      onRunInBackground={backToPaperSetup}
      onTryAgain={progress.tryAgain}
      onAcceptCandidates={progress.acceptCandidates}
      onRetryCandidates={progress.retryCandidates}
      onBackToPaperSetup={backToPaperSetup}
      onGenerateAnother={generateAnother}
    />
  );
}
