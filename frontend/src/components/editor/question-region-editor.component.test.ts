/**
 * Tests for Question region editor commit policy.
 *
 * These tests pin when draft BlockNote content becomes a Slot override so
 * structured actions like swap, undo, and restore are not clobbered by teardown.
 *
 * @module questionRegionEditorTests
 */
import { describe, expect, it } from 'vitest';
import { shouldCommitQuestionRegionDraft } from '@/lib/question-region-commit';
import type { ContentItem } from '@/types';

describe('QuestionRegionEditor commit policy', () => {
  const committedContent: ContentItem[] = [
    { type: 'paragraph', text: 'Source stem.' },
  ];
  const draftContent: ContentItem[] = [
    { type: 'paragraph', text: 'Teacher draft stem.' },
  ];

  it('commits changed draft content on blur', () => {
    expect(
      shouldCommitQuestionRegionDraft({
        latestContent: draftContent,
        committedContent,
        trigger: 'blur',
      }),
    ).toBe(true);
  });

  it('does not commit a changed draft during teardown', () => {
    expect(
      shouldCommitQuestionRegionDraft({
        latestContent: draftContent,
        committedContent,
        trigger: 'teardown',
      }),
    ).toBe(false);
  });
});
