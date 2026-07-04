import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type {
  ChapterTopicNode,
  GeneratedQuestionCandidate,
  GenerationBatch,
} from '@/types';
import {
  BulkQuestionGenerationSetup,
  GenerationProgressWorkspace,
} from './bulk-question-generation.component';

const chapters = [
  {
    id: 4,
    slug: 'carbon-and-its-compounds',
    name: 'Carbon and its Compounds',
    order: 4,
  },
];

const topics: ChapterTopicNode[] = [
  {
    id: 'life-processes:5.1',
    type: 'section',
    title: '5.1 LIFE PROCESSES',
    parent_id: null,
    source_element_id: 'element-1',
    source_range: { start: 1, end: 8 },
    page_range: { start: 81, end: 83 },
    element_count: 8,
    preview: 'Nutrition and respiration in living organisms.',
  },
  {
    id: 'life-processes:activity-5.1',
    type: 'section',
    title: '5.2 Nutrition',
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
    busy: false,
    error: '',
    onSelectChapter: vi.fn(),
    onToggleTopic: vi.fn(),
    onClearTopics: vi.fn(),
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
    expect(html).toContain('Topics');
    expect(html).toContain('5.1 Life Processes');
    expect(html).toContain('pp. 81–83');
    expect(html).not.toContain('Difficulty');
    expect(html).not.toContain('Easy');
    expect(html).not.toContain('Standard');
    expect(html).not.toContain('Challenging');
    expect(html).not.toContain(
      'Selected NCERT topics define the generation scope',
    );
    expect(html).not.toContain(
      'Generated Q&amp;A stays separate from the Question bank',
    );
    expect(html).not.toMatch(
      /batch size|provider|model|fallback|cost|marks distribution|prompt|instructions|topic hints/i,
    );
  });

  it('prevents generation until at least one topic is selected', () => {
    const html = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        {...setupProps({ selectedTopicIds: new Set() })}
      />,
    );

    expect(html).toContain('Select at least one topic.');
    expect(html).toContain('disabled=""');
  });

  it('waits for a Chapter selection before showing topics', () => {
    const html = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        {...setupProps({
          selectedChapterSlug: '',
          selectedTopicIds: new Set(),
        })}
      />,
    );

    expect(html).toContain('Select Chapter 4 to show topics.');
    expect(html).not.toContain('5.1 Life Processes');
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

  it('links to in-progress and ready generation drafts from setup', () => {
    const html = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        {...setupProps({
          batches: [
            {
              id: 41,
              status: 'generating_questions',
              chapter_slugs: ['carbon-and-its-compounds'],
              chapter_map_node_ids: ['carbon:4.1'],
              topic_names: [],
              difficulty_preset: 'balanced',
              requested_count: 10,
              candidate_count: 0,
              error: '',
              ready_at: null,
              accepted_at: null,
              expired_at: null,
              discarded_at: null,
              created_at: '2026-06-21T00:00:00Z',
              updated_at: '2026-06-21T00:00:00Z',
            },
            {
              id: 42,
              status: 'ready_for_review',
              chapter_slugs: ['carbon-and-its-compounds'],
              chapter_map_node_ids: ['carbon:4.2'],
              topic_names: [],
              difficulty_preset: 'balanced',
              requested_count: 10,
              candidate_count: 3,
              error: '',
              ready_at: '2026-06-21T00:00:03Z',
              accepted_at: null,
              expired_at: null,
              discarded_at: null,
              created_at: '2026-06-21T00:00:00Z',
              updated_at: '2026-06-21T00:00:03Z',
            },
          ],
          onOpenBatch: vi.fn(),
        })}
      />,
    );

    expect(html).toContain('Generation drafts');
    expect(html).toContain('Batch #41 · Generating');
    expect(html).toContain('View progress');
    expect(html).toContain('Batch #42 · Ready for review');
    expect(html).toContain('3 candidates ready');
    expect(html).toContain('Review draft');
  });

  it('shows a friendly active-batch message when Q&A is already generating', () => {
    const html = renderToStaticMarkup(
      <BulkQuestionGenerationSetup
        {...setupProps({
          activeBatchId: 1,
          error: 'Questions are already being generated.',
          onOpenActiveBatch: vi.fn(),
        })}
      />,
    );

    expect(html).toContain('Q&amp;A generation is already running.');
    expect(html).toContain('Batch #1 is preparing questions now.');
    expect(html).toContain('View progress');
    expect(html).not.toContain('Teacher already has active generation batch');
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
    discarded_at: null,
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
        content: {
          options: [
            { label: 'A', content: [{ text: 'Respiration' }] },
            { label: 'B', content: [{ text: 'Photosynthesis' }] },
            { label: 'C', content: [{ text: 'Transpiration' }] },
            { label: 'D', content: [{ text: 'Osmosis' }] },
          ],
        },
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
      accepting: false,
      acceptError: '',
      onRunInBackground: vi.fn(),
      onTryAgain: vi.fn(),
      onAcceptCandidates: vi.fn(),
      onRetryCandidates: vi.fn(),
      onBackToPaperSetup: vi.fn(),
      ...overrides,
    };
  }

  it('shows a lean teacher-facing progress state without backend details', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace {...progressProps()} />,
    );

    expect(html).toContain('Drafting Q&amp;A');
    expect(html).toContain(
      'Questions are being drafted from the selected topics.',
    );
    expect(html).toContain('Preparing');
    expect(html).toContain('Drafting');
    expect(html).toContain('Review');
    expect(html).toContain('Q&amp;A generation is in progress');
    expect(html).toContain(
      'This will update automatically when review is ready.',
    );
    expect(html).toContain('Back to setup');
    expect(html).not.toContain('Backend requested');
    expect(html).not.toContain('Validation may reduce');
    expect(html).not.toContain('Checking every');
    expect(html).not.toContain('Last checked');
    expect(html).not.toContain('%');
  });

  it('renders ready-for-review candidates with visible answers and counts', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: {
            ...baseBatch,
            status: 'ready_for_review',
            candidate_count: 1,
          },
          candidates,
        })}
      />,
    );

    expect(html).toContain('Review generated Q&amp;A');
    expect(html).toContain('Ready to review');
    expect(html).not.toContain('Q&amp;A generation is in progress');
    expect(html).toContain(
      '1 candidate passed validation and is shown for teacher review',
    );
    expect(html).toContain('1</span> accepted');
    expect(html).toContain('0</span> rejected');
    expect(html).toContain('Which process releases energy from glucose?');
    expect(html).toContain('A.');
    expect(html).toContain('Respiration');
    expect(html).toContain('B.');
    expect(html).toContain('Photosynthesis');
    expect(html).toContain('A. Respiration');
    expect(html).toContain('Respiration');
    expect(html).not.toContain('Grounding / citation context');
    expect(html).not.toContain('NCERT p. 84');
    expect(html).toContain('Reject');
    expect(html).toContain('Import accepted Q&amp;A');
    expect(html).toMatch(
      /<button(?![^>]*disabled="")[^>]*>Import accepted Q&amp;A<\/button>/,
    );
    expect(html).not.toContain('Run in background');
  });

  it('disables final import when every candidate is rejected', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: {
            ...baseBatch,
            status: 'ready_for_review',
            candidate_count: 1,
          },
          candidates,
          initialRejectedCandidateIds: [1],
        })}
      />,
    );

    expect(html).toContain('0</span> accepted');
    expect(html).toContain('1</span> rejected');
    expect(html).toContain('Restore at least one candidate');
    expect(html).toMatch(
      /<button[^>]*disabled=""[^>]*>Import accepted Q&amp;A<\/button>/,
    );
  });

  it('shows a recoverable final import API error', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: {
            ...baseBatch,
            status: 'ready_for_review',
            candidate_count: 1,
          },
          candidates,
          acceptError: 'Request failed (409)',
        })}
      />,
    );

    expect(html).toContain('Import failed.');
    expect(html).toContain('Request failed (409)');
    expect(html).toContain('Import accepted Q&amp;A');
  });

  it('shows completed state after the batch is accepted', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({ batch: { ...baseBatch, status: 'accepted' } })}
      />,
    );

    expect(html).toContain('Generation batch accepted');
    expect(html).toContain(
      'Accepted generated Q&amp;A entered the Question bank',
    );
    expect(html).toContain('Rejected candidates were not imported');
    expect(html).toContain('Back to paper setup');
  });

  it('offers "Discard & generate another" on a review-ready batch', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: {
            ...baseBatch,
            status: 'ready_for_review',
            candidate_count: 2,
          },
          onGenerateAnother: vi.fn(),
        })}
      />,
    );

    expect(html).toContain('Discard &amp; generate another');
  });

  it('labels the regenerate action plainly on a settled (accepted) batch', () => {
    const html = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: { ...baseBatch, status: 'accepted' },
          onGenerateAnother: vi.fn(),
        })}
      />,
    );

    expect(html).toContain('Generate another batch');
  });

  it('shows candidate loading, empty, and error states', () => {
    const loadingHtml = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: {
            ...baseBatch,
            status: 'ready_for_review',
            candidate_count: 1,
          },
          candidatesLoading: true,
        })}
      />,
    );
    const errorHtml = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: {
            ...baseBatch,
            status: 'ready_for_review',
            candidate_count: 1,
          },
          candidatesError: 'Request failed (500)',
        })}
      />,
    );
    const emptyHtml = renderToStaticMarkup(
      <GenerationProgressWorkspace
        {...progressProps({
          batch: {
            ...baseBatch,
            status: 'ready_for_review',
            candidate_count: 1,
          },
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
