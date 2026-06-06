/**
 * Intent tests for selected Slot actions.
 *
 * Manual editing must be discoverable as an explicit action instead of relying
 * on direct manipulation of the printable paper canvas.
 *
 * @module questionActionRailTests
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { QuestionActionRail } from './question-action-rail.component';

describe('QuestionActionRail', () => {
  it('exposes the focused question editor as an explicit action', () => {
    const html = renderToStaticMarkup(
      <QuestionActionRail
        locked={false}
        onEdit={() => undefined}
        onInfo={() => undefined}
        onAlternatives={() => undefined}
        onToggleLock={() => undefined}
        onAsk={() => undefined}
      />,
    );

    expect(html).toContain('aria-label="Edit question"');
    expect(html).toContain('Edit');
  });
});
