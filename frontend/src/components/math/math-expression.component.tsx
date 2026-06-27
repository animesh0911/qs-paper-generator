/**
 * Renders a LaTeX expression with KaTeX.
 *
 * Content items in PaperDocumentV1 carry math in a dedicated `latex` field
 * (e.g. chemical equations like `\text{C}_6\text{H}_{12}\text{O}_6`). Rendering
 * that string verbatim leaks raw LaTeX into the paper; this component turns it
 * into typeset math instead.
 *
 * `throwOnError: false` keeps malformed source from blanking the page — KaTeX
 * falls back to showing the offending source in red, which is still more useful
 * than a crash and signals bad data to reviewers.
 *
 * @module MathExpression
 */
import { useMemo } from 'react';
import katex from 'katex';

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
  const html = useMemo(
    () =>
      katex.renderToString(latex, {
        displayMode: display,
        throwOnError: false,
      }),
    [latex, display],
  );

  return (
    <span
      className={className}
      // KaTeX output is generated from our own content, not user free text.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
