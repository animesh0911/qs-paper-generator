import { useState } from 'react';
import type { GeneratedQuestionCandidate } from '@/types';
import { Button } from '@/components/ui/button';
import {
  candidateAnswerText,
  candidateOptionTexts,
  candidateQuestionText,
  candidateReviewCounts,
  candidateTopicLabels,
  toggleRejectedCandidate,
} from './candidate-review';

export interface CandidateReviewPanelProps {
  candidates: GeneratedQuestionCandidate[];
  candidatesLoading: boolean;
  candidatesError: string;
  accepting: boolean;
  acceptError: string;
  initialRejectedCandidateIds?: number[];
  mode?: 'review' | 'readOnly';
  onAcceptCandidates: (acceptedCandidateIds: number[]) => void;
  onRetryCandidates: () => void;
}

function candidateTypeLabel(candidate: GeneratedQuestionCandidate): string {
  const parts = [
    candidate.payload.qtype,
    typeof candidate.payload.marks === 'number'
      ? `${candidate.payload.marks} mark${candidate.payload.marks === 1 ? '' : 's'}`
      : '',
    candidate.payload.chapter_slug,
  ].filter((part): part is string => typeof part === 'string' && Boolean(part));
  return parts.join(' · ');
}

export function CandidateReviewPanel({
  candidates,
  candidatesLoading,
  candidatesError,
  accepting,
  acceptError,
  initialRejectedCandidateIds = [],
  mode = 'review',
  onAcceptCandidates,
  onRetryCandidates,
}: CandidateReviewPanelProps) {
  const readOnly = mode === 'readOnly';
  const visibleCandidates = readOnly
    ? candidates.filter((candidate) => candidate.status === 'accepted')
    : candidates;
  const [rejectedCandidateIds, setRejectedCandidateIds] = useState<Set<number>>(
    () => new Set(initialRejectedCandidateIds),
  );
  const reviewCounts = candidateReviewCounts(
    visibleCandidates,
    rejectedCandidateIds,
  );

  function toggleRejected(candidateId: number) {
    setRejectedCandidateIds((current) =>
      toggleRejectedCandidate(current, candidateId),
    );
  }

  function acceptedCandidateIds() {
    return visibleCandidates
      .filter((candidate) => !rejectedCandidateIds.has(candidate.id))
      .map((candidate) => candidate.id);
  }

  function importAcceptedCandidates() {
    onAcceptCandidates(acceptedCandidateIds());
  }

  return (
    <div className="border-t pt-5 space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h2 className="font-medium">
            {readOnly ? 'Imported Q&A from this session' : 'Review generated Q&A'}
          </h2>
          <p className="text-sm text-muted-foreground">
            {readOnly
              ? `${visibleCandidates.length} imported Q&A ${
                  visibleCandidates.length === 1 ? 'item is' : 'items are'
                } shown with answers from this AI generation session.`
              : `${visibleCandidates.length} candidate${
                  visibleCandidates.length === 1 ? '' : 's'
                } ready`}
          </p>
        </div>
        <div className="inline-flex w-fit rounded-md border bg-background px-3 py-2 text-sm">
          {readOnly ? (
            <>
              <span className="font-medium">{visibleCandidates.length}</span> imported
            </>
          ) : (
            <>
              <span className="font-medium">{reviewCounts.accepted}</span> accepted ·{' '}
              <span className="font-medium">{reviewCounts.rejected}</span> rejected
            </>
          )}
        </div>
      </div>

      {candidatesLoading && <p className="text-sm">Loading generated candidates…</p>}

      {!candidatesLoading && candidatesError && (
        <div role="alert" className="space-y-2">
          <div>
            <p className="text-sm font-medium">Candidates could not be loaded.</p>
            <p className="mt-1 text-sm text-muted-foreground">{candidatesError}</p>
          </div>
          <Button type="button" size="sm" onClick={onRetryCandidates}>
            Try loading candidates again
          </Button>
        </div>
      )}

      {!candidatesLoading && !candidatesError && visibleCandidates.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {readOnly
            ? 'No imported Q&A found for this session.'
            : 'This batch is ready, but no generated candidates were returned.'}
        </p>
      )}

      {!candidatesLoading && !candidatesError && visibleCandidates.length > 0 && (
        <ul
          className="max-h-[64vh] overflow-y-auto rounded-md border bg-background"
          aria-label="Generated Q&A candidates"
        >
          {visibleCandidates.map((candidate) => {
            const rejected = rejectedCandidateIds.has(candidate.id);
            const topics = candidateTopicLabels(candidate);
            const options = candidateOptionTexts(candidate);
            return (
              <li
                key={candidate.id}
                className={`space-y-3 border-b p-4 last:border-b-0 ${
                  rejected ? 'bg-secondary/70' : 'bg-background'
                }`}
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-1">
                    <p className="font-medium">{candidateQuestionText(candidate)}</p>
                    <p className="text-xs text-muted-foreground">
                      {candidateTypeLabel(candidate) || 'Generated candidate'}
                    </p>
                  </div>
                  {!readOnly && (
                    <Button
                      type="button"
                      size="sm"
                      variant={rejected ? 'outline' : 'ghost'}
                      onClick={() => toggleRejected(candidate.id)}
                    >
                      {rejected ? 'Undo reject' : 'Reject'}
                    </Button>
                  )}
                </div>

                {options.length > 0 && (
                  <ol className="grid gap-2 text-sm sm:grid-cols-2">
                    {options.map((option, index) => (
                      <li
                        key={`${option.label || index}-${option.text}`}
                        className="flex gap-2 rounded-md border bg-white/70 px-3 py-2"
                      >
                        {option.label && (
                          <span className="font-medium">{option.label}.</span>
                        )}
                        <span>{option.text}</span>
                      </li>
                    ))}
                  </ol>
                )}

                <div className="rounded-md border bg-secondary/50 p-3">
                  <p className="text-xs font-medium text-muted-foreground">Answer</p>
                  <p className="mt-1 text-sm">{candidateAnswerText(candidate)}</p>
                </div>

                {topics.length > 0 && (
                  <p className="text-sm text-muted-foreground">
                    Topics: {topics.join(', ')}
                  </p>
                )}

                {!readOnly && rejected && (
                  <p className="text-sm font-medium" role="status">
                    Rejected locally. Use Undo to include this candidate again.
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {!readOnly && acceptError && (
        <div
          className="rounded-md border border-destructive/40 bg-destructive/5 p-3"
          role="alert"
        >
          <p className="text-sm font-medium">Import failed.</p>
          <p className="mt-1 text-sm text-muted-foreground">{acceptError}</p>
        </div>
      )}

      {!readOnly && (
        <div className="sticky bottom-0 -mx-5 border-t bg-background/95 px-5 py-4 shadow-lg backdrop-blur sm:-mx-6 sm:px-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm">
              <span className="font-medium">{reviewCounts.accepted}</span> accepted ·{' '}
              <span className="font-medium">{reviewCounts.rejected}</span> rejected
            </p>
            <Button
              type="button"
              onClick={importAcceptedCandidates}
              disabled={
                accepting ||
                candidatesLoading ||
                Boolean(candidatesError) ||
                visibleCandidates.length === 0 ||
                reviewCounts.accepted === 0
              }
            >
              {accepting ? 'Importing accepted Q&A…' : 'Import accepted Q&A'}
            </Button>
          </div>
          {reviewCounts.accepted === 0 && visibleCandidates.length > 0 && (
            <p className="mt-2 text-sm text-muted-foreground">
              Restore at least one candidate to import into the Question bank.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
