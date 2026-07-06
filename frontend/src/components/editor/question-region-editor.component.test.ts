/**
 * Tests for Question region editor commit policy.
 *
 * These tests pin when draft BlockNote content becomes a Slot override so
 * structured actions like swap, undo, and restore are not clobbered by teardown.
 *
 * @module questionRegionEditorTests
 */
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { shouldCommitQuestionRegionDraft } from '@/lib/question-region-commit';
import type { EditorQuestionRegionBlock } from '@/lib/editor-paper';
import type { ContentItem } from '@/types';
import { QuestionRegionEditor } from './question-region-editor.component';

describe('QuestionRegionEditor rendering', () => {
  it('keeps selected math regions typeset instead of switching to raw BlockNote text', () => {
    const region: EditorQuestionRegionBlock = {
      blockType: 'questionStemBlock',
      regionKey: 'stem',
      text: '$$\\text{Mg} \\rightarrow \\ddot{\\text{O}}$$',
      displayPrefix: '',
      displaySuffix: '',
      content: [
        {
          type: 'paragraph',
          text: '$$\\text{Mg} \\rightarrow \\ddot{\\text{O}}$$',
        },
      ],
      blockNoteBlocks: [
        {
          type: 'paragraph',
          content: '$$\\text{Mg} \\rightarrow \\ddot{\\text{O}}$$',
        },
      ],
      editable: true,
      sourceKind: 'source_question_text',
      editTarget: 'slot_override',
      sourceLocked: true,
      isOverridden: false,
    };

    const html = renderToStaticMarkup(
      React.createElement(QuestionRegionEditor, {
        region,
        editable: true,
        onCommit: () => undefined,
      }),
    );

    expect(html).toContain('class="katex"');
    expect(html).not.toContain('bn-editor');
    expect(html).not.toContain('$$\\text{Mg}');
  });
});

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
