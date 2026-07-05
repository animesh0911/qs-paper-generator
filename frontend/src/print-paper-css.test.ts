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
});
