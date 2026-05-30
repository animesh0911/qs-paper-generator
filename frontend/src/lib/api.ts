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
import type { AssembleRequest, Chapter, PaperDocument } from '@/types';
import { assertPaperDocument } from './paper-document';

const TOKEN_KEY = 'qpg_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
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
    throw new Error(detail);
  }
  return res;
}

async function authResult(path: string, email: string, password: string) {
  const res = await request(path, {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
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
  return assertPaperDocument(await res.json());
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

export async function downloadPaperPdf(paperId: string) {
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
