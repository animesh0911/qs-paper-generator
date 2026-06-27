import type { ContentItem, GeneratedQuestionContentItem } from '@/types';

type TextContentItem = ContentItem | GeneratedQuestionContentItem;

export interface ContentItemsTextOptions {
  includeImages?: boolean;
  joinWith?: string;
  tableCellSeparator?: string;
  tableRowSeparator?: string;
}

export function contentItemsToPlainText(
  items: unknown,
  {
    includeImages = false,
    joinWith = ' ',
    tableCellSeparator = ' ',
    tableRowSeparator = ' ',
  }: ContentItemsTextOptions = {},
): string {
  if (!Array.isArray(items)) return '';
  return items
    .map((item) =>
      contentItemToPlainText(item, {
        includeImages,
        tableCellSeparator,
        tableRowSeparator,
      }),
    )
    .filter(Boolean)
    .join(joinWith)
    .trim();
}

function contentItemToPlainText(
  item: unknown,
  {
    includeImages,
    tableCellSeparator,
    tableRowSeparator,
  }: Required<
    Pick<
      ContentItemsTextOptions,
      'includeImages' | 'tableCellSeparator' | 'tableRowSeparator'
    >
  >,
): string {
  if (!item || typeof item !== 'object') return '';
  const contentItem = item as TextContentItem;
  const imageLike =
    Boolean(contentItem.assetId) || contentItem.type === 'image_placeholder';

  if (imageLike && !includeImages) return '';
  if (contentItem.text) return contentItem.text.trim();
  if (contentItem.latex) return contentItem.latex.trim();
  if (contentItem.rows?.length) {
    return contentItem.rows
      .map((row) => row.join(tableCellSeparator))
      .join(tableRowSeparator)
      .trim();
  }
  if (imageLike) {
    return contentItem.caption ? `[Diagram: ${contentItem.caption}]` : '[Diagram]';
  }
  return contentItem.caption?.trim() ?? '';
}
