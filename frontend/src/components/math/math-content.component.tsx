/**
 * Inline renderer for a ContentItem[] that may carry LaTeX.
 *
 * Editor previews (the non-editable question region and the alternatives
 * overlay) used to flatten content items into a plain string via
 * `contentItemToText`, which dumped a `latex` item's source verbatim. Rendering
 * the structured items here lets the math typeset with KaTeX while everything
 * else stays inline text — matching the compact, single-line preview style.
 *
 * The paper preview/print surface keeps its own block-level renderer because it
 * needs paper-specific table markup and CSS classes; this one is deliberately
 * lightweight and inline.
 *
 * @module MathContent
 */
import { Fragment } from 'react';
import type { ContentItem } from '@/types';
import { MathExpression } from './math-expression.component';

function inlineItemToText(item: ContentItem): string {
  if (item.text) return item.text;
  if (item.type === 'table' && item.rows) {
    return item.rows.map((row) => row.join(' | ')).join(' / ');
  }
  if (item.type === 'image_placeholder') {
    return item.caption ? `[Diagram: ${item.caption}]` : '[Diagram]';
  }
  return item.caption ?? '';
}

/**
 * Renders content items inline. `latex` items typeset with KaTeX; every other
 * item falls back to the same flattened text the previews showed before.
 */
export function MathContent({ items }: { items: ContentItem[] }) {
  return (
    <>
      {items.map((item, index) => {
        // `text` wins so labelled prose stays plain, mirroring contentItemToText.
        if (!item.text && item.latex) {
          return (
            <MathExpression key={index} latex={item.latex} display={false} />
          );
        }
        const text = inlineItemToText(item);
        return text ? <Fragment key={index}>{text}</Fragment> : null;
      })}
    </>
  );
}
