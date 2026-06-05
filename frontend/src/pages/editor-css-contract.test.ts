/**
 * CSS contract tests for the PaperDocumentV1 editor shell.
 *
 * These tests protect editor affordances that are implemented through CSS
 * rather than the PaperDocument view model. In particular, the question action
 * rail is positioned outside each Slot row, so its containing section must not
 * clip overflow.
 *
 * @module editorCssContractTests
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');
const questionActionRailSource = readFileSync(
  resolve(
    process.cwd(),
    'src/components/editor/question-action-rail.component.tsx',
  ),
  'utf8',
);
const editorPageSource = readFileSync(
  resolve(process.cwd(), 'src/pages/editor.page.tsx'),
  'utf8',
);
const editorInspectorSource = readFileSync(
  resolve(
    process.cwd(),
    'src/components/editor/editor-inspector.component.tsx',
  ),
  'utf8',
);

describe('editor CSS contracts', () => {
  it('keeps section overflow visible so the question action rail is not clipped', () => {
    const sectionRule = cssRule('.editor-paper-section');

    expect(sectionRule).not.toMatch(/\boverflow\s*:/);
    expect(questionActionRailSource).toContain('qpg-question-action-rail');
    expect(questionActionRailSource).toContain('absolute');
    expect(questionActionRailSource).toContain('right-[calc(100%+0.5rem)]');
  });

  it('starts each print section after the first on a fresh PDF page', () => {
    const sectionBreakRule = cssRule('.paper-section + .paper-section');

    expect(sectionBreakRule).toMatch(/\bbreak-before\s*:\s*page\b/);
    expect(sectionBreakRule).toMatch(/\bpage-break-before\s*:\s*always\b/);
  });

  it('keeps the inspector available in the single-column editor layout', () => {
    expect(editorPageSource).not.toContain('[&_.editor-inspector]:hidden');
    expect(editorPageSource).toContain('[&_.editor-inspector]:order-2');
    expect(editorInspectorSource).toContain('max-lg:static');
    expect(editorInspectorSource).toContain('max-lg:h-auto');
  });
});

function cssRule(selector: string) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = css.match(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`));

  expect(match, `Missing CSS rule for ${selector}`).not.toBeNull();
  return match?.[1] ?? '';
}
