/**
 * Commit policy for editable Question region drafts.
 *
 * This module keeps BlockNote draft commit rules testable outside the React
 * component so structured editor actions cannot be overwritten by teardown.
 *
 * Where it fits:
 * - Used by: `QuestionRegionEditor`.
 * - Uses: `ContentItem`.
 *
 * @module questionRegionCommit
 */
import type { ContentItem } from '@/types';

type QuestionRegionCommitTrigger = 'blur' | 'teardown';

export function shouldCommitQuestionRegionDraft({
  latestContent,
  committedContent,
  trigger,
}: {
  latestContent: ContentItem[];
  committedContent: ContentItem[];
  trigger: QuestionRegionCommitTrigger;
}) {
  if (trigger === 'teardown') return false;
  return JSON.stringify(latestContent) !== JSON.stringify(committedContent);
}
