const TOKEN_KEY = "qpg_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export interface Question {
  id: number;
  section: string;
  qtype: string;
  marks: number;
  text: string;
  options: { label: string; text: string }[];
  // Only present on dedicated answer-key endpoints; the default question
  // serializer omits it so paper-assemble responses do not leak the key.
  answer?: string;
}
export interface PaperItem {
  order: number;
  section: string;
  question: Question;
}
export interface Paper {
  id: number;
  title: string;
  total_marks: number;
  created_at: string;
  items: PaperItem[];
}

async function request(path: string, options: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Token ${token}`;

  const res = await fetch(`/api${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      detail = data.detail || Object.values(data).flat().join(" ") || detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return res;
}

async function authResult(path: string, email: string, password: string) {
  const res = await request(path, {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  setToken(data.token);
  return data;
}

export const login = (email: string, password: string) =>
  authResult("/auth/login", email, password);

export const register = (email: string, password: string) =>
  authResult("/auth/register", email, password);

export async function assemblePaper(): Promise<Paper> {
  const res = await request("/papers/assemble", { method: "POST", body: "{}" });
  return res.json();
}

export async function downloadPaperPdf(id: number) {
  const res = await request(`/papers/${id}/pdf`, { method: "GET" });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `paper-${id}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
