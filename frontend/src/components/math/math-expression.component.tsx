/**
 * Renders a LaTeX expression with KaTeX.
 *
 * Content items in PaperDocumentV1 carry math in a dedicated `latex` field
 * (e.g. chemical equations like `\text{C}_6\text{H}_{12}\text{O}_6`). Rendering
 * that string verbatim leaks raw LaTeX into the paper; this component turns it
 * into typeset math instead.
 *
 * Source is normalised first (see `normalizeLatex` — collapses JSON/Markdown
 * double-escaped commands). Malformed source (e.g. an OCR-mangled equation)
 * must not render as KaTeX's red error text in a teacher-facing paper, so we
 * parse with `throwOnError: true` and, on failure, fall back to showing the
 * source as plain text — readable and unobtrusive, still signalling bad data
 * without shouting in red.
 *
 * @module MathExpression
 */
import { useMemo } from 'react';
import katex from 'katex';
import { normalizeLatex } from './latex';

export interface MathExpressionProps {
  latex: string;
  /** Block math is centred on its own line; inline flows with surrounding text. */
  display?: boolean;
  className?: string;
}

export function MathExpression({
  latex,
  display = true,
  className,
}: MathExpressionProps) {
  const normalizedLatex = normalizeLatex(latex);
  const html = useMemo(() => {
    try {
      return katex.renderToString(normalizedLatex, {
        displayMode: display,
        throwOnError: true,
      });
    } catch {
      return null;
    }
  }, [normalizedLatex, display]);

  if (html === null) {
    // Unparseable LaTeX: show the source as plain text, not KaTeX red.
    return <span className={className}>{normalizedLatex}</span>;
  }

  return (
    <span
      className={className}
      // KaTeX output is generated from our own content, not user free text.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
