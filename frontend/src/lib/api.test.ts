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
  clearToken,
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
