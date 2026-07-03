import type {
  GenerationBatch,
  GenerationBatchCreateRequest,
  GenerationBatchStatus,
  GenerationDifficultyLabel,
} from '@/types';

export const GENERATION_DIFFICULTIES: GenerationDifficultyLabel[] = [
  'Easy',
  'Standard',
  'Challenging',
];

const BACKEND_DIFFICULTY_BY_LABEL: Record<GenerationDifficultyLabel, string> = {
  Easy: 'easy',
  Standard: 'balanced',
  Challenging: 'hard',
};

const LABEL_BY_BACKEND_DIFFICULTY: Record<string, GenerationDifficultyLabel> = {
  easy: 'Easy',
  balanced: 'Standard',
  hard: 'Challenging',
};

export const GENERATION_BATCH_QUESTION_COUNT = 30;

export function difficultyLabelFromPreset(
  preset: string,
): GenerationDifficultyLabel {
  return LABEL_BY_BACKEND_DIFFICULTY[preset] ?? 'Standard';
}

export function buildGenerationBatchPayload({
  chapterSlug,
  chapterMapNodeIds,
  difficulty,
}: {
  chapterSlug: string;
  chapterMapNodeIds: string[];
  difficulty: GenerationDifficultyLabel;
}): GenerationBatchCreateRequest {
  if (!chapterSlug) {
    throw new Error('Select one Chapter.');
  }
  if (chapterMapNodeIds.length === 0) {
    throw new Error('Select at least one NCERT topic.');
  }

  return {
    chapter_slugs: [chapterSlug],
    chapter_map_node_ids: chapterMapNodeIds,
    difficulty_preset: BACKEND_DIFFICULTY_BY_LABEL[difficulty],
    count: GENERATION_BATCH_QUESTION_COUNT,
  };
}

export function generationStageLabel(status: GenerationBatchStatus): string {
  switch (status) {
    case 'queued':
      return 'Queued';
    case 'generating_questions':
      return 'Generating Questions';
    case 'validating':
      return 'Validating';
    case 'ready_for_review':
      return 'Ready for review';
    case 'accepted':
      return 'Accepted';
    case 'expired':
      return 'Expired';
    case 'discarded':
      return 'Discarded';
    case 'failed':
      return 'Failed';
  }
}

export function generationStageDescription(
  status: GenerationBatchStatus,
): string {
  switch (status) {
    case 'queued':
      return 'The request is waiting for the generation worker.';
    case 'generating_questions':
      return 'The worker is drafting candidates from the selected NCERT topic scope.';
    case 'validating':
      return 'Candidates are being checked before they can be reviewed.';
    case 'ready_for_review':
      return 'Candidates are ready, but they are not in the Question bank until review is complete.';
    case 'accepted':
      return 'Reviewed candidates have been accepted into the Question bank.';
    case 'expired':
      return 'This generation job expired before review was completed.';
    case 'discarded':
      return 'You discarded this batch before importing any candidates.';
    case 'failed':
      return 'The job finished without usable candidates.';
  }
}

export function shouldShowNoValidQuestionsMessage(
  batch: Pick<GenerationBatch, 'status' | 'candidate_count'>,
): boolean {
  return (
    batch.status === 'failed' ||
    (batch.status === 'ready_for_review' && batch.candidate_count === 0)
  );
}
