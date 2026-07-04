/**
 * Renders a paragraph's `latex` string as mixed prose + typeset math.
 *
 * `\text{…}` groups render as normal, line-wrappable text; the math between
 * them is typeset inline with KaTeX. This keeps long sentences (e.g. a stem
 * ending in `\sqrt{3}`) wrapping naturally instead of overflowing as one
 * unbreakable KaTeX box.
 *
 * Splitting is only safe when every math segment parses on its own. Some latex
 * puts `\text{…}` inside a macro argument the splitter can't see through (e.g.
 * `\xrightarrow[\text{Sunlight}]{\text{Chlorophyll}}`), which would carve the
 * macro into invalid fragments. When any segment fails to parse, we abandon the
 * split and render the whole `latex` as one expression — correct for equations,
 * and `MathExpression` itself falls back to plain text if the whole is broken.
 *
 * @module LatexText
 */
import { Fragment, useMemo } from 'react';
import { latexParses, parseLatexSegments } from './latex';
import { MathExpression } from './math-expression.component';

export function LatexText({ latex }: { latex: string }) {
  const segments = useMemo(() => {
    const parsed = parseLatexSegments(latex);
    const everyMathParses = parsed.every(
      (segment) => segment.kind === 'text' || latexParses(segment.value),
    );
    return everyMathParses ? parsed : null;
  }, [latex]);

  if (segments === null) {
    return <MathExpression latex={latex} display={false} />;
  }

  return (
    <>
      {segments.map((segment, index) =>
        segment.kind === 'text' ? (
          <Fragment key={index}>{segment.value}</Fragment>
        ) : (
          <MathExpression key={index} latex={segment.value} display={false} />
        ),
      )}
    </>
  );
}
