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
  approvePaper,
  clearToken,
  fetchPaperDocument,
  getToken,
  login,
  savePaperDraft,
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
  it('uses a dev-only seeded teacher fallback when the local proxy is unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('proxy error', { status: 500 })),
    );

    const result = await login('teacher@example.com', 'teacher123');

    expect(result.user.email).toBe('teacher@example.com');
    expect(getToken()).toBe('dev-demo-token');
  });

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

  it('clears the fallback token through the normal auth storage seam', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('proxy error', { status: 500 })),
    );

    await login('teacher@example.com', 'teacher123');
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

    expect(document.paper.paperId).toBe('paper_mock_cbse_science_001');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/mock_cbse_science_001/',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('saves canonical PaperDocumentV1 drafts instead of editor document JSON', async () => {
    const persistedDocument = structuredClone(mockPaperDocumentV1);
    persistedDocument.paper.paperId = 'paper_123';
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            paperId: 'paper_mock_cbse_science_001',
            status: 'draft',
          }),
        ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await savePaperDraft(persistedDocument);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/123/',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ document: persistedDocument }),
      }),
    );
  });

  it('creates a persisted draft before saving standalone mock documents', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            paperId: 'paper_123',
            status: 'draft',
            document: {
              ...mockPaperDocumentV1,
              paper: { ...mockPaperDocumentV1.paper, paperId: 'paper_123' },
            },
          }),
        ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await savePaperDraft(mockPaperDocumentV1);

    expect(result.paperId).toBe('paper_123');
    expect(result.document?.paper.paperId).toBe('paper_123');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/drafts/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ document: mockPaperDocumentV1 }),
      }),
    );
  });

  it('approves the final canonical PaperDocumentV1 so the backend freezes current edits', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            paperId: 'paper_mock_cbse_science_001',
            status: 'approved',
          }),
        ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await approvePaper(mockPaperDocumentV1);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/mock_cbse_science_001/approve/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ document: mockPaperDocumentV1 }),
      }),
    );
  });
});
