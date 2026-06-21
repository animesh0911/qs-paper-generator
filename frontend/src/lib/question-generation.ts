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

export function splitTopicNames(raw: string): string[] {
  return raw
    .split(/[\n,]/)
    .map((topic) => topic.trim())
    .filter(Boolean);
}

export function buildGenerationBatchPayload({
  chapterSlugs,
  topicNamesByChapter,
  difficulty,
}: {
  chapterSlugs: string[];
  topicNamesByChapter: Record<string, string>;
  difficulty: GenerationDifficultyLabel;
}): GenerationBatchCreateRequest {
  if (chapterSlugs.length === 0) {
    throw new Error('Select at least one Chapter.');
  }

  const selected = new Set(chapterSlugs);
  return {
    chapter_slugs: chapterSlugs,
    topic_names: chapterSlugs.flatMap((slug) =>
      selected.has(slug) ? splitTopicNames(topicNamesByChapter[slug] ?? '') : [],
    ),
    difficulty_preset: BACKEND_DIFFICULTY_BY_LABEL[difficulty],
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
    case 'failed':
      return 'Failed';
  }
}

export function generationStageDescription(status: GenerationBatchStatus): string {
  switch (status) {
    case 'queued':
      return 'The request is waiting for the generation worker.';
    case 'generating_questions':
      return 'The worker is drafting candidates from the selected Chapter scope and Topic hints.';
    case 'validating':
      return 'Candidates are being checked before they can be reviewed.';
    case 'ready_for_review':
      return 'Candidates are ready, but they are not in the Question bank until review is complete.';
    case 'accepted':
      return 'Reviewed candidates have been accepted into the Question bank.';
    case 'expired':
      return 'This generation job expired before review was completed.';
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
