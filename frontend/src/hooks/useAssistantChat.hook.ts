/**
 * Mocked assistant review state for the bottom chat scaffold.
 *
 * Drives the review result card without any backend or model call: a Review
 * request flips to a `pending` state and, after a short simulated delay,
 * resolves to a deterministic result derived from the current paper view.
 *
 * Patterns:
 * - No network, no LLM, no randomness — the result is a pure function of the
 *   live `EditorPaperView`, so #34 can swap `buildReviewResult` for the real
 *   `GET /api/ai/jobs/{jobId}/` result without changing the card.
 * - Result content is factual (section/question/marks counts, real validation
 *   warnings); it never fabricates quality claims (CLAUDE.md Rule 12).
 *
 * Where it fits:
 * - Used by: `src/hooks/useEditorWorkspace.hook.ts`.
 * - Uses: `src/lib/editor-paper.ts`.
 *
 * @module useAssistantChat
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { EditorPaperView } from '@/lib/editor-paper';

export type AssistantStatus = 'idle' | 'pending' | 'complete';

export interface AssistantAffectedArea {
  id: string;
  label: string;
}

export interface AssistantResult {
  kind: 'review';
  summary: [string, string];
  affected: AssistantAffectedArea[];
  canApply: boolean;
}

const REVIEW_LATENCY_MS = 600;

function buildReviewResult(view: EditorPaperView): AssistantResult {
  const sectionCount = view.sections.length;
  const questionCount = view.validationSummary.totalSlots;
  const totalMarks = view.sections.reduce(
    (sum, section) => sum + section.marks,
    0,
  );
  const warnings = view.validationSummary.warnings;
  const overview = `Reviewed “${view.title}” — ${sectionCount} sections, ${questionCount} questions, ${totalMarks} marks.`;
  const finding =
    warnings.length > 0
      ? warnings[0]
      : 'No structural warnings detected across the sections.';

  return {
    kind: 'review',
    summary: [overview, finding],
    affected: view.sections
      .slice(0, 2)
      .map((section) => ({ id: section.sectionId, label: section.title })),
    canApply: true,
  };
}

export function useAssistantChat({ view }: { view: EditorPaperView }) {
  const [status, setStatus] = useState<AssistantStatus>('idle');
  const [result, setResult] = useState<AssistantResult | null>(null);
  const timerRef = useRef<number | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => clearTimer, [clearTimer]);

  const runReview = useCallback(() => {
    clearTimer();
    setResult(null);
    setStatus('pending');
    const reviewResult = buildReviewResult(view);
    timerRef.current = window.setTimeout(() => {
      setResult(reviewResult);
      setStatus('complete');
      timerRef.current = null;
    }, REVIEW_LATENCY_MS);
  }, [clearTimer, view]);

  const dismissResult = useCallback(() => {
    clearTimer();
    setStatus('idle');
    setResult(null);
  }, [clearTimer]);

  return {
    assistantStatus: status,
    assistantResult: result,
    runReview,
    dismissResult,
  };
}
