/**
 * Authenticated welcome screen.
 *
 * Shows the product pipeline as a live diagram: Upload and AI Q&A feed the
 * Question bank, and Generate assembles a paper from it. Desktop wires are
 * measured from the rendered card positions, so they stay attached to the
 * cards at any viewport size; below `lg` the pipeline stacks vertically.
 *
 * @module WelcomePage
 */
import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ArrowDown,
  ArrowRight,
  FileText,
  Library,
  Sparkles,
  UploadCloud,
} from 'lucide-react';
import { fetchBankQuestions } from '@/lib/api';

const SOURCE_WORKFLOWS = [
  {
    to: '/upload',
    title: 'Upload papers',
    description: 'Add questions from past-paper PDFs.',
    icon: UploadCloud,
    animationOrder: 1,
  },
  {
    to: '/ai-qa',
    title: 'AI Q&A',
    description: 'Draft new questions with AI.',
    icon: Sparkles,
    animationOrder: 2,
  },
] as const;

export default function WelcomePage() {
  const location = useLocation();
  const welcomeName = resolveWelcomeName(location.state);

  return (
    <div className="min-h-screen bg-secondary">
      <main className="mx-auto flex min-h-screen w-full max-w-6xl items-center px-4 py-10 sm:px-6">
        <section aria-labelledby="welcome-heading" className="w-full">
          <div className="mb-9 max-w-2xl lg:mb-11">
            <p className="text-sm font-medium text-foreground/70">
              Exam Desk · CBSE Class 10 Science
            </p>
            <h1
              id="welcome-heading"
              className="mt-2 text-3xl font-semibold leading-9 tracking-[-0.01em] text-foreground"
            >
              Welcome, {welcomeName}.
            </h1>
            <p className="mt-2 text-base leading-7 text-foreground/70">
              Grow the question bank by upload or AI, then generate a paper from
              it.
            </p>
          </div>

          <PipelineDiagram />
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

type BankCountState =
  | { status: 'loading' }
  | { status: 'ready'; count: number }
  | { status: 'hidden' };

function useBankQuestionCount(): BankCountState {
  const [state, setState] = useState<BankCountState>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;
    fetchBankQuestions({ limit: 1 }, { clearAuthOnUnauthorized: false })
      .then((response) => {
        if (!cancelled) setState({ status: 'ready', count: response.count });
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'hidden' });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

type WireGeometry = {
  wires: string[];
  ports: Array<[number, number]>;
  arrow: string;
};

/** Cubic wire with horizontal tangents, like node-editor connections. */
function wirePath(x1: number, y1: number, x2: number, y2: number): string {
  const reach = Math.max(24, Math.min(90, (x2 - x1) * 0.55));
  return `M ${x1} ${y1} C ${x1 + reach} ${y1}, ${x2 - reach} ${y2}, ${x2} ${y2}`;
}

function PipelineDiagram() {
  const bankCount = useBankQuestionCount();
  const stageRef = useRef<HTMLDivElement>(null);
  const uploadRef = useRef<HTMLAnchorElement>(null);
  const aiQaRef = useRef<HTMLAnchorElement>(null);
  const bankRef = useRef<HTMLAnchorElement>(null);
  const generateRef = useRef<HTMLAnchorElement>(null);
  const [geometry, setGeometry] = useState<WireGeometry | null>(null);

  useEffect(() => {
    const stage = stageRef.current;
    const upload = uploadRef.current;
    const aiQa = aiQaRef.current;
    const bank = bankRef.current;
    const generate = generateRef.current;
    if (!stage || !upload || !aiQa || !bank || !generate) return;

    function compute() {
      if (!stage || !upload || !aiQa || !bank || !generate) return;
      const origin = stage.getBoundingClientRect();
      const box = (el: HTMLElement) => {
        const rect = el.getBoundingClientRect();
        return {
          left: rect.left - origin.left,
          right: rect.right - origin.left,
          cy: rect.top - origin.top + rect.height / 2,
        };
      };
      const u = box(upload);
      const a = box(aiQa);
      const b = box(bank);
      const g = box(generate);

      // Wires only make sense in the three-column layout; when the pipeline
      // stacks vertically the gaps collapse and the SVG stays empty.
      if (b.left - u.right < 16 || g.left - b.right < 16) {
        setGeometry(null);
        return;
      }

      setGeometry({
        wires: [
          wirePath(u.right, u.cy, b.left - 2, b.cy),
          wirePath(a.right, a.cy, b.left - 2, b.cy),
          wirePath(b.right, b.cy, g.left - 7, g.cy),
        ],
        ports: [
          [u.right, u.cy],
          [a.right, a.cy],
          [b.left, b.cy],
          [b.right, b.cy],
        ],
        arrow: `M ${g.left - 1} ${g.cy} L ${g.left - 8} ${g.cy - 4.5} L ${g.left - 8} ${g.cy + 4.5} Z`,
      });
    }

    compute();
    const observer = new ResizeObserver(compute);
    observer.observe(stage);
    observer.observe(upload);
    observer.observe(aiQa);
    observer.observe(bank);
    observer.observe(generate);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={stageRef}
      className="relative grid gap-5 lg:grid-cols-[minmax(240px,1fr)_minmax(230px,0.72fr)_minmax(250px,1fr)] lg:items-center"
    >
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-1">
        {SOURCE_WORKFLOWS.map((workflow) => (
          <WorkflowCard
            key={workflow.to}
            ref={workflow.to === '/upload' ? uploadRef : aiQaRef}
            workflow={workflow}
          />
        ))}
      </div>

      <div
        className="qpg-flow-node flex flex-col items-center justify-center gap-2"
        style={{ '--qpg-flow-order': 3 } as CSSProperties}
      >
        <ArrowDown
          className="size-4 text-muted-foreground/70 lg:hidden"
          aria-hidden="true"
        />
        <BankNode ref={bankRef} bankCount={bankCount} />
        <ArrowDown
          className="size-4 text-muted-foreground/70 lg:hidden"
          aria-hidden="true"
        />
      </div>

      <GenerateCard ref={generateRef} />

      {geometry && (
        <svg
          className="qpg-wire-layer pointer-events-none absolute inset-0 hidden h-full w-full lg:block"
          aria-hidden="true"
        >
          {geometry.wires.map((d) => (
            <path
              key={d}
              d={d}
              className="qpg-wire"
              fill="none"
              strokeWidth="1.5"
            />
          ))}
          {geometry.wires.map((d, index) => (
            <path
              key={`comet-${d}`}
              d={d}
              className="qpg-wire-comet"
              fill="none"
              strokeWidth="1.5"
              pathLength={100}
              style={{ animationDelay: `${index * -1.1}s` }}
            />
          ))}
          {geometry.ports.map(([x, y]) => (
            <circle
              key={`${x}-${y}`}
              cx={x}
              cy={y}
              r="2.5"
              className="qpg-wire-port"
            />
          ))}
          <path d={geometry.arrow} className="qpg-wire-arrow" />
        </svg>
      )}
    </div>
  );
}

function WorkflowCard({
  workflow,
  ref,
}: {
  workflow: (typeof SOURCE_WORKFLOWS)[number];
  ref: React.Ref<HTMLAnchorElement>;
}) {
  const Icon = workflow.icon;

  return (
    <Link
      ref={ref}
      to={workflow.to}
      style={{ '--qpg-flow-order': workflow.animationOrder } as CSSProperties}
      className="qpg-flow-card qpg-flow-node group flex min-h-[9.75rem] flex-col rounded-lg border bg-background p-5 transition-colors duration-200 ease-out hover:border-foreground/30 active:bg-secondary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary"
    >
      <div className="flex size-9 shrink-0 items-center justify-center rounded-md border bg-secondary/55 text-foreground transition-colors duration-200 group-hover:bg-foreground group-hover:text-background">
        <Icon className="size-[1.0625rem]" aria-hidden="true" />
      </div>

      <div className="mt-3 min-w-0">
        <h2 className="text-lg font-semibold leading-7 text-foreground">
          {workflow.title}
        </h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          {workflow.description}
        </p>
      </div>

      <div className="mt-auto flex w-full items-center justify-end gap-1 pt-4 text-xs font-medium leading-4 text-foreground/70">
        Open
        <ArrowRight
          className="size-3.5 shrink-0 text-foreground/55 transition-transform duration-200 group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </div>
    </Link>
  );
}

function BankNode({
  bankCount,
  ref,
}: {
  bankCount: BankCountState;
  ref: React.Ref<HTMLAnchorElement>;
}) {
  return (
    <Link
      ref={ref}
      to="/question-bank"
      className="qpg-flow-card group/bank relative flex flex-col items-center gap-1 rounded-lg border bg-background px-5 py-3.5 text-center transition-colors duration-200 ease-out hover:border-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary"
    >
      <Library
        className="size-4 text-muted-foreground transition-colors duration-200 group-hover/bank:text-foreground"
        aria-hidden="true"
      />
      <span className="text-[0.8125rem] font-semibold leading-4 text-foreground">
        Question bank
      </span>
      <span className="min-h-4 text-xs leading-4 text-muted-foreground">
        {bankCount.status === 'loading' && (
          <span
            className="inline-block h-3 w-16 animate-pulse rounded bg-secondary align-middle"
            aria-hidden="true"
          />
        )}
        {bankCount.status === 'ready' &&
          `${bankCount.count} ${bankCount.count === 1 ? 'question' : 'questions'}`}
      </span>
    </Link>
  );
}

function GenerateCard({ ref }: { ref: React.Ref<HTMLAnchorElement> }) {
  return (
    <Link
      ref={ref}
      to="/generate"
      style={{ '--qpg-flow-order': 4 } as CSSProperties}
      className="qpg-flow-node group flex min-h-[11rem] flex-col rounded-lg border border-primary bg-primary p-6 text-primary-foreground transition-colors duration-200 ease-out hover:bg-primary/90 active:bg-primary/85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary"
    >
      <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-primary-foreground/15 bg-primary-foreground/10">
        <FileText className="size-[1.0625rem]" aria-hidden="true" />
      </div>

      <div className="mt-3 min-w-0">
        <h2 className="text-xl font-semibold leading-7">Generate paper</h2>
        <p className="mt-1 text-sm leading-6 text-primary-foreground/75">
          Assemble a CBSE-style paper from your bank.
        </p>
      </div>

      <div className="mt-auto flex w-full items-center justify-end gap-1 pt-4 text-xs font-medium leading-4 text-primary-foreground/90">
        Start
        <ArrowRight
          className="size-3.5 shrink-0 text-primary-foreground/75 transition-transform duration-200 group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </div>
    </Link>
  );
}
