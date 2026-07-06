/**
 * Regression tests for browser-PDF print CSS.
 *
 * The backend downloads use Chromium against the React print route, so these
 * styles are part of the PDF contract: page counters must not be hardcoded and
 * wide KaTeX formulae must be constrained to the paper column.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(here, 'index.css'), 'utf8');

describe('print paper CSS', () => {
  it('uses paged-media counters for the repeated paper footer', () => {
    expect(css).toContain('.paper-page-number::after');
    expect(css).toContain('counter(page)');
  });

  it('constrains KaTeX formulae to the printable paper column', () => {
    expect(css).toContain('.paper-question-body .katex');
    expect(css).toMatch(/max-width:\s*100%/);
    expect(css).toMatch(/overflow-x:\s*auto/);
  });

  it('keeps printed OR and internal-choice spacing under contract', () => {
    expect(css).toContain('.paper-or-divider');
    expect(css).toContain('.paper-choice-group');
    expect(cssRules('.paper-choice-group')).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/\bgap\s*:\s*8pt\b/),
        expect.stringMatching(/\bmargin-top\s*:\s*7pt\b/),
      ]),
    );
    expect(cssRule('.paper-choice-group strong')).toMatch(
      /\btext-align\s*:\s*center\b/,
    );
  });
});

function cssRule(selector: string) {
  const rules = cssRules(selector);

  expect(rules, `Missing CSS rule for ${selector}`).not.toHaveLength(0);
  return rules[0] ?? '';
}

function cssRules(selector: string) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return Array.from(
    css.matchAll(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`, 'g')),
  ).map((match) => match[1]);
}
