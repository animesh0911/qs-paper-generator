/**
 * Shared authenticated app header: brand, the workflow links, and sign out.
 * Reuses the quiet "Exam Desk" header treatment (sticky, translucent,
 * hairline border) so every workflow page shares one chrome.
 *
 * @module AppHeader
 */
import { useEffect, useMemo, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Library,
  LoaderCircle,
  Sparkles,
  Upload,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchIngestionJobs } from '@/lib/api';
import { isIngestionJobRecent, isIngestionTerminal } from '@/lib/ingestion';
import { useAuth } from '@/hooks/useAuth.hook';
import { Button } from '@/components/ui/button';
import type { IngestionJob } from '@/types';

const TERMINAL_HEADER_VISIBLE_MS = 30 * 60 * 1000;

function shouldShowHeaderJob(job: IngestionJob): boolean {
  return (
    !isIngestionTerminal(job.status) ||
    isIngestionJobRecent(job, TERMINAL_HEADER_VISIBLE_MS)
  );
}

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
  const location = useLocation();
  const showIngestionPill = location.pathname !== '/upload';

  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
      <div className="flex flex-wrap items-center gap-2 px-4 py-2 sm:px-6">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-2">
          <Link
            to="/"
            className="min-w-0 rounded-sm py-1.5 leading-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
          {showIngestionPill && <IngestionActivityPill />}
          <Button
            variant="ghost"
            size="sm"
            className="h-11 sm:h-9"
            onClick={logout}
          >
            Sign out
          </Button>
        </div>
      </div>
    </header>
  );
}

function IngestionActivityPill() {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function refresh() {
      try {
        const next = await fetchIngestionJobs();
        if (cancelled) return;
        setJobs(next);
        const hasActive = next.some((job) => !isIngestionTerminal(job.status));
        timer = setTimeout(refresh, hasActive ? 3000 : 15000);
      } catch {
        if (!cancelled) timer = setTimeout(refresh, 15000);
      }
    }

    refresh();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  const job = useMemo(
    () =>
      jobs.find((item) => !isIngestionTerminal(item.status)) ??
      jobs.find(shouldShowHeaderJob),
    [jobs],
  );

  if (!job) return null;

  const inProgress = !isIngestionTerminal(job.status);
  const hasProgress = job.status === 'running' && job.total_pages > 0;
  const progress = hasProgress
    ? ` · ${job.pages_done}/${job.total_pages} pages`
    : '';
  const label = inProgress
    ? job.status === 'pending'
      ? 'Extraction queued'
      : `Extraction running${progress}`
    : job.status === 'done'
      ? `${job.created_count} extracted`
      : 'Extraction failed';

  return (
    <Link
      to="/upload"
      className={cn(
        'inline-flex h-8 max-w-[11rem] items-center gap-1.5 rounded-md border px-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        inProgress
          ? 'border-input bg-secondary text-foreground hover:bg-secondary/80'
          : 'border-input bg-background text-muted-foreground hover:bg-secondary',
      )}
      aria-label={`${label}. Open upload progress.`}
      aria-live="polite"
    >
      {inProgress ? (
        <LoaderCircle
          className="size-3.5 motion-safe:animate-spin"
          aria-hidden="true"
        />
      ) : job.status === 'failed' ? (
        <AlertTriangle className="size-3.5" aria-hidden="true" />
      ) : (
        <CheckCircle2 className="size-3.5" aria-hidden="true" />
      )}
      <span className="truncate">{label}</span>
    </Link>
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
              'inline-flex h-11 min-w-11 flex-1 shrink-0 items-center justify-center gap-1.5 rounded-md px-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:h-9 sm:min-w-9 sm:flex-none',
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
