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
  fetchEditorDraft,
  fetchGenerationBatch,
  fetchGenerationCandidates,
  fetchBankQuestions,
  fetchPaperFormats,
  fetchPaperDocument,
  getToken,
  login,
  persistDraft,
  persistEditorDraft,
  downloadPaperPdfPackage,
  openPaperPrintPreview,
  reservePaperPrintPreview,
} from './api';

const storage = new Map<string, string>();

beforeEach(() => {
  storage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
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

  it('clears a stale token when the backend rejects an authenticated request', async () => {
    storage.set('qpg_token', 'stale-token');
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ detail: 'Invalid token.' }), {
          status: 401,
        }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchPaperFormats()).rejects.toThrow('Invalid token.');

    expect(getToken()).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/formats',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Token stale-token',
        }),
      }),
    );
  });

  it('does not clear the stored session for one-off token override failures', async () => {
    storage.set('qpg_token', 'current-session-token');
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'Invalid token.' }), {
            status: 401,
          }),
      ),
    );

    await expect(fetchPaperDocument('paper_1', 'print-token')).rejects.toThrow(
      'Invalid token.',
    );

    expect(getToken()).toBe('current-session-token');
  });

  it('can keep the current screen mounted when a non-critical request is unauthorized', async () => {
    storage.set('qpg_token', 'current-session-token');
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'Invalid token.' }), {
            status: 401,
          }),
      ),
    );

    await expect(
      fetchBankQuestions({ limit: 1 }, { clearAuthOnUnauthorized: false }),
    ).rejects.toThrow('Invalid token.');

    expect(getToken()).toBe('current-session-token');
  });

  it('uses the active browser session when the print route has no token query', async () => {
    storage.set('qpg_token', 'current-session-token');
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify(mockPaperDocumentV1)),
    );
    vi.stubGlobal('fetch', fetchMock);

    await fetchPaperDocument('paper_mock_cbse_science_001', null);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/mock_cbse_science_001/',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Token current-session-token',
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

  it('does not attach a stale token to login requests', async () => {
    storage.set('qpg_token', 'stale-token');
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            token: 'fresh-token',
            user: { email: 'teacher@example.com' },
          }),
        ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await login('teacher@example.com', 'teacher123');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({
        headers: expect.not.objectContaining({
          Authorization: expect.any(String),
        }),
      }),
    );
    expect(getToken()).toBe('fresh-token');
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

  it('loads the editor draft document and paper-local answers together', async () => {
    const answerDocument = {
      schemaVersion: 'paper_answer_document.v1',
      paperId: 'paper_mock_cbse_science_001',
      answersBySlotId: {
        slot_A_01: {
          slotId: 'slot_A_01',
          questionId: 'q_1',
          content: [{ type: 'paragraph', text: 'Model answer' }],
          source: 'generated',
          modified: false,
        },
      },
    };
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            document: mockPaperDocumentV1,
            answer_document: answerDocument,
            status: 'draft',
          }),
        ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const draft = await fetchEditorDraft('paper_mock_cbse_science_001');

    expect(draft.document.paper.id).toBe('paper_mock_cbse_science_001');
    expect(draft.answer_document).toEqual(answerDocument);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/mock_cbse_science_001/editor-draft/',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('rejects an invalid persisted paper instead of opening a broken editor', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () => new Response(JSON.stringify({ paper: { id: 'paper_1' } })),
      ),
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

  it('persists the editor draft document and answer document together', async () => {
    const persistedDocument = structuredClone(mockPaperDocumentV1);
    persistedDocument.paper.id = 'paper_123';
    const answerDocument = {
      schemaVersion: 'paper_answer_document.v1' as const,
      paperId: 'paper_123',
      answersBySlotId: {},
    };
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            document: persistedDocument,
            answer_document: answerDocument,
            status: 'draft',
          }),
        ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const saved = await persistEditorDraft(persistedDocument, answerDocument);

    expect(saved.answer_document).toEqual(answerDocument);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/123/editor-draft/',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          document: persistedDocument,
          answer_document: answerDocument,
        }),
      }),
    );
  });

  it('downloads the one-click PDF package', async () => {
    vi.useFakeTimers();
    const persistedDocument = structuredClone(mockPaperDocumentV1);
    persistedDocument.paper.id = 'paper_123';
    const click = vi.fn();
    const remove = vi.fn();
    const anchor = { href: '', download: '', click, remove };
    const fetchMock = vi.fn(async () => new Response(new Blob(['zip'])));
    vi.stubGlobal('fetch', fetchMock);
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:package'),
      revokeObjectURL,
    });
    vi.stubGlobal('document', {
      createElement: vi.fn(() => anchor),
      body: {
        appendChild: vi.fn((node) => node),
      },
    });

    await downloadPaperPdfPackage(persistedDocument);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/papers/123/download-package/',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(anchor.href).toBe('blob:package');
    expect(anchor.download).toBe('paper_123-pdfs.zip');
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).not.toHaveBeenCalled();

    vi.advanceTimersByTime(60_000);

    expect(revokeObjectURL).toHaveBeenCalledWith('blob:package');
    expect(globalThis.open).toBeUndefined();
  });

  it('opens the question-paper print preview in a new tab', () => {
    const persistedDocument = structuredClone(mockPaperDocumentV1);
    persistedDocument.paper.id = 'paper_123';
    const open = vi.fn();
    vi.stubGlobal('open', open);

    openPaperPrintPreview(persistedDocument);

    expect(open).toHaveBeenCalledWith(
      '/editor/paper_123/print',
      '_blank',
      'noopener,noreferrer',
    );
  });

  it('reserves a preview tab synchronously and navigates it later', () => {
    const persistedDocument = structuredClone(mockPaperDocumentV1);
    persistedDocument.paper.id = 'paper_123';
    const tab = {
      location: { href: '' },
      close: vi.fn(),
    };
    const open = vi.fn(() => tab);
    vi.stubGlobal('open', open);

    const reserved = reservePaperPrintPreview();
    reserved.show(persistedDocument);

    expect(open).toHaveBeenCalledWith('about:blank', '_blank');
    expect(tab.location.href).toBe('/editor/paper_123/print');
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
