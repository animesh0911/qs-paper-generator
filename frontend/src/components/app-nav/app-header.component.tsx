/**
 * Shared authenticated app header: brand, the workflow links, and sign out.
 * Reuses the quiet "Exam Desk" header treatment (sticky, translucent,
 * hairline border) so every workflow page shares one chrome.
 *
 * @module AppHeader
 */
import { Link, NavLink } from 'react-router-dom';
import { FileText, Library, Sparkles, Upload } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth.hook';
import { Button } from '@/components/ui/button';

const NAV_ITEMS = [
  {
    to: '/generate',
    label: 'Generate paper',
    shortLabel: 'Generate',
    icon: FileText,
    end: true,
  },
  {
    to: '/upload',
    label: 'Upload papers',
    shortLabel: 'Upload',
    icon: Upload,
    end: false,
  },
  {
    to: '/question-bank',
    label: 'Question bank',
    shortLabel: 'Bank',
    icon: Library,
    end: false,
  },
  {
    to: '/ai-qa',
    label: 'AI Q&A',
    shortLabel: 'Q&A',
    icon: Sparkles,
    end: false,
  },
] as const;

export function AppHeader() {
  const { logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
      <div className="flex flex-wrap items-center gap-2 px-4 py-2 sm:px-6">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-2">
          <Link
            to="/"
            className="min-w-0 rounded-sm leading-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <p className="text-[0.625rem] font-medium uppercase tracking-wide text-muted-foreground">
              CBSE Class 10 Science
            </p>
            <p className="text-sm font-semibold">Question Paper Generator</p>
          </Link>
          <div className="order-3 w-full sm:order-none sm:w-auto">
            <WorkflowNav />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-1.5">
          <Button variant="ghost" size="sm" onClick={logout}>
            Sign out
          </Button>
        </div>
      </div>
    </header>
  );
}

function WorkflowNav() {
  return (
    <nav
      aria-label="Workflows"
      className="flex w-full min-w-0 items-center gap-0.5 rounded-md bg-secondary/70 p-0.5 sm:w-auto"
    >
      {NAV_ITEMS.map(({ to, label, shortLabel, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          aria-label={label}
          className={({ isActive }) =>
            cn(
              'inline-flex h-9 min-w-9 flex-1 shrink-0 items-center justify-center gap-1.5 rounded-md px-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:flex-none',
              isActive
                ? 'bg-background text-foreground'
                : 'text-muted-foreground hover:bg-background/70 hover:text-foreground',
            )
          }
        >
          <Icon className="size-3.5" aria-hidden="true" />
          <span className="sm:hidden">{shortLabel}</span>
          <span className="hidden sm:inline">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
