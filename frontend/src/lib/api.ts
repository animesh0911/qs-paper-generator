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
  BankQuestion,
  BankQuestionFilters,
  BankQuestionSource,
  BankQuestionsResponse,
  Chapter,
  ChapterTopicsResponse,
  EditorDraftResponse,
  GenerationBatch,
  GenerationBatchCreateRequest,
  GeneratedQuestionCandidate,
  IngestionAnswersResponse,
  AnswerGenerationJob,
  IngestionJob,
  PaperAnswerDocument,
  PaperDocument,
  PaperFormatSummary,
  PaperSourceSummary,
} from '@/types';
import { paperDocumentSchema } from '@/types/paper-document.schema';

const TOKEN_KEY = 'qpg_token';
const AUTH_TOKEN_CHANGED_EVENT = 'qpg:auth-token-changed';

/**
 * Every request aborts eventually. Without a signal, a stalled connection
 * (dead wifi, hung proxy) leaves `fetch` pending forever and any UI state
 * keyed on it — e.g. the upload page's "Uploading…" — stuck with no error.
 * Uploads get a longer budget: a 25 MB scan on school wifi is slow but alive.
 */
const REQUEST_TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 120_000;

function isAbortError(err: unknown): boolean {
  return (
    err instanceof DOMException &&
    (err.name === 'TimeoutError' || err.name === 'AbortError')
  );
}

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

type ApiRequestOptions = RequestInit & {
  /**
   * Authenticated background adornments can opt out so a non-critical 401 does
   * not kick the teacher off the current screen.
   */
  clearAuthOnUnauthorized?: boolean;
};

async function request(
  path: string,
  options: ApiRequestOptions = {},
  tokenOverride?: string | null,
): Promise<Response> {
  // FormData bodies must set their own multipart boundary, so we never force a
  // JSON Content-Type on them (the PDF upload relies on this).
  const isFormData =
    typeof FormData !== 'undefined' && options.body instanceof FormData;
  const { clearAuthOnUnauthorized = true, ...fetchOptions } = options;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(fetchOptions.headers as Record<string, string>),
  };
  const token = tokenOverride === undefined ? getToken() : tokenOverride;
  if (token) headers['Authorization'] = `Token ${token}`;

  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      ...fetchOptions,
      headers,
    });
  } catch (err) {
    if (isAbortError(err)) {
      throw new Error(
        'The request timed out. Check your connection and try again.',
      );
    }
    throw err;
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      detail = data.detail || Object.values(data).flat().join(' ') || detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    if (
      clearAuthOnUnauthorized &&
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

export interface AuthUser {
  id: number;
  email: string;
  school?: number | null;
}

export interface AuthResponse {
  token: string;
  user?: AuthUser;
}

async function authResult(
  path: string,
  email: string,
  password: string,
): Promise<AuthResponse> {
  const res = await request(
    path,
    {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    },
    null,
  );
  const data = (await res.json()) as AuthResponse;
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
  token?: string | null,
): Promise<EditorDraftResponse> {
  const id = paperId.replace(/^paper_/, '');
  const res = await request(
    `/papers/${id}/editor-draft/`,
    { method: 'GET' },
    token ?? undefined,
  );
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

function isPaperAnswerDocument(
  value: unknown,
): value is EditorDraftResponse['answer_document'] {
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

export async function persistEditorDraft(
  paper: PaperDocument,
  answerDocument: PaperAnswerDocument,
): Promise<EditorDraftResponse> {
  const id = paper.paper.id.replace(/^paper_/, '');
  const res = await request(`/papers/${id}/editor-draft/`, {
    method: 'PATCH',
    body: JSON.stringify({
      document: paper,
      answer_document: answerDocument,
    }),
  });
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

/** Distinct source papers for the Question Bank's source filter. */
export async function fetchBankQuestionSources(): Promise<
  BankQuestionSource[]
> {
  const res = await request('/bank/question-sources/');
  return res.json();
}

/** List bank questions for the browsable Question Bank view (paginated). */
export async function fetchBankQuestions(
  filters: BankQuestionFilters = {},
  options: ApiRequestOptions = {},
): Promise<BankQuestionsResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value));
    }
  }
  const query = params.toString();
  const res = await request(
    `/bank/questions/${query ? `?${query}` : ''}`,
    options,
  );
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

export async function fetchPaperSources(
  chapterSlugs: string[] = [],
): Promise<PaperSourceSummary[]> {
  const params = new URLSearchParams();
  for (const slug of chapterSlugs) params.append('chapter', slug);
  const query = params.toString();
  const res = await request(`/bank/sources/${query ? `?${query}` : ''}`, {
    method: 'GET',
  });
  return res.json();
}

const DOWNLOAD_OBJECT_URL_REVOKE_DELAY_MS = 60_000;

export interface ReservedPaperPrintPreview {
  show: (paper: PaperDocument) => void;
  close: () => void;
}

export function openPaperPrintPreview(paper: PaperDocument) {
  globalThis.open?.(
    `/editor/${paper.paper.id}/print`,
    '_blank',
    'noopener,noreferrer',
  );
}

export function reservePaperPrintPreview(): ReservedPaperPrintPreview {
  // Must keep the Window handle so dirty-save downloads can reserve the tab
  // synchronously with the click and navigate it after the async save. Do not
  // use noopener here: several browsers return null or sever script access,
  // leaving the reserved tab stuck on about:blank.
  const tab = globalThis.open?.('about:blank', '_blank');
  return {
    show: (paper: PaperDocument) => {
      const href = `/editor/${paper.paper.id}/print`;
      if (tab) {
        tab.location.href = href;
      } else {
        globalThis.open?.(href, '_blank', 'noopener,noreferrer');
      }
    },
    close: () => tab?.close(),
  };
}

export async function downloadPaperPdfPackage(paper: PaperDocument) {
  const paperId = paper.paper.id;
  const id = paperId.replace(/^paper_/, '');
  const res = await request(`/papers/${id}/download-package/`, {
    method: 'GET',
  });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${paperId}-pdfs.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(
    () => URL.revokeObjectURL(url),
    DOWNLOAD_OBJECT_URL_REVOKE_DELAY_MS,
  );
}

/**
 * Upload a teacher's PDF for out-of-request extraction. Returns 202 + the
 * queued `IngestionJob` to poll; the Gemini extraction runs later via cron.
 */
export async function uploadIngestionPdf(pdf: File): Promise<IngestionJob> {
  const body = new FormData();
  body.append('pdf', pdf);
  const res = await request('/bank/ingest/', {
    method: 'POST',
    body,
    signal: AbortSignal.timeout(UPLOAD_TIMEOUT_MS),
  });
  return res.json();
}

/** List recent ingestion jobs (scoped to the teacher's school). */
export async function fetchIngestionJobs(): Promise<IngestionJob[]> {
  const res = await request('/bank/ingest/', { method: 'GET' });
  return res.json();
}

/** Poll one ingestion job's status (scoped to the teacher's school). */
export async function fetchIngestionJob(
  jobId: number | string,
): Promise<IngestionJob> {
  const res = await request(`/bank/ingest/${jobId}/`, { method: 'GET' });
  return res.json();
}

/** Dismiss a failed ingestion job, removing it from the teacher's queue. */
export async function dismissIngestionJob(
  jobId: number | string,
): Promise<void> {
  await request(`/bank/ingest/${jobId}/`, { method: 'DELETE' });
}

/**
 * Re-queue a failed ingestion job so the drainer extracts it again (resuming
 * from its last per-page checkpoint). Returns the re-queued `pending` job.
 */
export async function retryIngestionJob(
  jobId: number | string,
): Promise<IngestionJob> {
  const res = await request(`/bank/ingest/${jobId}/retry/`, { method: 'POST' });
  return res.json();
}

/**
 * List the questions a finished ingestion job added to the bank — what the
 * upload status card shows once extraction + validation complete.
 */
export async function fetchIngestionJobQuestions(
  jobId: number | string,
): Promise<BankQuestion[]> {
  const res = await request(`/bank/ingest/${jobId}/questions/`, {
    method: 'GET',
  });
  return res.json();
}

export async function fetchIngestionJobAnswers(
  jobId: number | string,
): Promise<IngestionAnswersResponse> {
  const res = await request(`/bank/ingest/${jobId}/answers/`, {
    method: 'GET',
  });
  return res.json();
}

export async function generateIngestionJobAnswers(
  jobId: number | string,
): Promise<AnswerGenerationJob> {
  const res = await request(`/bank/ingest/${jobId}/answers/`, {
    method: 'POST',
  });
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

/** Re-queue a failed generation batch so the drainer runs it again. */
export async function retryGenerationBatch(
  batchId: number | string,
): Promise<GenerationBatch> {
  const res = await request(`/bank/generation-batches/${batchId}/retry/`, {
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
