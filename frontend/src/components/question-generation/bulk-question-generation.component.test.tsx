import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { GenerationBatch } from '@/types';
import {
  BulkQuestionGenerationSetup,
  GenerationProgressWorkspace,
} from './bulk-question-generation.component';

const chapters = [
  { id: 1, slug: 'life-processes', name: 'Life Processes', order: 5 },
  { id: 2, slug: 'electricity', name: 'Electricity', order: 12 },
];

describe('BulkQuestionGenerationSetup', () => {
  it('shows the separate Question bank action controls without backend-owned knobs', () => {
    const html = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        chapters={chapters}
        selectedSlugs={new Set(['life-processes'])}
        topicNamesByChapter={{ 'life-processes': 'Nutrition' }}
        difficulty="Standard"
        busy={false}
        error=""
        onToggleChapter={vi.fn()}
        onSelectAllChapters={vi.fn()}
        onTopicNamesChange={vi.fn()}
        onDifficultyChange={vi.fn()}
        onStart={vi.fn()}
      />,
    );

    expect(html).toContain('Generate Question bank');
    expect(html).toContain('Select all Chapters');
    expect(html).toContain('Optional Topics under Life Processes');
    expect(html).toContain('Easy');
    expect(html).toContain('Standard');
    expect(html).toContain('Challenging');
    expect(html).not.toMatch(/batch size|provider|model|fallback|cost|marks distribution/i);
  });
});

describe('GenerationProgressWorkspace', () => {
  const baseBatch: GenerationBatch = {
    id: 144,
    status: 'generating_questions',
    chapter_slugs: ['life-processes'],
    topic_names: [],
    difficulty_preset: 'balanced',
    requested_count: 10,
    candidate_count: 0,
    error: '',
    ready_at: null,
    accepted_at: null,
    expired_at: null,
    created_at: '2026-06-21T00:00:00Z',
    updated_at: '2026-06-21T00:00:00Z',
  };

  it('shows polling stages and background navigation without percentages', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        batch={baseBatch}
        loading={false}
        error=""
        onRunInBackground={vi.fn()}
        onTryAgain={vi.fn()}
        onBackToPaperSetup={vi.fn()}
      />,
    );

    expect(html).toContain('Generating Questions');
    expect(html).toContain('Run in background');
    expect(html).not.toContain('%');
  });

  it('replaces progress with the review entry point when ready', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        batch={{ ...baseBatch, status: 'ready_for_review', candidate_count: 3 }}
        loading={false}
        error=""
        onRunInBackground={vi.fn()}
        onTryAgain={vi.fn()}
        onBackToPaperSetup={vi.fn()}
      />,
    );

    expect(html).toContain('Ready for review');
    expect(html).toContain('Review generated Questions');
    expect(html).not.toContain('Run in background');
  });

  it('shows the no-valid-Questions failure actions', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        batch={{ ...baseBatch, status: 'failed' }}
        loading={false}
        error=""
        onRunInBackground={vi.fn()}
        onTryAgain={vi.fn()}
        onBackToPaperSetup={vi.fn()}
      />,
    );

    expect(html).toContain(
      'AI generation did not produce any Questions and answers. Try again later.',
    );
    expect(html).toContain('Try again');
    expect(html).toContain('Back to paper setup');
  });
});
