/**
 * Tests for the bottom assistant chat scaffold.
 *
 * These pin the result-card contract that the live AI flow (#34) inherits:
 * the assistant advertises that it cannot rewrite sourced question text, action
 * buttons appear only after a result is ready, and Apply stays disabled while
 * no live apply path exists.
 *
 * @module assistantChatTests
 */
import { createRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { AssistantChat } from './assistant-chat.component';
import type { AssistantResult } from '@/hooks/useAssistantChat.hook';

const baseProps = {
  chatValue: '',
  inputRef: createRef<HTMLInputElement>(),
  onChatChange: vi.fn(),
  onApply: vi.fn(),
  onDismiss: vi.fn(),
};

const completeResult: AssistantResult = {
  kind: 'review',
  summary: [
    'Reviewed “Science” — 3 sections, 39 questions, 80 marks.',
    'No structural warnings detected across the sections.',
  ],
  affected: [
    { id: 'section-a', label: 'Section A' },
    { id: 'section-b', label: 'Section B' },
  ],
  canApply: true,
};

describe('AssistantChat', () => {
  it('states that the assistant cannot rewrite sourced question text', () => {
    const html = renderToStaticMarkup(
      <AssistantChat status="idle" result={null} {...baseProps} />,
    );

    expect(html).toContain('explain, review, and suggest');
    expect(html).toContain('can’t rewrite sourced question text');
  });

  it('shows a pending state with no action buttons before the result is ready', () => {
    const html = renderToStaticMarkup(
      <AssistantChat status="pending" result={null} {...baseProps} />,
    );

    expect(html).toContain('Reviewing this paper');
    expect(html).not.toContain('Dismiss');
    expect(html).not.toContain('Apply fix');
  });

  it('renders both summary lines, affected areas, and actions once complete', () => {
    const html = renderToStaticMarkup(
      <AssistantChat
        status="complete"
        result={completeResult}
        {...baseProps}
      />,
    );

    expect(html).toContain('39 questions, 80 marks');
    expect(html).toContain('No structural warnings detected');
    expect(html).toContain('Section A');
    expect(html).toContain('Section B');
    expect(html).toContain('Dismiss');
    // Apply is present as a slot for #34 but disabled while no live apply exists.
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>\s*Apply fix/);
  });
});
