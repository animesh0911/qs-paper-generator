/**
 * Decide whether a content item's `latex` field carries real math worth
 * typesetting, versus being a plain-prose wrapper.
 *
 * The ingestor emits a paragraph's `latex` as the full typeset version of the
 * text — often the whole sentence wrapped in `\text{…}` with the actual math
 * spliced in (e.g. `\text{… index is } \sqrt{3}.`). When a paragraph carries
 * both `text` and `latex`, the renderers prefer `text` so labelled prose stays
 * plain; but that drops the math. This helper lets a renderer prefer `latex`
 * only when stripping the `\text{…}` prose leaves behind genuine math.
 *
 * @module latex
 */
import katex from 'katex';

/**
 * Collapse JSON/Markdown double-escaped commands back to normal LaTeX. Some
 * ingestion payloads carry `\\text{CuSO}` as two literal backslashes; KaTeX
 * reads `\\` as a line break, turning valid chemistry into red error output.
 */
export function normalizeLatex(latex: string): string {
  return latex.replace(/\\\\(?=[A-Za-z])/g, '\\');
}

/** True when KaTeX can parse `latex` (after normalisation) without error. */
export function latexParses(latex: string): boolean {
  try {
    katex.renderToString(normalizeLatex(latex), { throwOnError: true });
    return true;
  } catch {
    return false;
  }
}

/** Strip `\text{…}` groups (handling one level of nested braces) and trim. */
function stripTextGroups(latex: string): string {
  let previous: string;
  let current = latex;
  // Repeat until stable: innermost `\text{…}` (no nested braces) removed first,
  // so nested groups collapse from the inside out.
  do {
    previous = current;
    current = current.replace(/\\text\{[^{}]*\}/g, '');
  } while (current !== previous);
  return current;
}

/**
 * True when `latex` contains math beyond plain `\text{…}` prose — i.e. a LaTeX
 * command (`\sqrt`, `\Omega`, `\rightarrow`, …) or sub/superscript markup
 * survives once the prose wrappers are removed.
 */
export function latexHasMath(latex: string | undefined): boolean {
  if (!latex) return false;
  const remainder = stripTextGroups(latex);
  return /\\[a-zA-Z]|[\^_]/.test(remainder);
}

export interface LatexSegment {
  kind: 'text' | 'math';
  value: string;
}

/** Tokens that bind an adjacent `\text{…}` into a math expression. */
const MATH_BINDERS = new Set(['_', '^', '{']);

/** Last non-whitespace character of a string (`''` if none). */
function lastNonSpace(value: string): string {
  for (let i = value.length - 1; i >= 0; i -= 1) {
    if (!/\s/.test(value[i])) return value[i];
  }
  return '';
}

/**
 * Split a paragraph's `latex` into prose and math segments. Top-level `\text{…}`
 * groups that wrap natural-language prose become `text` segments (rendered as
 * normal, line-wrappable HTML); everything else stays a `math` segment
 * (typeset inline with KaTeX).
 *
 * The ingestor emits a whole sentence as one `latex` string — e.g.
 * `\text{… index is } \sqrt{3}.`. Typesetting that wholesale produces a single
 * unbreakable KaTeX box that overflows its column, so we peel off the prose.
 *
 * But `\text{…}` is also KaTeX's own construct for upright symbols — chemistry
 * leans on it (`\text{CO}_2`, `\xrightarrow{\text{Chlorophyll}}`). Peeling those
 * out would shatter a valid equation into malformed fragments. So a `\text{…}`
 * is treated as prose only when it is at brace depth 0 (not an argument to
 * another macro) AND nothing binds to it — no `_`/`^`/`{` immediately before or
 * after. That keeps `\text{CO}_2` (followed by `_`) and `\xrightarrow{\text{…}}`
 * (nested) inside the math run, while still peeling off sentence wrappers.
 */
export function parseLatexSegments(latex: string): LatexSegment[] {
  const segments: LatexSegment[] = [];
  const TEXT_OPEN = '\\text{';
  let mathBuffer = '';
  let index = 0;
  let depth = 0;

  const flushMath = () => {
    if (mathBuffer.trim()) segments.push({ kind: 'math', value: mathBuffer });
    mathBuffer = '';
  };

  while (index < latex.length) {
    if (depth === 0 && latex.startsWith(TEXT_OPEN, index)) {
      // Find the matching close brace for this `\text{…}`.
      let braceDepth = 1;
      let cursor = index + TEXT_OPEN.length;
      const start = cursor;
      while (cursor < latex.length && braceDepth > 0) {
        const char = latex[cursor];
        if (char === '{') braceDepth += 1;
        else if (char === '}') braceDepth -= 1;
        if (braceDepth > 0) cursor += 1;
      }
      const after = latex[cursor + 1] ?? '';
      const bindsBefore = MATH_BINDERS.has(lastNonSpace(mathBuffer));
      const bindsAfter = MATH_BINDERS.has(after);

      if (!bindsBefore && !bindsAfter) {
        // A standalone prose wrapper — peel it off so it can wrap.
        flushMath();
        segments.push({ kind: 'text', value: latex.slice(start, cursor) });
      } else {
        // Bound to surrounding math (e.g. `\text{CO}_2`) — keep it verbatim.
        mathBuffer += latex.slice(index, cursor + 1);
      }
      index = cursor + 1; // skip past the closing brace
    } else {
      const char = latex[index];
      if (char === '{') depth += 1;
      else if (char === '}') depth = Math.max(0, depth - 1);
      mathBuffer += char;
      index += 1;
    }
  }

  flushMath();
  return segments;
}
