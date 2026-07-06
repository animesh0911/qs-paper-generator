/**
 * Authenticated welcome screen.
 *
 * Gives teachers a deliberate choice between the three core workflows after
 * sign-in instead of dropping them straight into paper generation.
 *
 * @module WelcomePage
 */
import type { CSSProperties } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ArrowDown,
  ArrowUpRight,
  FileText,
  Sparkles,
  UploadCloud,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const WORKFLOWS = [
  {
    to: '/generate',
    title: 'Generate',
    description: 'Assemble a CBSE-style paper from your bank.',
    icon: FileText,
  },
  {
    to: '/upload',
    title: 'Upload',
    description: 'Add questions from past-paper PDFs.',
    icon: UploadCloud,
  },
  {
    to: '/ai-qa',
    title: 'AI Q&A',
    description: 'Draft new questions with AI.',
    icon: Sparkles,
  },
] as const;

export default function WelcomePage() {
  const location = useLocation();
  const welcomeName = resolveWelcomeName(location.state);

  return (
    <div className="min-h-screen bg-secondary">
      <main className="mx-auto flex min-h-screen max-w-6xl items-center px-4 py-8 sm:px-6 lg:py-10">
        <section aria-labelledby="welcome-heading" className="w-full">
          <div className="mb-7 max-w-2xl lg:mb-8">
            <p className="text-sm font-medium text-muted-foreground">
              Exam Desk
            </p>
            <h1
              id="welcome-heading"
              className="mt-2 text-3xl font-semibold leading-9 tracking-[-0.01em] text-foreground"
            >
              Welcome, {welcomeName}.
            </h1>
            <p className="mt-2 text-base leading-7 text-muted-foreground">
              Grow the question bank by upload or AI, then generate a paper from
              it.
            </p>
          </div>

          <ConvergeDiagram />
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

function ConvergeDiagram() {
  const upload = WORKFLOWS[1];
  const aiQa = WORKFLOWS[2];
  const generate = WORKFLOWS[0];

  return (
    <div className="qpg-flow-stage relative overflow-hidden rounded-lg border bg-background p-4 sm:p-5 lg:p-7">
      <div className="hidden lg:block" aria-hidden="true">
        <div className="qpg-flow-line qpg-flow-line-east absolute left-[31%] top-[29%] h-px w-[19%]" />
        <div className="qpg-flow-line qpg-flow-line-east absolute left-[31%] top-[71%] h-px w-[19%]" />
        <div className="qpg-flow-line qpg-flow-line-south absolute left-1/2 top-[29%] h-[42%] w-px" />
        <div className="qpg-flow-line qpg-flow-line-east qpg-flow-line-final absolute left-1/2 top-1/2 h-px w-[28%]" />
      </div>
      <FlowBridge variant="desktop" />

      <div className="relative grid gap-5 lg:grid-cols-[minmax(220px,0.9fr)_minmax(132px,0.38fr)_minmax(240px,0.9fr)] lg:items-center">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
          <WorkflowNode workflow={upload} tone="source" animationOrder={1} />
          <WorkflowNode workflow={aiQa} tone="source" animationOrder={2} />
        </div>

        <FlowBridge variant="mobile" />
        <div className="hidden lg:block" aria-hidden="true" />
        <WorkflowNode workflow={generate} tone="primary" animationOrder={4} />
      </div>
    </div>
  );
}

function FlowBridge({ variant }: { variant: 'desktop' | 'mobile' }) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 py-1 text-muted-foreground',
        variant === 'desktop'
          ? 'absolute left-1/2 top-1/2 z-10 hidden -translate-x-1/2 -translate-y-1/2 lg:flex'
          : 'qpg-flow-node lg:hidden',
      )}
      style={{ '--qpg-flow-order': 3 } as CSSProperties}
    >
      <ArrowDown className="size-4 lg:hidden" aria-hidden="true" />
      <Link
        to="/question-bank"
        className="qpg-flow-bridge-label group/bank inline-flex items-center gap-1 rounded-md border bg-background px-2.5 py-1 text-[0.6875rem] font-medium leading-4 text-foreground/70 transition-colors duration-200 ease-out hover:border-foreground/25 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label="Question bank"
      >
        Question bank
        <ArrowUpRight
          className="size-3 shrink-0 text-foreground/45 transition-transform duration-200 group-hover/bank:-translate-y-0.5 group-hover/bank:translate-x-0.5"
          aria-hidden="true"
        />
      </Link>
      <ArrowDown className="size-4 lg:hidden" aria-hidden="true" />
    </div>
  );
}

function WorkflowNode({
  workflow,
  tone,
  animationOrder,
}: {
  workflow: (typeof WORKFLOWS)[number];
  tone: 'source' | 'primary';
  animationOrder: 1 | 2 | 4;
}) {
  const Icon = workflow.icon;
  const isPrimary = tone === 'primary';

  return (
    <Link
      to={workflow.to}
      style={{ '--qpg-flow-order': animationOrder } as CSSProperties}
      className={cn(
        'qpg-flow-card qpg-flow-node group flex min-h-40 flex-col rounded-lg border bg-background p-5 transition-colors duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'hover:border-foreground/25 hover:bg-secondary/35 active:bg-secondary/55',
        isPrimary && 'border-foreground/25 hover:bg-secondary/70',
      )}
      aria-label={workflow.title}
    >
      <div
        className={cn(
          'flex size-9 shrink-0 items-center justify-center rounded-md border transition-colors duration-200',
          isPrimary
            ? 'bg-background/85 text-foreground'
            : 'bg-secondary/55 text-foreground group-hover:bg-foreground group-hover:text-background',
        )}
      >
        <Icon className="size-[1.0625rem]" aria-hidden="true" />
      </div>

      <div className="mt-3 min-w-0">
        <p
          className={cn(
            'text-[0.6875rem] font-medium leading-4',
            isPrimary ? 'text-foreground/70' : 'text-muted-foreground',
          )}
        >
          {isPrimary ? 'Uses bank' : 'Feeds bank'}
        </p>
        <h2
          className={cn(
            'mt-0.5 text-lg font-semibold leading-7',
            isPrimary ? 'text-foreground' : 'text-foreground',
          )}
        >
          {workflow.title}
        </h2>
        <p
          className={cn(
            'mt-1 text-[0.9375rem] leading-6',
            isPrimary ? 'text-muted-foreground' : 'text-muted-foreground',
          )}
        >
          {workflow.description}
        </p>
      </div>

      <div
        className={cn(
          'mt-auto flex w-full items-center justify-end gap-1 pt-4 text-[0.6875rem] font-medium leading-4',
          isPrimary ? 'text-foreground' : 'text-foreground',
        )}
      >
        <span className="text-foreground/70">
          {isPrimary ? 'Generate' : 'Open'}
        </span>
        <ArrowUpRight
          className="size-3 shrink-0 text-foreground/55 transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </div>
    </Link>
  );
}
