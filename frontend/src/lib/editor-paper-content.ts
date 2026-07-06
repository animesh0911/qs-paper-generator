import type { Block, PartialBlock } from '@blocknote/core';
import type { ContentItem } from '@/types';

interface ClipboardSlotView {
  questionBlockTree: {
    children: Array<{
      blockType: string;
      internalChoiceGroupIndex?: number;
      internalChoiceOptionIndex?: number;
      displayPrefix?: string;
      text: string;
    }>;
  };
}

export function blockNoteBlocksToContentItems(blocks: Block[]): ContentItem[] {
  return blocks.flatMap((block): ContentItem[] => {
    if (block.type === 'table') {
      const rows = blockNoteTableRows(block.content);
      return rows.length > 0 ? [{ type: 'table', rows }] : [];
    }

    const text = blockContentToText(block.content);
    return text.length > 0 ? [{ type: 'paragraph', text }] : [];
  });
}

export function blockNoteBlocksToText(blocks: Block[]): string[] {
  return blocks.map((block) => blockContentToText(block.content));
}

export function contentItemsToText(items: ContentItem[]): string {
  return items.map(contentItemToText).filter(Boolean).join('\n');
}

/**
 * Full printable question text for a Slot, for the per-question copy control.
 */
export function editorSlotClipboardText(slot: ClipboardSlotView): string {
  const lines: string[] = [];

  for (const region of slot.questionBlockTree.children) {
    if (
      region.blockType === 'internalChoiceBlock' &&
      (region.internalChoiceOptionIndex ?? 0) > 0
    ) {
      lines.push('OR');
    } else if (
      region.blockType === 'internalChoiceBlock' &&
      (region.internalChoiceGroupIndex ?? 0) > 0 &&
      (region.internalChoiceOptionIndex ?? 0) === 0
    ) {
      lines.push('');
    }

    const line = [region.displayPrefix, region.text]
      .map((part) => part?.trim() ?? '')
      .filter(Boolean)
      .join(' ');
    if (line) lines.push(line);
  }

  return lines.join('\n').trim();
}

export function contentItemToText(item: ContentItem): string {
  if (item.text) return item.text;
  if (item.latex) return item.latex;
  if (item.type === 'table' && item.rows) {
    return item.rows.map((row) => row.join(' | ')).join(' / ');
  }
  if (item.type === 'image_placeholder') {
    return item.caption ? `[Diagram: ${item.caption}]` : '[Diagram]';
  }
  return item.caption ?? '';
}

export function contentItemsToBlockNoteBlocks(
  items: ContentItem[],
): PartialBlock[] {
  const blocks = items.map(contentItemToBlockNoteBlock);

  return blocks.length > 0 ? blocks : [paragraphBlock('')];
}

function contentItemToBlockNoteBlock(item: ContentItem): PartialBlock {
  if (item.type === 'table' && item.rows) {
    return {
      type: 'table',
      content: {
        type: 'tableContent',
        rows: item.rows.map((row) => ({ cells: row })),
      },
    };
  }

  return paragraphBlock(contentItemToText(item));
}

function blockContentToText(content: unknown): string {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';

  return content
    .map((item) => {
      if (
        item &&
        typeof item === 'object' &&
        'text' in item &&
        typeof item.text === 'string'
      ) {
        return item.text;
      }
      return '';
    })
    .filter(Boolean)
    .join('');
}

function blockNoteTableRows(content: unknown): string[][] {
  if (
    !content ||
    typeof content !== 'object' ||
    !('type' in content) ||
    content.type !== 'tableContent' ||
    !('rows' in content) ||
    !Array.isArray(content.rows)
  ) {
    return [];
  }

  return content.rows
    .map((row) => {
      if (
        !row ||
        typeof row !== 'object' ||
        !('cells' in row) ||
        !Array.isArray(row.cells)
      ) {
        return [];
      }

      return row.cells.map(cellToText);
    })
    .filter((row) => row.length > 0);
}

function cellToText(cell: unknown): string {
  if (typeof cell === 'string') return cell;
  if (!Array.isArray(cell)) return '';

  return cell
    .map((item) => {
      if (typeof item === 'string') return item;
      if (
        item &&
        typeof item === 'object' &&
        'text' in item &&
        typeof item.text === 'string'
      ) {
        return item.text;
      }
      return '';
    })
    .join('');
}

export function paragraphBlock(content: string): PartialBlock {
  return {
    type: 'paragraph',
    content,
  };
}
