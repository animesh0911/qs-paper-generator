/**
 * Focused schema-aware BlockNote overlay for one paper Slot Question.
 *
 * Overlay changes stay transient until `Use this question`. Unsupported
 * freeform blocks or invalid Question shapes are rejected without changing the
 * paper-local canonical state.
 *
 * @module QuestionEditOverlay
 */
import { useMemo, useRef, useState } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import { AlertTriangle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { DocQuestion, DocQuestionContent } from '@/types';
import {
  questionToSemanticBlocks,
  semanticBlocksToQuestionContent,
  type QuestionSemanticBlock,
  type QuestionSemanticBlockType,
} from '@/lib/question-editing';
import { questionBlockNoteSchema } from '@/lib/question-blocknote-schema';

const semanticTypes = new Set<QuestionSemanticBlockType>([
  'qpgStem',
  'qpgPassage',
  'qpgAssertion',
  'qpgReason',
  'qpgOption',
  'qpgSubpart',
  'qpgChoiceOption',
  'qpgImage',
  'qpgTable',
  'qpgEquation',
]);

export function QuestionEditOverlay({
  displayNumber,
  question,
  content,
  onApply,
  onClose,
}: {
  displayNumber: string;
  question: DocQuestion;
  content: DocQuestionContent;
  onApply: (content: DocQuestionContent) => void;
  onClose: () => void;
}) {
  const [error, setError] = useState('');
  const initialBlocks = useMemo(
    () =>
      questionToSemanticBlocks({ ...question, content }).map((block) => ({
        type: block.type,
        props: block.props,
        content: block.content,
      })),
    [content, question],
  );
  const editor = useCreateBlockNote(
    {
      schema: questionBlockNoteSchema,
      animations: false,
      initialContent: initialBlocks,
    },
    [question.id],
  );
  const originalDocument = useRef(JSON.stringify(editor.document));

  function closeOverlay() {
    if (
      JSON.stringify(editor.document) !== originalDocument.current &&
      !window.confirm('Discard changes to this question?')
    ) {
      return;
    }
    onClose();
  }

  function applyDraft() {
    const convertedBlocks = editor.document.map(blockToSemanticBlock);
    if (convertedBlocks.some((block) => block === undefined)) {
      rejectDraft(
        'Editing the question this way is not supported yet. Reverting back to the original question.',
      );
      return;
    }
    const blocks = convertedBlocks.filter(
      (block): block is QuestionSemanticBlock => block !== undefined,
    );
    const result = semanticBlocksToQuestionContent(
      question.type,
      blocks,
      content,
    );
    if (!result.ok) {
      rejectDraft(result.message);
      return;
    }
    onApply(result.content);
  }

  function rejectDraft(message: string) {
    editor.replaceBlocks(editor.document, initialBlocks);
    originalDocument.current = JSON.stringify(editor.document);
    setError(message);
  }

  function addCollectionEntry() {
    const collection = editableCollection(question.type);
    if (!collection || editor.document.length === 0) return;
    const semanticBlocks = editor.document
      .map(blockToSemanticBlock)
      .filter((block): block is QuestionSemanticBlock => block !== undefined);
    const matching = semanticBlocks.filter(
      (block) => block.props.region === collection.region,
    );
    const label =
      collection.region === 'subpart'
        ? String(new Set(matching.map((block) => block.props.label)).size + 1)
        : nextAlphaLabel(matching.map((block) => block.props.label));
    const groupIndex =
      collection.region === 'choice'
        ? (matching.at(-1)?.props.groupIndex ?? 0)
        : -1;
    const block: QuestionSemanticBlock = {
      type: collection.type,
      props: {
        regionKey:
          collection.region === 'choice'
            ? `choice:${groupIndex}:${label}`
            : `${collection.region}:${label}`,
        region: collection.region,
        label,
        groupIndex,
        marks: -1,
        itemJson: JSON.stringify({ type: 'paragraph', text: '' }),
      },
      content: '',
    };
    editor.insertBlocks(
      [{ type: block.type, props: block.props, content: block.content }],
      editor.document.at(-1)!,
      'after',
    );
  }

  const collection = editableCollection(question.type);

  return (
    <div
      data-editor-chrome
      className="editor-question-edit-overlay fixed inset-0 z-50 bg-foreground/45 p-4 max-sm:p-0"
      role="dialog"
      aria-modal="true"
      aria-labelledby="question-edit-title"
    >
      <div className="mx-auto flex h-full max-w-5xl flex-col overflow-hidden rounded-lg bg-background shadow-[0_6px_8px_rgba(15,23,42,0.16)] max-sm:rounded-none">
        <header className="flex items-start justify-between gap-3 border-b px-5 py-4">
          <div>
            <p className="text-xs text-muted-foreground">
              Question {displayNumber}
            </p>
            <h2 id="question-edit-title" className="mt-1 text-lg font-semibold">
              Edit question
            </h2>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span className="rounded-sm bg-secondary px-2 py-1">
                {question.type.replace(/_/g, ' ')}
              </span>
              <span className="rounded-sm bg-secondary px-2 py-1">
                {question.defaultMarks}{' '}
                {question.defaultMarks === 1 ? 'mark' : 'marks'}
              </span>
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label="Close question editor"
            onClick={closeOverlay}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </header>
        {collection && initialBlocks.length > 0 && (
          <div className="flex justify-end border-b px-5 py-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addCollectionEntry}
            >
              Add {collection.label}
            </Button>
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-auto p-5">
          {initialBlocks.length > 0 ? (
            <BlockNoteView
              editor={editor}
              theme="light"
              editable
              slashMenu={false}
              filePanel={false}
              tableHandles={false}
              emojiPicker={false}
              comments={false}
              className="qpg-question-edit-overlay"
            />
          ) : (
            <p className="rounded-md border bg-secondary p-4 text-sm">
              This question can be reviewed, but editing is not available for
              this type yet.
            </p>
          )}
          {error && (
            <div
              role="alert"
              className="mt-4 flex gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm"
            >
              <AlertTriangle
                className="mt-0.5 h-4 w-4 flex-none"
                aria-hidden="true"
              />
              {error}
            </div>
          )}
        </div>
        <footer className="flex justify-end gap-2 border-t px-5 py-4">
          <Button type="button" variant="outline" onClick={closeOverlay}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={initialBlocks.length === 0}
            onClick={applyDraft}
          >
            Use this question
          </Button>
        </footer>
      </div>
    </div>
  );
}

function editableCollection(type: DocQuestion['type']) {
  if (type === 'mcq' || type === 'assertion_reason') {
    return {
      region: 'option',
      type: 'qpgOption',
      label: 'option',
    } as const;
  }
  if (
    type === 'short_answer' ||
    type === 'long_answer' ||
    type === 'case_based'
  ) {
    return {
      region: 'subpart',
      type: 'qpgSubpart',
      label: 'subpart',
    } as const;
  }
  if (type === 'internal_choice') {
    return {
      region: 'choice',
      type: 'qpgChoiceOption',
      label: 'choice',
    } as const;
  }
  return undefined;
}

function nextAlphaLabel(labels: string[]) {
  const used = new Set(labels.map((label) => label.toUpperCase()));
  for (let code = 65; code <= 90; code += 1) {
    const label = String.fromCharCode(code);
    if (!used.has(label)) return label;
  }
  return String(labels.length + 1);
}

function blockToSemanticBlock(
  blockValue: unknown,
): QuestionSemanticBlock | undefined {
  const block = blockValue as {
    type: string;
    props: QuestionSemanticBlock['props'];
    content: unknown;
  };
  if (!semanticTypes.has(block.type as QuestionSemanticBlockType)) {
    return undefined;
  }
  const props = block.props as QuestionSemanticBlock['props'];
  return {
    type: block.type as QuestionSemanticBlockType,
    props,
    content: blockContentToText(block.content),
  };
}

function blockContentToText(content: unknown) {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  return content
    .map((item) => {
      if (
        item &&
        typeof item === 'object' &&
        'text' in item &&
        typeof item.text === 'string'
      ) {
        return item.text;
      }
      return '';
    })
    .join('');
}
