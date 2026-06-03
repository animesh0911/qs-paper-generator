/**
 * BlockNote-backed editor for editable PaperDocument chrome text.
 *
 * Paper title, section headings, and instruction text share the same
 * lifecycle: static display until selected, BlockNote editing, then commit
 * normalized text on blur.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `src/lib/editor-paper.ts`.
 *
 * @module PaperChromeEditor
 */
import { useEffect, useRef } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import { Trash2 } from 'lucide-react';
import {
  blockNoteBlocksToText,
  type EditorPaperChromeBlock,
} from '@/lib/editor-paper';
import { cn } from '@/lib/utils';

export function PaperChromeEditor({
  block,
  editable,
  className,
  onCommit,
  onDelete,
}: {
  block: EditorPaperChromeBlock;
  editable: boolean;
  className?: string;
  onCommit: (text: string) => void;
  onDelete?: () => void;
}) {
  const deleteControl =
    block.editCapabilities.delete && onDelete ? (
      <button
        type="button"
        data-editor-chrome
        className="qpg-paper-chrome-delete inline-flex h-5 w-5 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`Delete ${formatChromeBlockLabel(block.blockType)}`}
        title={`Delete ${formatChromeBlockLabel(block.blockType)}`}
        onMouseDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onDelete();
        }}
      >
        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    ) : null;

  if (!editable) {
    return (
      <div className="qpg-paper-chrome-control-group">
        <div className={cn('qpg-paper-chrome-text', className)}>
          {block.text.split('\n').map((line, index) => (
            <p key={`${block.regionKey}:${index}`}>{line}</p>
          ))}
        </div>
        {deleteControl}
      </div>
    );
  }

  return (
    <div className="qpg-paper-chrome-control-group">
      <ActivePaperChromeEditor
        block={block}
        className={className}
        onCommit={onCommit}
      />
      {deleteControl}
    </div>
  );
}

function formatChromeBlockLabel(blockType: string) {
  return blockType.replace(/_/g, ' ');
}

function ActivePaperChromeEditor({
  block,
  className,
  onCommit,
}: {
  block: EditorPaperChromeBlock;
  className?: string;
  onCommit: (text: string) => void;
}) {
  const mountedRef = useRef(false);
  const suppressInitialChangeRef = useRef(true);
  const latestTextRef = useRef(block.text);
  const editor = useCreateBlockNote(
    {
      animations: false,
      initialContent: block.blockNoteBlocks,
    },
    [block.regionKey, block.text],
  );

  useEffect(() => {
    mountedRef.current = true;
    suppressInitialChangeRef.current = true;
    latestTextRef.current = block.text;
    const timeoutId = window.setTimeout(() => {
      suppressInitialChangeRef.current = false;
    }, 0);

    return () => {
      mountedRef.current = false;
      window.clearTimeout(timeoutId);
    };
  }, [block.regionKey, block.text]);

  function handleCommit() {
    onCommit(latestTextRef.current);
  }

  return (
    <div onBlurCapture={handleCommit}>
      <BlockNoteView
        editor={editor}
        editable
        onChange={(changedEditor) => {
          if (!mountedRef.current || suppressInitialChangeRef.current) return;
          latestTextRef.current = blockNoteBlocksToText(
            changedEditor.document,
          ).join('\n');
        }}
        formattingToolbar={false}
        linkToolbar={false}
        slashMenu={false}
        sideMenu={false}
        filePanel={false}
        tableHandles={false}
        emojiPicker={false}
        comments={false}
        className={cn('qpg-question-blocknote', className)}
      />
    </div>
  );
}
