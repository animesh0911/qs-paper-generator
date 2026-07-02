/**
 * Authenticated welcome screen.
 *
 * Gives teachers a deliberate choice between the three core workflows after
 * sign-in instead of dropping them straight into paper generation.
 *
 * @module WelcomePage
 */
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, FileText, Sparkles, UploadCloud } from 'lucide-react';
import { AppHeader } from '@/components/app-nav';
import { cn } from '@/lib/utils';

const WORKFLOWS = [
  {
    to: '/generate',
    title: 'Generate',
    description: 'Build a CBSE paper from selected chapters.',
    icon: FileText,
  },
  {
    to: '/upload',
    title: 'Upload',
    description: 'Add PDF papers to grow the question bank.',
    icon: UploadCloud,
  },
  {
    to: '/ai-qa',
    title: 'AI Q&A',
    description: 'Draft question-and-answer candidates.',
    icon: Sparkles,
  },
] as const;

export default function WelcomePage() {
  const location = useLocation();
  const welcomeName = resolveWelcomeName(location.state);

  return (
    <div className="min-h-screen bg-secondary">
      <AppHeader />

      <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-5xl items-center px-4 py-8 sm:px-6">
        <section aria-labelledby="welcome-heading" className="w-full">
          <div className="mb-6 max-w-2xl">
            <p className="text-sm font-medium text-muted-foreground">
              Class 10 Science exam desk
            </p>
            <h1
              id="welcome-heading"
              className="mt-2 text-2xl font-semibold leading-8 tracking-[-0.01em] text-foreground sm:text-3xl sm:leading-10"
            >
              Welcome, {welcomeName}.
            </h1>
            <p className="mt-1 text-lg font-medium leading-7 text-foreground/80">
              What would you like to do?
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            {WORKFLOWS.map((workflow) => (
              <WorkflowCard key={workflow.to} workflow={workflow} />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

const WELCOME_NAME_STORAGE_KEY = 'qpg_welcome_name';

type WelcomeLocationState = {
  welcomeName?: string;
};

function resolveWelcomeName(state: unknown): string {
  const fromRoute = (state as WelcomeLocationState | null)?.welcomeName;
  if (fromRoute) return fromRoute;
  if (typeof sessionStorage === 'undefined') return 'Teacher';
  return sessionStorage.getItem(WELCOME_NAME_STORAGE_KEY) || 'Teacher';
}

function WorkflowCard({ workflow }: { workflow: (typeof WORKFLOWS)[number] }) {
  const Icon = workflow.icon;

  return (
    <Link
      to={workflow.to}
      className={cn(
        'group flex min-h-48 flex-col rounded-xl border bg-background p-5 transition-colors duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'hover:border-foreground/25 hover:bg-secondary/35 active:bg-secondary/55',
      )}
      aria-label={workflow.title}
    >
      <div className="flex size-11 items-center justify-center rounded-lg border bg-secondary/55 text-foreground transition-colors duration-200 group-hover:bg-foreground group-hover:text-background">
        <Icon className="size-5" aria-hidden="true" />
      </div>

      <div className="mt-5">
        <h2 className="text-xl font-semibold leading-7 text-foreground">
          {workflow.title}
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {workflow.description}
        </p>
      </div>

      <div className="mt-auto flex items-center justify-between pt-6 text-sm font-medium text-foreground">
        <span>Open</span>
        <ArrowRight
          className="size-4 transition-transform duration-200 group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </div>
    </Link>
  );
}
