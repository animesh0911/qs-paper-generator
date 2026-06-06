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
  assemblePaper,
  clearToken,
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
});
