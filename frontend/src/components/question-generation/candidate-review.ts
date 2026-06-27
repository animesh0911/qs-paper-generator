import type { GeneratedQuestionCandidate } from '@/types';
import { contentItemsToPlainText } from '@/lib/content-items';

export function toggleRejectedCandidate(
  rejectedIds: Set<number>,
  candidateId: number,
): Set<number> {
  const next = new Set(rejectedIds);
  if (next.has(candidateId)) next.delete(candidateId);
  else next.add(candidateId);
  return next;
}

export function candidateReviewCounts(
  candidates: Pick<GeneratedQuestionCandidate, 'id'>[],
  rejectedIds: Set<number>,
): { accepted: number; rejected: number } {
  const rejected = candidates.filter((candidate) => rejectedIds.has(candidate.id)).length;
  return { accepted: candidates.length - rejected, rejected };
}

export function candidateQuestionText(candidate: GeneratedQuestionCandidate): string {
  const payload = candidate.payload;
  if (typeof payload.raw_text === 'string' && payload.raw_text.trim()) {
    return payload.raw_text.trim();
  }
  const text = contentItemsToPlainText(payload.content?.stem);
  if (text) return text;
  return 'Untitled generated Question';
}

export function candidateOptionTexts(
  candidate: GeneratedQuestionCandidate,
): { label: string; text: string }[] {
  const options = candidate.payload.content?.options;
  if (!Array.isArray(options)) return [];
  return options
    .map((option) => {
      if (!option || typeof option !== 'object') return null;
      const label =
        'label' in option && typeof option.label === 'string'
          ? option.label.trim()
          : '';
      const text =
        'text' in option && typeof option.text === 'string'
          ? option.text.trim()
          : contentItemsToPlainText('content' in option ? option.content : undefined);
      if (!label && !text) return null;
      return { label, text };
    })
    .filter((option): option is { label: string; text: string } => option !== null);
}

export function candidateAnswerText(candidate: GeneratedQuestionCandidate): string {
  const answer = candidate.payload.answer;
  return typeof answer === 'string' && answer.trim()
    ? answer.trim()
    : 'No answer was returned.';
}

export function candidateTopicLabels(candidate: GeneratedQuestionCandidate): string[] {
  const topics = candidate.payload.topic_names;
  return Array.isArray(topics)
    ? topics.filter((topic): topic is string => typeof topic === 'string' && Boolean(topic.trim()))
    : [];
}

export function candidateGroundingText(candidate: GeneratedQuestionCandidate): string {
  const payload = candidate.payload;
  const direct =
    candidate.grounding_manifest ?? payload.grounding_manifest ?? payload.grounding_context;
  if (typeof direct === 'string' && direct.trim()) return direct.trim();
  if (direct && typeof direct === 'object') return JSON.stringify(direct);

  const source = payload.source;
  if (source && typeof source === 'object') {
    const citation = source.citation ?? source.citations ?? source.page_range;
    if (typeof citation === 'string' && citation.trim()) return citation.trim();
    if (citation && typeof citation === 'object') return JSON.stringify(citation);
    if (typeof source.name === 'string' && source.name.trim()) return source.name.trim();
  }

  return '';
}
