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
import { Fragment, type ReactNode } from 'react';
import type { ContentItem } from '@/types';
import { MathExpression } from './math-expression.component';
import { LatexText } from './latex-text.component';
import { latexHasMath, latexParses } from './latex';

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

/** An asset-backed image item, optionally carrying a backend-resolved `url`. */
type ImageContentItem = ContentItem & { url?: string };

function isImageItem(item: ContentItem): item is ImageContentItem {
  return item.type === 'image' && Boolean(item.assetId);
}

/**
 * Renders a stored diagram inline. Falls back to a visible `[Diagram]` marker
 * when the backend did not resolve a URL, so a missing asset never disappears
 * silently — teachers must see that the source question carries a figure.
 */
function QuestionImage({ item }: { item: ImageContentItem }) {
  if (!item.url) {
    return (
      <span className="qpg-question-image-missing">
        {item.caption ? `[Diagram: ${item.caption}]` : '[Diagram]'}
      </span>
    );
  }
  return (
    <img
      className="qpg-question-image"
      src={item.url}
      alt={item.caption || 'Question diagram'}
      loading="lazy"
    />
  );
}

interface MathSegment {
  text: string;
  math: boolean;
  display: boolean;
}

const MATH_DELIMITERS = [
  { open: '$$', close: '$$', display: true },
  { open: '\\[', close: '\\]', display: true },
  { open: '\\(', close: '\\)', display: false },
  { open: '$', close: '$', display: false },
];

function isEscaped(text: string, index: number): boolean {
  let slashCount = 0;
  for (let pos = index - 1; pos >= 0 && text[pos] === '\\'; pos -= 1) {
    slashCount += 1;
  }
  return slashCount % 2 === 1;
}

function findDelimiter(text: string, from: number) {
  let best: {
    index: number;
    open: string;
    close: string;
    display: boolean;
  } | null = null;
  for (const delimiter of MATH_DELIMITERS) {
    let index = text.indexOf(delimiter.open, from);
    while (index !== -1 && isEscaped(text, index)) {
      index = text.indexOf(delimiter.open, index + delimiter.open.length);
    }
    if (index !== -1 && (best === null || index < best.index)) {
      best = { index, ...delimiter };
    }
  }
  return best;
}

function splitMathText(text: string): MathSegment[] {
  const segments: MathSegment[] = [];
  let cursor = 0;

  while (cursor < text.length) {
    const delimiter = findDelimiter(text, cursor);
    if (!delimiter) break;
    const contentStart = delimiter.index + delimiter.open.length;
    const contentEnd = text.indexOf(delimiter.close, contentStart);
    if (contentEnd === -1) break;
    if (delimiter.index > cursor) {
      segments.push(
        ...splitPlainFormulaText(text.slice(cursor, delimiter.index)),
      );
    }
    segments.push({
      text: text.slice(contentStart, contentEnd),
      math: true,
      display: delimiter.display,
    });
    cursor = contentEnd + delimiter.close.length;
  }

  if (cursor < text.length) {
    segments.push(...splitPlainFormulaText(text.slice(cursor)));
  }
  return segments;
}

const PLAIN_FORMULA_PATTERN =
  /C[nN]H2[nN]\s*\+\s*1\s*-\s*OH|\b(?=(?:[A-Z][a-z]?\d*)+\b)(?=[A-Za-z0-9]*\d)[A-Z][A-Za-z0-9]*\b/g;

function plainFormulaToLatex(value: string): string | null {
  if (/^C[nN]H2[nN]\s*\+\s*1\s*-\s*OH$/.test(value)) {
    return String.raw`C_nH_{2n+1}-OH`;
  }

  // Conservative chemistry shorthand: only formula-looking tokens with at
  // least one digit reach here (H2SO4, KMnO4, O2). Words like Class/OR/What
  // never match because they lack a digit and lowercase runs are disallowed.
  if (!/^(?:[A-Z][a-z]?\d*)+$/.test(value) || !/\d/.test(value)) {
    return null;
  }

  return value.replace(/(\d+)/g, '_{$1}');
}

const RAW_LATEX_COMMAND_PATTERN = /\\[A-Za-z]+/g;

function findRawLatexStart(text: string, from: number): number {
  RAW_LATEX_COMMAND_PATTERN.lastIndex = from;
  let match = RAW_LATEX_COMMAND_PATTERN.exec(text);
  while (match) {
    if (!isEscaped(text, match.index)) return match.index;
    match = RAW_LATEX_COMMAND_PATTERN.exec(text);
  }
  return -1;
}

function consumeRawLatexRun(text: string, start: number): number {
  let index = start;
  let braceDepth = 0;
  let bracketDepth = 0;

  while (index < text.length) {
    const char = text[index];

    if (char === '\\') {
      const command = /^\\[A-Za-z]+/.exec(text.slice(index));
      index += command ? command[0].length : 1;
      continue;
    }

    if (char === '{') {
      braceDepth += 1;
      index += 1;
      continue;
    }
    if (char === '}') {
      braceDepth = Math.max(0, braceDepth - 1);
      index += 1;
      continue;
    }
    if (char === '[') {
      bracketDepth += 1;
      index += 1;
      continue;
    }
    if (char === ']') {
      bracketDepth = Math.max(0, bracketDepth - 1);
      index += 1;
      continue;
    }

    if (braceDepth > 0 || bracketDepth > 0) {
      index += 1;
      continue;
    }

    // At top level, a raw extracted equation is made of commands, chemical
    // symbols emitted as commands, operators, digits, labels, and whitespace.
    // A bare lowercase word means prose has resumed. This deliberately stops
    // before markers like `(b)` so adjacent equations can be rendered as two
    // math runs instead of one malformed blob.
    if (
      char === '(' &&
      /[a-z]/.test(text[index + 1] ?? '') &&
      text[index + 2] === ')'
    ) {
      break;
    }
    if (/[a-z]/.test(char)) break;
    index += 1;
  }

  return index;
}

function trimRawLatexEnd(text: string, start: number, end: number): number {
  let candidateEnd = end;
  while (candidateEnd > start) {
    const candidate = text.slice(start, candidateEnd).trim();
    if (candidate && latexHasMath(candidate) && latexParses(candidate)) {
      return start + text.slice(start, candidateEnd).length;
    }
    candidateEnd -= 1;
  }
  return start;
}

function splitTextWithRawLatex(text: string): MathSegment[] {
  const segments: MathSegment[] = [];
  let cursor = 0;

  while (cursor < text.length) {
    const start = findRawLatexStart(text, cursor);
    if (start === -1) break;

    if (start > cursor) {
      segments.push(...splitPlainFormulaOnly(text.slice(cursor, start)));
    }

    const consumedEnd = consumeRawLatexRun(text, start);
    const latexEnd = trimRawLatexEnd(text, start, consumedEnd);
    if (latexEnd > start) {
      segments.push({
        text: text.slice(start, latexEnd).trimEnd(),
        math: true,
        display: false,
      });
      cursor = latexEnd;
    } else {
      const command = /^\\[A-Za-z]+/.exec(text.slice(start));
      const skipTo = start + (command ? command[0].length : 1);
      segments.push(...splitPlainFormulaOnly(text.slice(cursor, skipTo)));
      cursor = skipTo;
    }
  }

  if (cursor < text.length) {
    segments.push(...splitPlainFormulaOnly(text.slice(cursor)));
  }
  return segments;
}

function splitPlainFormulaOnly(text: string): MathSegment[] {
  const segments: MathSegment[] = [];
  let cursor = 0;

  for (const match of text.matchAll(PLAIN_FORMULA_PATTERN)) {
    const value = match[0];
    const index = match.index ?? 0;
    const latex = plainFormulaToLatex(value);
    if (!latex) continue;
    if (index > cursor) {
      segments.push({
        text: text.slice(cursor, index),
        math: false,
        display: false,
      });
    }
    segments.push({ text: latex, math: true, display: false });
    cursor = index + value.length;
  }

  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), math: false, display: false });
  }
  return segments;
}

function splitPlainFormulaText(text: string): MathSegment[] {
  return splitTextWithRawLatex(text);
}

export function MathText({ text }: { text: string }) {
  const nodes: ReactNode[] = splitMathText(text).map((segment, index) => {
    if (segment.math) {
      return (
        <MathExpression
          key={index}
          latex={segment.text}
          display={segment.display}
        />
      );
    }
    return <Fragment key={index}>{segment.text}</Fragment>;
  });
  return <>{nodes}</>;
}

/**
 * Renders content items inline. `latex` items typeset with KaTeX; every other
 * item falls back to the same flattened text the previews showed before.
 */
export function MathContent({ items }: { items: ContentItem[] }) {
  return (
    <>
      {items.map((item, index) => {
        if (isImageItem(item)) {
          return <QuestionImage key={index} item={item} />;
        }
        // Prefer the `latex` field when it carries real math: either the item
        // has no plain text, or its latex still holds math once `\text{…}` prose
        // is stripped (e.g. a sentence ending in `\sqrt{3}`). Plain-prose latex
        // wrappers fall through to text so labelled prose stays plain.
        if (item.latex && (!item.text || latexHasMath(item.latex))) {
          return <LatexText key={index} latex={item.latex} />;
        }
        const text = inlineItemToText(item);
        return text ? <MathText key={index} text={text} /> : null;
      })}
    </>
  );
}
