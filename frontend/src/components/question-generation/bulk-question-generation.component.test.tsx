import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { ChapterTopicNode, GenerationBatch } from '@/types';
import {
  BulkQuestionGenerationSetup,
  GenerationProgressWorkspace,
} from './bulk-question-generation.component';

const chapters = [
  { id: 1, slug: 'life-processes', name: 'Life Processes', order: 5 },
  { id: 2, slug: 'electricity', name: 'Electricity', order: 12 },
];

const topics: ChapterTopicNode[] = [
  {
    id: 'life-processes:5.1',
    type: 'section',
    title: '5.1 Life Processes',
    parent_id: null,
    source_element_id: 'element-1',
    source_range: { start: 1, end: 8 },
    page_range: { start: 81, end: 83 },
    element_count: 8,
    preview: 'Nutrition and respiration in living organisms.',
  },
  {
    id: 'life-processes:activity-5.1',
    type: 'activity',
    title: 'Activity 5.1',
    parent_id: 'life-processes:5.1',
    source_element_id: 'element-4',
    source_range: { start: 4, end: 6 },
    page_range: { start: 82, end: 82 },
    element_count: 3,
    preview: 'Observe the experiment.',
  },
];

function setupProps(overrides = {}) {
  return {
    chapters,
    chaptersLoading: false,
    chaptersError: '',
    selectedChapterSlug: 'life-processes',
    topics,
    topicsLoading: false,
    topicsError: '',
    selectedTopicIds: new Set(['life-processes:5.1']),
    difficulty: 'Standard' as const,
    busy: false,
    error: '',
    onSelectChapter: vi.fn(),
    onToggleTopic: vi.fn(),
    onClearTopics: vi.fn(),
    onDifficultyChange: vi.fn(),
    onStart: vi.fn(),
    ...overrides,
  };
}

describe('BulkQuestionGenerationSetup', () => {
  it('shows the separate topic-scoped Q&A controls without backend-owned knobs', () => {
    const html = renderToStaticMarkup(
      <BulkQuestionGenerationSetup {...setupProps()} />,
    );

    expect(html).toContain('Generate AI Q&amp;A');
    expect(html).toContain('NCERT Chapter');
    expect(html).toContain('Topic scope');
    expect(html).toContain('5.1 Life Processes');
    expect(html).toContain('Section · pp. 81–83');
    expect(html).toContain('Generated Q&amp;A stays separate from the Question bank');
    expect(html).toContain('Easy');
    expect(html).toContain('Standard');
    expect(html).toContain('Challenging');
    expect(html).not.toMatch(/batch size|provider|model|fallback|cost|marks distribution|prompt|instructions|topic hints/i);
  });

  it('prevents generation until at least one topic is selected', () => {
    const html = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        {...setupProps({ selectedTopicIds: new Set() })}
      />,
    );

    expect(html).toContain('Select at least one NCERT topic to enable generation.');
    expect(html).toContain('disabled=""');
  });

  it('explains that the MVP is one Chapter per generation run', () => {
    const html = renderToStaticMarkup(
      <BulkQuestionGenerationSetup {...setupProps()} />,
    );

    expect(html).toContain('The MVP supports one Chapter per run');
    expect(html).toContain('type="radio"');
  });

  it('shows Chapter and topic loading and error states', () => {
    const loadingHtml = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        {...setupProps({ chapters: [], chaptersLoading: true })}
      />,
    );
    const chapterErrorHtml = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        {...setupProps({
          chapters: [],
          chaptersError: 'Request failed (500)',
          selectedChapterSlug: '',
        })}
      />,
    );
    const topicsErrorHtml = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        {...setupProps({ topics: [], topicsError: 'Request failed (500)' })}
      />,
    );

    expect(loadingHtml).toContain('Loading Chapters…');
    expect(chapterErrorHtml).toContain('Chapters could not be loaded.');
    expect(topicsErrorHtml).toContain('Topics could not be loaded.');
  });
});

describe('GenerationProgressWorkspace', () => {
  const baseBatch: GenerationBatch = {
    id: 144,
    status: 'generating_questions',
    chapter_slugs: ['life-processes'],
    chapter_map_node_ids: ['life-processes:5.1'],
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

  function progressProps(overrides = {}) {
    return {
      batch: baseBatch,
      loading: false,
      error: '',
      lastCheckedAt: '2026-06-21T00:00:03Z',
      pollIntervalMs: 3000,
      onRunInBackground: vi.fn(),
      onTryAgain: vi.fn(),
      onBackToPaperSetup: vi.fn(),
      ...overrides,
    };
  }

  it('shows polling stages and background navigation without percentages', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace {...progressProps()} />,
    );

    expect(html).toContain('Generating Questions');
    expect(html).toContain('Checking every 3 seconds');
    expect(html).toContain('Run in background');
    expect(html).not.toContain('%');
  });

  it('shows a disabled review entry point when ready', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: { ...baseBatch, status: 'ready_for_review', candidate_count: 3 },
        })}
      />,
    );

    expect(html).toContain('Ready for review');
    expect(html).toContain('Review generated Questions');
    expect(html).toContain('Review workspace is not connected in this release yet.');
    expect(html).toContain('disabled=""');
    expect(html).not.toContain('Run in background');
  });

  it('shows a recoverable load error when no batch is available', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({ batch: null, error: 'Request failed (500)' })}
      />,
    );

    expect(html).toContain('We could not load this generation job.');
    expect(html).toContain('Try again');
    expect(html).toContain('Back to paper setup');
  });

  it('shows the no-valid-Questions failure actions', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({ batch: { ...baseBatch, status: 'failed' } })}
      />,
    );

    expect(html).toContain('No valid Questions were produced');
    expect(html).toContain('Try again');
    expect(html).toContain('Back to paper setup');
  });
});
