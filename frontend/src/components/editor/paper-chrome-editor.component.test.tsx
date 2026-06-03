/**
 * Tests for editable paper chrome controls.
 *
 * These tests pin the visible affordance policy for PaperDocument chrome and
 * instruction blocks: delete controls appear only when the canonical block
 * allows deletion.
 *
 * @module paperChromeEditorTests
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { PaperChromeEditor } from './paper-chrome-editor.component';
import type { EditorPaperChromeBlock } from '@/lib/editor-paper';

describe('PaperChromeEditor', () => {
  it('renders a delete control only when the block can be deleted', () => {
    const deletableHtml = renderToStaticMarkup(
      <PaperChromeEditor
        block={chromeBlock({ text: true, delete: true, reorder: false })}
        editable={false}
        onCommit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    const fixedHtml = renderToStaticMarkup(
      <PaperChromeEditor
        block={chromeBlock({ text: true, delete: false, reorder: false })}
        editable={false}
        onCommit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(deletableHtml).toContain('aria-label="Delete series"');
    expect(fixedHtml).not.toContain('Delete series');
  });
});

function chromeBlock(
  editCapabilities: EditorPaperChromeBlock['editCapabilities'],
): EditorPaperChromeBlock {
  return {
    blockId: 'chrome:series',
    blockType: 'series',
    regionKey: 'chrome:series',
    text: 'LMNK2',
    blockNoteBlocks: [{ type: 'paragraph', content: 'LMNK2' }],
    editable: editCapabilities.text,
    editCapabilities,
    sourceKind: 'paper_chrome',
    editTarget: 'paper_document',
    sourceLocked: false,
  };
}
