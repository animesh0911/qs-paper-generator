/**
 * Shared authenticated app header: brand, the three workflow links, and sign
 * out. Reuses the quiet "Exam Desk" header treatment (sticky, translucent,
 * hairline border) so every workflow page shares one chrome.
 *
 * @module AppHeader
 */
import { NavLink } from 'react-router-dom';
import { FileText, Library, Sparkles, Upload } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth.hook';
import { Button } from '@/components/ui/button';

const NAV_ITEMS = [
  { to: '/', label: 'Generate paper', icon: FileText, end: true },
  { to: '/upload', label: 'Upload papers', icon: Upload, end: false },
  { to: '/question-bank', label: 'Question bank', icon: Library, end: false },
  { to: '/ai-qa', label: 'AI Q&A', icon: Sparkles, end: false },
] as const;

export function AppHeader() {
  const { logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-5">
          <div className="leading-tight">
            <p className="text-[0.6875rem] font-medium uppercase tracking-wide text-muted-foreground">
              CBSE Class 10 Science
            </p>
            <p className="text-sm font-semibold">Question Paper Generator</p>
          </div>
          <nav aria-label="Workflows" className="flex items-center gap-1">
            {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    isActive
                      ? 'bg-secondary text-foreground'
                      : 'text-muted-foreground hover:bg-secondary/70 hover:text-foreground',
                  )
                }
              >
                <Icon className="size-4" aria-hidden="true" />
                <span className="hidden sm:inline">{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
        <Button variant="ghost" size="sm" onClick={logout}>
          Sign out
        </Button>
      </div>
    </header>
  );
}
