/**
 * Single HTTP adapter for the backend.
 *
 * All requests go through the private `request()` helper, which:
 * - prefixes `/api`,
 * - attaches `Authorization: Token <value>` if a token is present,
 * - parses DRF error envelopes into a readable `Error.message`.
 *
 * Token storage is the boring localStorage approach — the same token the
 * backend returns from `/api/auth/login`. The choice to omit a refresh
 * flow is deliberate for the MVP; revisit when sessions need to outlive
 * a browser tab.
 *
 * @module api
 */
import type {
  AssembleRequest,
  Chapter,
  ChapterTopicsResponse,
  EditorDraftResponse,
  GenerationBatch,
  GenerationBatchCreateRequest,
  GeneratedQuestionCandidate,
  IngestionJob,
  PaperDocument,
  PaperFormatSummary,
  SourceType,
} from '@/types';
import { paperDocumentSchema } from '@/types/paper-document.schema';

const TOKEN_KEY = 'qpg_token';
const AUTH_TOKEN_CHANGED_EVENT = 'qpg:auth-token-changed';

function notifyTokenChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_TOKEN_CHANGED_EVENT));
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
  notifyTokenChanged();
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  notifyTokenChanged();
}
export function onTokenChange(listener: () => void): () => void {
  window.addEventListener(AUTH_TOKEN_CHANGED_EVENT, listener);
  window.addEventListener('storage', listener);
  return () => {
    window.removeEventListener(AUTH_TOKEN_CHANGED_EVENT, listener);
    window.removeEventListener('storage', listener);
  };
}

async function request(
  path: string,
  options: RequestInit = {},
  tokenOverride?: string | null,
): Promise<Response> {
  // FormData bodies must set their own multipart boundary, so we never force a
  // JSON Content-Type on them (the PDF upload relies on this).
  const isFormData =
    typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers as Record<string, string>),
  };
  const token = tokenOverride === undefined ? getToken() : tokenOverride;
  if (token) headers['Authorization'] = `Token ${token}`;

  const res = await fetch(`/api${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      detail = data.detail || Object.values(data).flat().join(' ') || detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    if (
      tokenOverride === undefined &&
      token &&
      (res.status === 401 || res.status === 403)
    ) {
      clearToken();
    }
    throw new Error(detail);
  }
  return res;
}

async function authResult(path: string, email: string, password: string) {
  const res = await request(
    path,
    {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    },
    null,
  );
  const data = await res.json();
  setToken(data.token);
  return data;
}

export const login = (email: string, password: string) =>
  authResult('/auth/login', email, password);

export const register = (email: string, password: string) =>
  authResult('/auth/register', email, password);

export async function assemblePaper(
  body: AssembleRequest = {},
): Promise<PaperDocument> {
  const res = await request('/papers/assemble', {
    method: 'POST',
    body: JSON.stringify(body),
  });
  // Runtime contract check — see paper-document.schema.ts for rationale.
  const parsed = paperDocumentSchema.safeParse(await res.json());
  if (!parsed.success) {
    throw new Error(
      `Backend returned an unexpected PaperDocument shape: ${parsed.error.message}`,
    );
  }
  return parsed.data as PaperDocument;
}

export async function fetchPaperDocument(
  paperId: string,
  token?: string | null,
): Promise<PaperDocument> {
  const id = paperId.replace(/^paper_/, '');
  const res = await request(
    `/papers/${id}/`,
    { method: 'GET' },
    token ?? undefined,
  );
  const parsed = paperDocumentSchema.safeParse(await res.json());
  if (!parsed.success) {
    throw new Error(
      `Backend returned an unexpected PaperDocument shape: ${parsed.error.message}`,
    );
  }
  return parsed.data as PaperDocument;
}

export async function fetchEditorDraft(
  paperId: string,
): Promise<EditorDraftResponse> {
  const id = paperId.replace(/^paper_/, '');
  const res = await request(`/papers/${id}/editor-draft/`, { method: 'GET' });
  const data = await res.json();
  const parsed = paperDocumentSchema.safeParse(data.document);
  if (!parsed.success) {
    throw new Error(
      `Backend returned an unexpected PaperDocument shape: ${parsed.error.message}`,
    );
  }
  if (!isPaperAnswerDocument(data.answer_document)) {
    throw new Error('Backend returned an unexpected answer document shape.');
  }
  return {
    document: parsed.data as PaperDocument,
    answer_document: data.answer_document,
    status: typeof data.status === 'string' ? data.status : '',
  };
}

function isPaperAnswerDocument(value: unknown): value is EditorDraftResponse['answer_document'] {
  return (
    Boolean(value) &&
    typeof value === 'object' &&
    (value as { schemaVersion?: unknown }).schemaVersion ===
      'paper_answer_document.v1' &&
    typeof (value as { paperId?: unknown }).paperId === 'string' &&
    Boolean((value as { answersBySlotId?: unknown }).answersBySlotId) &&
    typeof (value as { answersBySlotId?: unknown }).answersBySlotId === 'object'
  );
}

export async function persistDraft(paper: PaperDocument): Promise<void> {
  const id = paper.paper.id.replace(/^paper_/, '');
  await request(`/papers/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify({ document: paper }),
  });
}

export async function approvePaper(paper: PaperDocument): Promise<void> {
  await persistDraft(paper);
  const id = paper.paper.id.replace(/^paper_/, '');
  await request(`/papers/${id}/approve/`, { method: 'POST' });
}

export interface Metadata {
  sections: { code: string; label: string }[];
  question_types: { code: string; label: string }[];
  cognitive_levels: { code: string; label: string }[];
}

export async function fetchMetadata(): Promise<Metadata> {
  const res = await request('/bank/metadata/');
  return res.json();
}

export async function fetchChapters(): Promise<Chapter[]> {
  const res = await request('/bank/chapters/');
  return res.json();
}

export async function fetchChapterTopics(
  chapterSlug: string,
): Promise<ChapterTopicsResponse> {
  const res = await request(`/corpus/chapters/${chapterSlug}/topics/`);
  return res.json();
}

export async function fetchPaperFormats(): Promise<PaperFormatSummary[]> {
  const res = await request('/papers/formats', { method: 'GET' });
  return res.json();
}

export async function downloadPaperPdf(paper: PaperDocument) {
  const paperId = paper.paper.id;
  const id = paperId.replace(/^paper_/, '');
  const res = await request(`/papers/${id}/pdf/`, { method: 'GET' });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${paperId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * Upload a teacher's PDF for out-of-request extraction. Returns 202 + the
 * queued `IngestionJob` to poll; the Gemini extraction runs later via cron.
 */
export async function uploadIngestionPdf(
  pdf: File,
  sourceType: SourceType,
): Promise<IngestionJob> {
  const body = new FormData();
  body.append('pdf', pdf);
  body.append('source_type', sourceType);
  const res = await request('/bank/ingest/', { method: 'POST', body });
  return res.json();
}

/** Poll one ingestion job's status (scoped to the teacher's school). */
export async function fetchIngestionJob(
  jobId: number | string,
): Promise<IngestionJob> {
  const res = await request(`/bank/ingest/${jobId}/`, { method: 'GET' });
  return res.json();
}

export async function createGenerationBatch(
  body: GenerationBatchCreateRequest,
): Promise<GenerationBatch> {
  const res = await request('/bank/generation-batches/', {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function fetchGenerationBatch(
  batchId: number | string,
): Promise<GenerationBatch> {
  const res = await request(`/bank/generation-batches/${batchId}/`, {
    method: 'GET',
  });
  return res.json();
}

export async function fetchGenerationBatches(): Promise<GenerationBatch[]> {
  const res = await request('/bank/generation-batches/', { method: 'GET' });
  return res.json();
}

export async function discardGenerationBatch(
  batchId: number | string,
): Promise<GenerationBatch> {
  const res = await request(`/bank/generation-batches/${batchId}/discard/`, {
    method: 'POST',
  });
  return res.json();
}

export async function fetchGenerationCandidates(
  batchId: number | string,
): Promise<GeneratedQuestionCandidate[]> {
  const res = await request(`/bank/generation-batches/${batchId}/candidates/`, {
    method: 'GET',
  });
  return res.json();
}

export async function acceptGenerationCandidates(
  batchId: number | string,
  acceptedCandidateIds: number[],
): Promise<GenerationBatch> {
  const res = await request(`/bank/generation-batches/${batchId}/accept/`, {
    method: 'POST',
    body: JSON.stringify({ accepted_candidate_ids: acceptedCandidateIds }),
  });
  return res.json();
}
