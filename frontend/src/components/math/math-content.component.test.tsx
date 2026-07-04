/**
 * Tests for the inline content renderer used by editor preview surfaces.
 *
 * Pins that `latex` content items typeset with KaTeX instead of leaking raw
 * source, while plain text and other item kinds stay as inline text.
 *
 * @module mathContentTests
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { ContentItem } from '@/types';
import { MathContent, MathText } from './math-content.component';

describe('MathText', () => {
  it('typesets dollar-delimited LaTeX embedded in raw extracted text', () => {
    const html = renderToStaticMarkup(
      <MathText text="Consider $$p\,\text{Al} + q\,\text{H}_2\text{O}$$ now." />,
    );

    expect(html).toContain('class="katex-display"');
    expect(html).toContain('Al');
    expect(html).not.toContain('$$');
  });

  it('typesets inline dollar-delimited LaTeX without display math', () => {
    const html = renderToStaticMarkup(
      <MathText text="Study $\text{CuSO}_4 + \text{Mg} \longrightarrow$ products." />,
    );

    expect(html).toContain('class="katex"');
    expect(html).not.toContain('class="katex-display"');
    expect(html).not.toContain('$\text{CuSO}_4');
  });

  it('normalizes double-escaped extracted LaTeX commands before KaTeX render', () => {
    const html = renderToStaticMarkup(
      <MathText text={String.raw`Study $\\text{CuSO}_4 + \\text{Mg} \\longrightarrow$ products.`} />,
    );

    expect(html).toContain('class="katex"');
    expect(html).not.toContain('katex-error');
    expect(html).not.toContain('\\\\text{CuSO}_4');
  });
});

describe('MathContent', () => {
  it('typesets latex items with KaTeX rather than dumping raw source', () => {
    const items: ContentItem[] = [
      {
        type: 'equation',
        latex:
          '\\text{C}_6\\text{H}_{12}\\text{O}_{6(\\text{aq})} + 6\\text{O}_{2(\\text{g})} \\rightarrow 6\\text{CO}_{2(\\text{g})}',
      },
    ];

    const html = renderToStaticMarkup(<MathContent items={items} />);

    expect(html).toContain('class="katex"');
    // Inline math, not block: no centred display wrapper.
    expect(html).not.toContain('class="katex-display"');
  });

  it('renders plain text and falls back for non-math items', () => {
    const items: ContentItem[] = [
      { type: 'paragraph', text: 'Balance the equation:' },
      { type: 'image_placeholder', caption: 'circuit' },
    ];

    const html = renderToStaticMarkup(<MathContent items={items} />);

    expect(html).toContain('Balance the equation:');
    expect(html).toContain('[Diagram: circuit]');
    expect(html).not.toContain('class="katex"');
  });
});
