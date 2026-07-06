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

describe('WelcomePage', () => {
  it('presents the three primary workflows after sign-in', () => {
    const html = renderToStaticMarkup(<WelcomePage />);

    expect(html).toContain('Welcome, Varad.');
    expect(html).toContain('Exam Desk');
    expect(html).toContain(
      'Grow the question bank by upload or AI, then generate a paper',
    );
    expect(html).toContain('Generate');
    expect(html).toContain('Upload');
    expect(html).toContain('AI Q&amp;A');
    expect(html).toContain('Question bank');
    expect(html).toContain('Feeds bank');
    expect(html).toContain('Uses bank');
    expect(html).not.toContain('Class 10 Science exam desk');
    expect(html).not.toContain('Verified question bank');
    expect(html).not.toContain('Sign out');
    expect(html).not.toContain('Diagram variants');
    expect(html).toContain('href="/generate"');
    expect(html).toContain('href="/upload"');
    expect(html).toContain('href="/ai-qa"');
  });
});
