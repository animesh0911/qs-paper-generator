/**
 * API adapter tests.
 *
 * These tests cover local-development behavior around auth. The backend remains
 * the source of truth in normal runs, but the editor shell can still be opened
 * when host-side Vite is running without the Docker backend.
 *
 * @module apiTests
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mockPaperDocumentV1 } from '@/mocks';
import {
  acceptGenerationCandidates,
  approvePaper,
  assemblePaper,
  clearToken,
  createGenerationBatch,
  fetchGenerationBatch,
  fetchGenerationCandidates,
  fetchPaperFormats,
  fetchPaperDocument,
  getToken,
  login,
  persistDraft,
} from './api';

const storage = new Map<string, string>();

beforeEach(() => {
  storage.clear();
  vi.restoreAllMocks();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
  });
});

describe('paper formats', () => {
  it('loads backend-owned formats for the generation form', async () => {
    const formats = [
      {
        format_id: 'cbse_science_class_10_board_compact_2026_v1',
        name: 'CBSE End Term Exam',
      },
    ];
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(formats)));
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchPaperFormats()).resolves.toEqual(formats);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/formats',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('sends the selected format as the only paper-layout choice', async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify(mockPaperDocumentV1)),
    );
    vi.stubGlobal('fetch', fetchMock);

    await assemblePaper({
      format_id: 'cbse_science_class_10_board_compact_2026_v1',
      difficulty: 'standard',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/assemble',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          format_id: 'cbse_science_class_10_board_compact_2026_v1',
          difficulty: 'standard',
        }),
      }),
    );
  });
});

describe('generation batches', () => {
  it('creates and polls bulk Question generation batches through the backend API', async () => {
    const batch = {
      id: 144,
      status: 'queued',
      chapter_slugs: ['life-processes'],
      topic_names: ['Nutrition'],
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
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(batch)));
    vi.stubGlobal('fetch', fetchMock);

    await createGenerationBatch({
      chapter_slugs: ['life-processes'],
      topic_names: ['Nutrition'],
      difficulty_preset: 'balanced',
    });
    await fetchGenerationBatch(144);
    await fetchGenerationCandidates(144);
    await acceptGenerationCandidates(144, [1, 3]);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/bank/generation-batches/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          chapter_slugs: ['life-processes'],
          topic_names: ['Nutrition'],
          difficulty_preset: 'balanced',
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/bank/generation-batches/144/',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/bank/generation-batches/144/candidates/',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/api/bank/generation-batches/144/accept/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ accepted_candidate_ids: [1, 3] }),
      }),
    );
  });
});

describe('login', () => {
  it('does not use the dev fallback for other credentials', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('proxy error', { status: 500 })),
    );

    await expect(login('wrong@example.com', 'teacher123')).rejects.toThrow(
      'Request failed (500)',
    );
    expect(getToken()).toBeNull();
  });

  it('stores and clears backend auth tokens through the normal storage seam', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              token: 'backend-token',
              user: { email: 'teacher@example.com' },
            }),
          ),
      ),
    );

    await login('teacher@example.com', 'teacher123');
    expect(getToken()).toBe('backend-token');

    clearToken();

    expect(getToken()).toBeNull();
  });
});

describe('paper persistence', () => {
  it('fetches a persisted canonical PaperDocumentV1 draft by paper id', async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify(mockPaperDocumentV1)),
    );
    vi.stubGlobal('fetch', fetchMock);

    const document = await fetchPaperDocument('paper_mock_cbse_science_001');

    expect(document.paper.id).toBe('paper_mock_cbse_science_001');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/mock_cbse_science_001/',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('rejects an invalid persisted paper instead of opening a broken editor', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ paper: { id: 'paper_1' } }))),
    );

    await expect(fetchPaperDocument('paper_1')).rejects.toThrow(
      'Backend returned an unexpected PaperDocument shape',
    );
  });

  it('persists canonical PaperDocument drafts instead of editor document JSON', async () => {
    const persistedDocument = structuredClone(mockPaperDocumentV1);
    persistedDocument.paper.id = 'paper_123';
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({})));
    vi.stubGlobal('fetch', fetchMock);

    await persistDraft(persistedDocument);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/123/',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ document: persistedDocument }),
      }),
    );
  });

  it('saves the canonical draft before approving the backend paper', async () => {
    const persistedDocument = structuredClone(mockPaperDocumentV1);
    persistedDocument.paper.id = 'paper_123';
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({})));
    vi.stubGlobal('fetch', fetchMock);

    await approvePaper(persistedDocument);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/papers/123/',
      expect.objectContaining({ method: 'PATCH' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/papers/123/approve/',
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
