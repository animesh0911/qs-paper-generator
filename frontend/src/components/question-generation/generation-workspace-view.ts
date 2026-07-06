import type { GenerationBatch, GenerationBatchStatus } from '@/types';
import { shouldShowNoValidQuestionsMessage } from '@/lib/question-generation';

const ACTIVE_GENERATION_STATUSES: GenerationBatch['status'][] = [
  'queued',
  'generating_questions',
  'validating',
];

export const MAX_GENERATION_DRAFTS_TO_SHOW = 3;

export interface ReviewableGenerationBatch {
  batch: GenerationBatch;
  ready: boolean;
  failed: boolean;
  statusLabel: string;
  detail: string;
}

export function reviewableGenerationBatches(
  batches: GenerationBatch[],
): ReviewableGenerationBatch[] {
  return batches
    .filter((batch) =>
      [
        'queued',
        'generating_questions',
        'validating',
        'ready_for_review',
        // Keep failures visible: a batch that died mid-generation must not
        // silently vanish from the list — the teacher needs to see it failed and
        // open the reason, not wonder where their generation went.
        'failed',
      ].includes(batch.status),
    )
    .slice(0, MAX_GENERATION_DRAFTS_TO_SHOW)
    .map((batch) => {
      const ready = batch.status === 'ready_for_review';
      const failed = batch.status === 'failed';
      return {
        batch,
        ready,
        failed,
        statusLabel: ready ? 'Ready for review' : failed ? 'Failed' : 'Generating',
        detail: ready
          ? `${batch.candidate_count} candidate${batch.candidate_count === 1 ? '' : 's'} ready`
          : failed
            ? batch.error ||
              'Generation failed. Open for details, or start a new batch.'
            : 'We’ll update this when candidates are ready.',
      };
    });
}

export function isActiveGenerationStatus(status: GenerationBatch['status']) {
  return ACTIVE_GENERATION_STATUSES.includes(status);
}

export function progressStageLabel(status: GenerationBatchStatus) {
  switch (status) {
    case 'queued':
      return 'Preparing';
    case 'generating_questions':
      return 'Drafting Q&A';
    case 'validating':
      return 'Checking';
    case 'ready_for_review':
      return 'Ready to review';
    case 'accepted':
      return 'Imported';
    case 'expired':
      return 'Closed';
    case 'discarded':
      return 'Discarded';
    case 'failed':
      return 'Needs retry';
  }
}

export function progressStageDescription(status: GenerationBatchStatus) {
  switch (status) {
    case 'queued':
      return 'Your request is in line. This usually takes a moment.';
    case 'generating_questions':
      return 'Questions are being drafted from the selected topics.';
    case 'validating':
      return 'The draft is being checked before review.';
    case 'ready_for_review':
      return 'Review the candidates below and import the ones you want.';
    case 'accepted':
      return 'Accepted Q&A has been added to the Question bank.';
    case 'expired':
      return 'This request is no longer active.';
    case 'discarded':
      return 'You discarded this batch. Start a new one any time.';
    case 'failed':
      return 'No usable Q&A was created.';
  }
}

export function progressStep(status: GenerationBatchStatus) {
  switch (status) {
    case 'queued':
      return 0;
    case 'generating_questions':
    case 'validating':
      return 1;
    case 'ready_for_review':
    case 'accepted':
      return 2;
    case 'expired':
    case 'discarded':
    case 'failed':
      return 0;
  }
}

export function generationProgressView(
  batch: GenerationBatch | null,
  candidateCount: number,
) {
  const active = batch ? isActiveGenerationStatus(batch.status) : false;
  const noValidQuestions = batch ? shouldShowNoValidQuestionsMessage(batch) : false;
  const canShowReview = Boolean(batch) && !noValidQuestions;
  const importedCandidateCount = candidateCount;
  const canGenerateAnother = Boolean(batch) && batch?.status !== 'queued' && !active;
  const generateAnotherLabel =
    batch?.status === 'ready_for_review'
      ? 'Discard & generate another'
      : 'Generate another batch';

  return {
    active,
    noValidQuestions,
    canShowReview,
    step: batch ? progressStep(batch.status) : 0,
    importedCandidateCount,
    canGenerateAnother,
    generateAnotherLabel,
  };
}
