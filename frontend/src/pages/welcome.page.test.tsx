import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import WelcomePage from './welcome.page';

vi.mock('react-router-dom', () => ({
  Link: ({ children, to }: { children: ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  NavLink: ({ children, to }: { children: ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useLocation: () => ({ state: { welcomeName: 'Varad' } }),
}));

vi.mock('@/hooks/useAuth.hook', () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

vi.mock('@/lib/api', () => ({
  fetchBankQuestions: vi.fn(async () => ({
    count: 0,
    limit: 1,
    offset: 0,
    results: [],
  })),
}));

describe('WelcomePage', () => {
  it('presents the pipeline: sources feed the bank, generate uses it', () => {
    const html = renderToStaticMarkup(<WelcomePage />);

    expect(html).toContain('Welcome, Varad.');
    expect(html).toContain('Exam Desk');
    expect(html).not.toContain(
      'Build your question bank from PDFs or AI, then generate a paper in',
    );
    expect(html).toContain('Upload Papers');
    expect(html).toContain('AI Q&amp;A');
    expect(html).toContain('Question Bank');
    expect(html).toContain('Generate Paper');
    expect(html).toContain('Opens BlockNote editor');
    expect(html).not.toContain('Sign out');
    expect(html).toContain('href="/upload"');
    expect(html).toContain('href="/ai-qa"');
    expect(html).toContain('href="/question-bank"');
    expect(html).toContain('href="/generate"');
  });
});
