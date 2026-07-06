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

  it('typesets upload answer formulas that use slash-parenthesis delimiters', () => {
    const html = renderToStaticMarkup(
      <MathText
        text={String.raw`Power \(P = 1\text{ kW} = 1000\text{ W}\) and voltage \(V = 220\text{ V}\). Current \(I = \frac{P}{V}\).`}
      />,
    );

    expect(html).toContain('class="katex"');
    expect(html).toContain('1000');
    expect(html).toContain('<mfrac>');
    expect(html).not.toContain('\\(P =');
  });

  it('normalizes double-escaped extracted LaTeX commands before KaTeX render', () => {
    const html = renderToStaticMarkup(
      <MathText
        text={String.raw`Study $\\text{CuSO}_4 + \\text{Mg} \\longrightarrow$ products.`}
      />,
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

  it('keeps spaces around inline math in prose latex paragraphs', () => {
    const items: ContentItem[] = [
      {
        type: 'paragraph',
        latex:
          '\\text{Deduce the }F_2\\text{ phenotypic ratio / }F_2\\text{ ratio showing external look.}',
      },
    ];

    const html = renderToStaticMarkup(<MathContent items={items} />);

    expect(html).toContain('Deduce the ');
    expect(html).toContain(' phenotypic ratio / ');
    expect(html).toContain(' ratio showing external look.');
    expect(html).not.toContain('Deducethe');
  });

  it('typesets a paragraph that carries both text and math-bearing latex', () => {
    const items: ContentItem[] = [
      {
        type: 'paragraph',
        text: 'the refractive index is \\sqrt{3}.',
        latex: '\\text{the refractive index is } \\sqrt{3}.',
      },
    ];

    const html = renderToStaticMarkup(<MathContent items={items} />);

    // Typeset via KaTeX (the square root becomes an <msqrt>) rather than
    // dumping the sentence as a plain text node with the raw `\sqrt{3}` source.
    expect(html).toContain('class="katex"');
    expect(html).toContain('<msqrt>');
  });

  it('keeps prose plain when latex is only a \\text wrapper', () => {
    const items: ContentItem[] = [
      {
        type: 'paragraph',
        text: 'By eating the bread on which it is growing.',
        latex: '\\text{By eating the bread on which it is growing.}',
      },
    ];

    const html = renderToStaticMarkup(<MathContent items={items} />);

    expect(html).toContain('By eating the bread on which it is growing.');
    expect(html).not.toContain('class="katex"');
  });

  it('typesets a chemistry equation without shattering \\text symbols', () => {
    // `\text{}` here marks upright element symbols, not prose — and `\xrightarrow`
    // carries a nested `\text{}`. None of it must be split into KaTeX errors.
    const items: ContentItem[] = [
      {
        type: 'paragraph',
        text: 'CO2 + O2 + H2O -> C6H12O6 + H2O',
        latex:
          '\\text{CO}_2 + \\text{O}_2 + \\text{H}_2\\text{O} ' +
          '\\xrightarrow{\\text{Chlorophyll}} ' +
          '\\text{C}_6\\text{H}_{12}\\text{O}_6 + \\text{H}_2\\text{O}',
      },
    ];

    const html = renderToStaticMarkup(<MathContent items={items} />);

    expect(html).toContain('class="katex"');
    // KaTeX only emits this class when it renders its red parse-error fallback.
    expect(html).not.toContain('katex-error');
  });

  it('renders an equation with a labelled arrow whole, not as literal command text', () => {
    // `\xrightarrow[…]{…}` hides `\text{}` inside a macro arg the splitter can't
    // see through; the whole latex must render, never leaking `\xrightarrow`.
    const items: ContentItem[] = [
      {
        type: 'equation',
        latex:
          '6\\text{CO}_2 + 6\\text{H}_2\\text{O} ' +
          '\\xrightarrow[\\text{Sunlight}]{\\text{Chlorophyll}} ' +
          '\\text{C}_6\\text{H}_{12}\\text{O}_6 + \\text{O}_2',
      },
    ];

    const html = renderToStaticMarkup(<MathContent items={items} />);

    expect(html).toContain('class="katex"');
    expect(html).not.toContain('katex-error');
    // KaTeX renders `\xrightarrow` as an `x-arrow` span; if the split had leaked
    // the raw command as text, this class would be absent.
    expect(html).toContain('x-arrow');
  });

  it('renders unparseable latex as plain text, never a red katex error', () => {
    const items: ContentItem[] = [
      { type: 'equation', latex: '\\xrightarrow{' },
    ];

    const html = renderToStaticMarkup(<MathContent items={items} />);

    expect(html).not.toContain('katex-error');
    expect(html).toContain('\\xrightarrow{');
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
