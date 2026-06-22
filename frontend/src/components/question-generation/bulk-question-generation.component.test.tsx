import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { GeneratedQuestionCandidate, GenerationBatch } from '@/types';
import {
  BulkQuestionGenerationSetup,
  GenerationProgressWorkspace,
} from './bulk-question-generation.component';

const chapters = [
  { id: 1, slug: 'life-processes', name: 'Life Processes', order: 5 },
  { id: 2, slug: 'electricity', name: 'Electricity', order: 12 },
];

function setupProps(overrides = {}) {
  return {
    chapters,
    chaptersLoading: false,
    chaptersError: '',
    selectedSlugs: new Set(['life-processes']),
    topicNamesByChapter: { 'life-processes': 'Nutrition' },
    difficulty: 'Standard' as const,
    busy: false,
    error: '',
    onToggleChapter: vi.fn(),
    onSelectAllChapters: vi.fn(),
    onClearChapters: vi.fn(),
    onTopicNamesChange: vi.fn(),
    onDifficultyChange: vi.fn(),
    onStart: vi.fn(),
    ...overrides,
  };
}

describe('BulkQuestionGenerationSetup', () => {
  it('shows the separate Question bank action controls without backend-owned knobs', () => {
    const html = renderToStaticMarkup(
      <BulkQuestionGenerationSetup {...setupProps()} />,
    );

    expect(html).toContain('Generation setup');
    expect(html).toContain('Select all Chapters');
    expect(html).toContain('Clear selection');
    expect(html).toContain('Optional Topic hints for Life Processes');
    expect(html).toContain('Easy');
    expect(html).toContain('Standard');
    expect(html).toContain('Challenging');
    expect(html).not.toMatch(/batch size|provider|model|fallback|cost|marks distribution/i);
  });

  it('prevents generation until at least one Chapter is selected', () => {
    const html = renderToStaticMarkup(
      <BulkQuestionGenerationSetup {...setupProps({ selectedSlugs: new Set() })} />,
    );

    expect(html).toContain('Select at least one Chapter to enable generation.');
    expect(html).toContain('disabled=""');
  });

  it('shows Chapter loading and error states', () => {
    const loadingHtml = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        {...setupProps({ chapters: [], chaptersLoading: true })}
      />,
    );
    const errorHtml = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        {...setupProps({
          chapters: [],
          chaptersError: 'Request failed (500)',
          selectedSlugs: new Set(),
        })}
      />,
    );

    expect(loadingHtml).toContain('Loading Chapters…');
    expect(errorHtml).toContain('Chapters could not be loaded.');
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

  const candidates: GeneratedQuestionCandidate[] = [
    {
      id: 1,
      status: 'ready_for_review',
      payload: {
        chapter_slug: 'life-processes',
        qtype: 'mcq',
        marks: 1,
        raw_text: 'Which process releases energy from glucose?',
        answer: 'A. Respiration',
        topic_names: ['Respiration'],
        source: { citation: 'NCERT p. 84' },
      },
      question_id: null,
      accepted_at: null,
      created_at: '2026-06-21T00:00:00Z',
      updated_at: '2026-06-21T00:00:00Z',
    },
  ];

  function progressProps(overrides = {}) {
    return {
      batch: baseBatch,
      loading: false,
      error: '',
      lastCheckedAt: '2026-06-21T00:00:03Z',
      pollIntervalMs: 3000,
      candidates: [],
      candidatesLoading: false,
      candidatesError: '',
      onRunInBackground: vi.fn(),
      onTryAgain: vi.fn(),
      onRetryCandidates: vi.fn(),
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

  it('renders ready-for-review candidates with visible answers and counts', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: { ...baseBatch, status: 'ready_for_review', candidate_count: 1 },
          candidates,
        })}
      />,
    );

    expect(html).toContain('Review generated Q&amp;A');
    expect(html).toContain('1</span> accepted');
    expect(html).toContain('0</span> rejected');
    expect(html).toContain('Which process releases energy from glucose?');
    expect(html).toContain('A. Respiration');
    expect(html).toContain('Respiration');
    expect(html).toContain('Grounding / citation context');
    expect(html).toContain('NCERT p. 84');
    expect(html).toContain('Reject');
    expect(html).not.toContain('Run in background');
  });

  it('shows candidate loading, empty, and error states', () => {
    const loadingHtml = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: { ...baseBatch, status: 'ready_for_review', candidate_count: 1 },
          candidatesLoading: true,
        })}
      />,
    );
    const errorHtml = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: { ...baseBatch, status: 'ready_for_review', candidate_count: 1 },
          candidatesError: 'Request failed (500)',
        })}
      />,
    );
    const emptyHtml = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: { ...baseBatch, status: 'ready_for_review', candidate_count: 1 },
        })}
      />,
    );

    expect(loadingHtml).toContain('Loading generated candidates…');
    expect(errorHtml).toContain('Candidates could not be loaded.');
    expect(errorHtml).toContain('Try loading candidates again');
    expect(emptyHtml).toContain('no generated candidates were returned');
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
