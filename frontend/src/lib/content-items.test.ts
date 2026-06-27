import { describe, expect, it } from 'vitest';
import { contentItemsToPlainText } from './content-items';

describe('contentItemsToPlainText', () => {
  it('flattens non-image content items and skips image placeholders by default', () => {
    expect(
      contentItemsToPlainText([
        { type: 'paragraph', text: 'First sentence.' },
        { type: 'equation', latex: 'H_2O' },
        { type: 'table', rows: [['Metal', 'Reaction']] },
        {
          type: 'image_placeholder',
          assetId: 'diagram-1',
          caption: 'Hidden diagram caption.',
        },
      ]),
    ).toBe('First sentence. H_2O Metal Reaction');
  });

  it('can include image placeholders for renderers that want captions', () => {
    expect(
      contentItemsToPlainText(
        [{ type: 'image_placeholder', caption: 'Carbon structure' }],
        { includeImages: true },
      ),
    ).toBe('[Diagram: Carbon structure]');
  });
});
