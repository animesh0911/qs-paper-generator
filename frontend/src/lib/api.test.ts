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
import { clearToken, getToken, login } from './api';

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
