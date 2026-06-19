import { describe, expect, it } from 'vitest';
import { generatedPaperEditorPath } from './editor-routes';

describe('editor routes', () => {
  it('opens the persisted generated paper in the editor', () => {
    expect(generatedPaperEditorPath('paper_42')).toBe('/editor/paper_42');
  });
});
