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
    expect(html).toContain('What would you like to do?');
    expect(html).toContain('Generate paper');
    expect(html).toContain('Upload papers');
    expect(html).toContain('AI Q&amp;A');
    expect(html).toContain('href="/generate"');
    expect(html).toContain('href="/upload"');
    expect(html).toContain('href="/ai-qa"');
  });
});
