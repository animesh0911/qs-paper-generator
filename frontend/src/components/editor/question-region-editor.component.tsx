/**
 * BlockNote-backed editor for source Question regions.
 *
 * The module keeps BlockNote lifecycle quirks local to editable Question
 * regions. Callers pass canonical region content and receive committed
 * ContentItem arrays on blur.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `src/lib/editor-paper.ts`.
 *
 * @module QuestionRegionEditor
 */
import { useEffect, useRef } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import { blockNoteBlocksToContentItems } from '@/lib/editor-paper';
import type { EditorQuestionRegionBlock } from '@/lib/editor-paper';
import type { ContentItem } from '@/types';

export function QuestionRegionEditor({
  region,
  editable,
  onCommit,
}: {
  region: EditorQuestionRegionBlock;
  editable: boolean;
  onCommit: (content: ContentItem[]) => void;
}) {
  if (!editable) {
    return (
      <div className="qpg-question-blocknote qpg-question-region-text">
        {region.text}
      </div>
    );
  }

  return <ActiveQuestionRegionEditor region={region} onCommit={onCommit} />;
}

function ActiveQuestionRegionEditor({
  region,
  onCommit,
}: {
  region: EditorQuestionRegionBlock;
  onCommit: (content: ContentItem[]) => void;
}) {
  const mountedRef = useRef(false);
  const suppressInitialChangeRef = useRef(true);
  const latestContentRef = useRef(region.content);
  const committedContentRef = useRef(region.content);
  const onCommitRef = useRef(onCommit);
  const editor = useCreateBlockNote(
    {
      animations: false,
      initialContent: region.blockNoteBlocks,
    },
    [region.regionKey, region.text],
  );

  useEffect(() => {
    onCommitRef.current = onCommit;
  }, [onCommit]);

  useEffect(() => {
    mountedRef.current = true;
    suppressInitialChangeRef.current = true;
    latestContentRef.current = region.content;
    committedContentRef.current = region.content;
    const timeoutId = window.setTimeout(() => {
      suppressInitialChangeRef.current = false;
    }, 0);

    return () => {
      commitLatestContent();
      mountedRef.current = false;
      window.clearTimeout(timeoutId);
    };
  }, [region.content, region.regionKey, region.text]);

  function commitLatestContent() {
    if (
      JSON.stringify(latestContentRef.current) ===
      JSON.stringify(committedContentRef.current)
    ) {
      return;
    }

    onCommitRef.current(latestContentRef.current);
    committedContentRef.current = latestContentRef.current;
  }

  function handleCommit() {
    commitLatestContent();
  }

  return (
    <div onBlurCapture={handleCommit}>
      <BlockNoteView
        editor={editor}
        editable
        onChange={(changedEditor) => {
          if (!mountedRef.current || suppressInitialChangeRef.current) return;
          latestContentRef.current = blockNoteBlocksToContentItems(
            changedEditor.document,
          );
        }}
        formattingToolbar={false}
        linkToolbar={false}
        slashMenu={false}
        sideMenu={false}
        filePanel={false}
        tableHandles={false}
        emojiPicker={false}
        comments={false}
        className="qpg-question-blocknote"
      />
    </div>
  );
}
