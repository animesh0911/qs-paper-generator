/**
 * Bottom assistant chat surface for the paper editor.
 *
 * Renders the persistent floating assistant: a capability helper line, the
 * review result card, and the chat input. It is purely presentational — the
 * mocked review state machine lives in `useAssistantChat`.
 *
 * Patterns:
 * - Carries `data-editor-chrome` so print/export styling removes it without
 *   touching paper content; it never overlays the paper sheet.
 * - Action buttons (Apply / Dismiss) render only once a result is `complete`,
 *   matching the live AI result card slots (#34). In this scaffold Apply and
 *   the chat Send are present but disabled — no model call exists yet.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `src/hooks/useAssistantChat.hook.ts`, `src/components/ui/button`.
 *
 * @module AssistantChat
 */
import type { RefObject } from 'react';
import { CheckCircle2, Loader2, MessageSquareText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type {
  AssistantResult,
  AssistantStatus,
} from '@/hooks/useAssistantChat.hook';

const HELPER_COPY =
  'The assistant can explain, review, and suggest — it can’t rewrite sourced question text.';

const SEND_DISABLED_TITLE =
  'Live chat replies arrive with AI integration. Use Review paper for a sample result.';

const APPLY_DISABLED_TITLE =
  'Applying review fixes arrives with live AI review.';

export function AssistantChat({
  status,
  result,
  chatValue,
  selectedSlotLabel,
  inputRef,
  onChatChange,
  onApply,
  onDismiss,
}: {
  status: AssistantStatus;
  result: AssistantResult | null;
  chatValue: string;
  selectedSlotLabel?: string;
  inputRef: RefObject<HTMLInputElement | null>;
  onChatChange: (value: string) => void;
  onApply: () => void;
  onDismiss: () => void;
}) {
  return (
    <div
      data-editor-chrome
      className="editor-chat-footer fixed bottom-3 left-1/2 z-30 w-[min(calc(100vw-2rem),48rem)] -translate-x-1/2"
    >
      <div className="space-y-2 rounded-lg border bg-background/95 p-2 shadow-[0_8px_24px_rgba(15,23,42,0.12)] backdrop-blur">
        {status !== 'idle' && (
          <AssistantResultCard
            status={status}
            result={result}
            onApply={onApply}
            onDismiss={onDismiss}
          />
        )}

        <p className="px-1 text-xs text-muted-foreground">{HELPER_COPY}</p>

        <div className="flex items-center gap-3">
          <MessageSquareText
            className="h-5 w-5 flex-none text-muted-foreground"
            aria-hidden="true"
          />
          <input
            ref={inputRef}
            aria-label="Ask about this paper"
            className={cn(
              'min-w-0 flex-1 bg-transparent px-1 text-sm outline-none',
              'placeholder:text-muted-foreground',
            )}
            value={chatValue}
            placeholder={
              selectedSlotLabel
                ? `Ask about question ${selectedSlotLabel}`
                : 'Ask about this paper'
            }
            onChange={(event) => onChatChange(event.target.value)}
          />
          <Button size="sm" disabled title={SEND_DISABLED_TITLE}>
            Ask
          </Button>
        </div>
      </div>
    </div>
  );
}

function AssistantResultCard({
  status,
  result,
  onApply,
  onDismiss,
}: {
  status: AssistantStatus;
  result: AssistantResult | null;
  onApply: () => void;
  onDismiss: () => void;
}) {
  return (
    <section
      aria-label="Assistant review result"
      className="rounded-md border bg-secondary/40 p-3"
    >
      {status === 'pending' || !result ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Reviewing this paper…
        </p>
      ) : (
        <>
          <div className="flex items-start gap-2">
            <CheckCircle2
              className="mt-0.5 h-4 w-4 flex-none text-foreground"
              aria-hidden="true"
            />
            <div className="min-w-0 space-y-0.5">
              <p className="text-sm font-medium leading-5">
                {result.summary[0]}
              </p>
              <p className="text-sm leading-5 text-muted-foreground">
                {result.summary[1]}
              </p>
            </div>
          </div>

          {result.affected.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-muted-foreground">Affected:</span>
              {result.affected.map((area) => (
                <span
                  key={area.id}
                  className="rounded-full border bg-background px-2 py-0.5 text-xs"
                >
                  {area.label}
                </span>
              ))}
            </div>
          )}

          <div className="mt-3 flex justify-end gap-2">
            {result.canApply && (
              <Button
                variant="outline"
                size="sm"
                disabled
                title={APPLY_DISABLED_TITLE}
                onClick={onApply}
              >
                Apply fix
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={onDismiss}>
              Dismiss
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
