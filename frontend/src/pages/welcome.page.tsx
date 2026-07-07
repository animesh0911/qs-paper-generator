/**
 * Authenticated welcome screen.
 *
 * Presents the product pipeline as a calm exam-desk map: Upload Papers and
 * AI Q&A feed the Question Bank, and Generate Paper opens the editor. Desktop
 * wires are measured from rendered card positions so the animation stays
 * attached to the cards at every viewport width; below `lg` the flow stacks.
 *
 * @module WelcomePage
 */
import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ArrowDown,
  ArrowRight,
  BookOpenText,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FilePlus2,
  FileText,
  Library,
  PencilLine,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { fetchBankQuestions } from '@/lib/api';

const SOURCE_WORKFLOWS = [
  {
    to: '/upload',
    title: 'Upload Papers',
    description: 'Extract questions from any PDF or past-paper document.',
    icon: FilePlus2,
    animationOrder: 1,
  },
  {
    to: '/ai-qa',
    title: 'AI Q&A',
    description: 'Generate questions and answers from a selected topic with AI.',
    icon: Sparkles,
    animationOrder: 2,
  },
] as const;

export default function WelcomePage() {
  const location = useLocation();
  const welcomeName = resolveWelcomeName(location.state);

  return (
    <div className="qpg-welcome-shell min-h-screen bg-secondary text-foreground">
      <WelcomeHeader welcomeName={welcomeName} />
      <main className="relative z-10 w-full px-6 py-10 sm:px-10 lg:px-16 lg:py-12 xl:px-[6.75rem]">
        <section aria-labelledby="welcome-heading" className="w-full">
          <div className="mb-9 max-w-3xl sm:mb-10 lg:mb-11">
            <p className="text-sm font-medium leading-6 text-slate-500">
              Exam Desk · CBSE Class 10 Science
            </p>
            <h1
              id="welcome-heading"
              className="mt-2.5 text-[1.875rem] font-semibold leading-[1.12] tracking-[-0.02em] text-slate-950 text-balance sm:text-[2.125rem] lg:text-4xl"
            >
              Welcome, {welcomeName}.
            </h1>
          </div>

          <PipelineDiagram />
        </section>
      </main>
    </div>
  );
}

function WelcomeHeader({ welcomeName }: { welcomeName: string }) {
  return (
    <header className="qpg-welcome-header relative z-20 border-b border-slate-200/80 bg-white/95 backdrop-blur">
      <div className="flex h-[4.75rem] items-center justify-between gap-4 px-6 sm:px-10 lg:px-16 xl:px-[4.25rem]">
        <Link
          to="/"
          className="group flex min-w-0 items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          aria-label="Exam Desk home"
        >
          <span className="qpg-home-logo flex size-10 shrink-0 items-center justify-center rounded-[0.625rem] bg-slate-950 text-white transition-transform duration-200 ease-out group-hover:-translate-y-0.5">
            <BookOpenText className="size-5" aria-hidden="true" />
          </span>
          <span className="truncate text-lg font-semibold tracking-[-0.015em] text-slate-950">
            Exam Desk
          </span>
        </Link>

        <div className="flex items-center justify-end gap-3 text-slate-500 sm:gap-5">
          <button
            type="button"
            className="inline-flex size-10 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            aria-label="Help"
          >
            <CircleHelp className="size-5" aria-hidden="true" />
          </button>
          <div className="flex items-center gap-2.5 rounded-full py-1 pl-1 pr-1.5 text-sm font-medium text-slate-600">
            <span className="flex size-10 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500">
              <UserRound className="size-5" aria-hidden="true" />
            </span>
            <span className="hidden max-w-32 truncate sm:inline">
              {welcomeName}
            </span>
            <ChevronDown className="hidden size-4 text-slate-400 sm:block" aria-hidden="true" />
          </div>
        </div>
      </div>
    </header>
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
  const reach = Math.max(30, Math.min(110, (x2 - x1) * 0.58));
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
      if (b.left - u.right < 18 || g.left - b.right < 18) {
        setGeometry(null);
        return;
      }

      setGeometry({
        wires: [
          wirePath(u.right, u.cy, b.left - 2, b.cy),
          wirePath(a.right, a.cy, b.left - 2, b.cy),
          wirePath(b.right, b.cy, g.left - 8, g.cy),
        ],
        ports: [
          [u.right, u.cy],
          [a.right, a.cy],
          [b.left, b.cy],
          [b.right, b.cy],
        ],
        arrow: `M ${g.left - 1} ${g.cy} L ${g.left - 11} ${g.cy - 6} L ${g.left - 11} ${g.cy + 6} Z`,
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
      className="relative isolate grid gap-5 lg:grid-cols-[minmax(20rem,0.9fr)_minmax(13rem,0.48fr)_minmax(23rem,1fr)] lg:items-center lg:gap-7 xl:grid-cols-[24.5rem_13rem_28rem] xl:gap-20"
    >
      <div className="relative z-10 grid gap-5 lg:gap-6">
        {SOURCE_WORKFLOWS.map((workflow) => (
          <WorkflowCard
            key={workflow.to}
            ref={workflow.to === '/upload' ? uploadRef : aiQaRef}
            workflow={workflow}
          />
        ))}
      </div>

      <div
        className="qpg-flow-node relative z-10 flex flex-col items-center justify-center gap-3"
        style={{ '--qpg-flow-order': 3 } as CSSProperties}
      >
        <ArrowDown
          className="size-5 text-slate-400 lg:hidden"
          aria-hidden="true"
        />
        <BankNode ref={bankRef} bankCount={bankCount} />
        <ArrowDown
          className="size-5 text-slate-400 lg:hidden"
          aria-hidden="true"
        />
      </div>

      <GenerateCard ref={generateRef} />

      {geometry && (
        <svg
          className="qpg-wire-layer pointer-events-none absolute inset-0 z-0 hidden h-full w-full lg:block"
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
              strokeWidth="2.75"
              pathLength={100}
              style={{ animationDelay: `${index * -0.95}s` }}
            />
          ))}
          {geometry.ports.map(([x, y]) => (
            <circle
              key={`${x}-${y}`}
              cx={x}
              cy={y}
              r="3"
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
      className="qpg-flow-card qpg-source-card qpg-flow-node group/bank relative z-10 flex min-h-[9.75rem] items-center gap-4 rounded-xl bg-white/72 p-5 backdrop-blur-md transition-colors duration-200 ease-out hover:border-slate-300 hover:bg-white/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary sm:p-6"
    >
      <span className="flex size-14 shrink-0 items-center justify-center rounded-xl border border-slate-200/80 bg-white/58 text-slate-950 backdrop-blur-sm transition-colors duration-200 group-hover/bank:bg-white/90">
        <Icon className="size-6" aria-hidden="true" />
      </span>

      <span className="min-w-0 flex-1">
        <span className="block text-base font-semibold leading-6 tracking-[-0.015em] text-slate-950">
          {workflow.title}
        </span>
        <span className="mt-2 block max-w-[17rem] text-sm leading-6 text-slate-500 text-pretty">
          {workflow.description}
        </span>
        <span className="mt-5 inline-flex items-center gap-2.5 text-sm font-medium text-slate-950">
          Open
          <ArrowRight
            className="size-4 text-slate-700 transition-transform duration-200 group-hover/bank:translate-x-1"
            aria-hidden="true"
          />
        </span>
      </span>

      <ChevronRight
        className="size-5 shrink-0 text-slate-500 transition-transform duration-200 group-hover/bank:translate-x-1 group-hover/bank:text-slate-800"
        aria-hidden="true"
      />
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
      className="qpg-flow-card qpg-bank-node group/bank relative z-10 flex w-full max-w-[13rem] flex-col items-center rounded-xl bg-white/74 px-5 py-5 text-center backdrop-blur-md transition-colors duration-200 ease-out hover:border-slate-300 hover:bg-white/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary"
    >
      <span className="flex size-12 items-center justify-center rounded-xl border border-slate-200/80 bg-white/58 text-slate-950 backdrop-blur-sm transition-colors duration-200 group-hover/bank:bg-white/90">
        <Library className="size-6" aria-hidden="true" />
      </span>
      <span className="mt-4 text-base font-semibold leading-6 tracking-[-0.015em] text-slate-950">
        Question Bank
      </span>
      <span className="mt-0.5 min-h-5 text-sm font-medium leading-5 text-blue-700">
        {bankCount.status === 'loading' && (
          <span
            className="inline-block h-3.5 w-24 animate-pulse rounded-full bg-slate-200 align-middle"
            aria-label="Loading question count"
          />
        )}
        {bankCount.status === 'ready' &&
          `${bankCount.count} ${bankCount.count === 1 ? 'question' : 'questions'}`}
        {bankCount.status === 'hidden' && 'Source library'}
      </span>
      <span className="mt-3 h-px w-full bg-slate-200/80" aria-hidden="true" />
      <span className="mt-3 text-xs leading-5 text-slate-500 text-pretty">
        Built from uploaded papers and AI-generated content.
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
      className="qpg-generate-card qpg-flow-node group relative z-10 flex min-h-[20.5rem] flex-col overflow-hidden rounded-xl border border-white/10 bg-slate-950/90 p-6 text-white backdrop-blur-md transition-transform duration-200 ease-out hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary lg:h-[23.25rem] lg:p-8"
    >
      <span className="relative z-10 flex size-12 items-center justify-center rounded-xl border border-white/15 bg-white/10 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
        <FileText className="size-6" aria-hidden="true" />
      </span>

      <span className="relative z-10 mt-6 block min-w-0">
        <span className="block text-[1.375rem] font-semibold leading-8 tracking-[-0.02em] text-white">
          Generate Paper
        </span>
        <span className="mt-2 block max-w-[20rem] text-base leading-6 text-slate-300 text-pretty">
          Create a paper from your question bank and open it in the editor.
        </span>
      </span>

      <span className="relative z-10 mt-4 inline-flex w-fit items-center gap-2 rounded-lg border border-white/10 bg-white/10 px-3 py-1.5 text-sm font-medium leading-5 text-white/90 backdrop-blur-sm">
        <PencilLine className="size-4" aria-hidden="true" />
        Opens BlockNote editor
      </span>

      <span
        className="relative z-10 mt-5 h-px w-full bg-white/15"
        aria-hidden="true"
      />
      <span className="relative z-10 mt-4 block max-w-[23rem] text-sm leading-6 text-slate-300 text-pretty">
        Swap alternate questions, rearrange sections, and finalize the paper
        manually.
      </span>

      <span className="relative z-10 mt-auto flex w-full items-center justify-end gap-3 pt-5 text-base font-semibold leading-7 text-white">
        Start
        <ArrowRight
          className="size-6 text-white/85 transition-transform duration-200 group-hover:translate-x-1.5"
          aria-hidden="true"
        />
      </span>
    </Link>
  );
}
