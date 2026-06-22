/**
 * Frontend type exports.
 *
 * `PaperDocumentV1` types are inferred from the runtime Zod contract schema so
 * the API validation surface and TypeScript surface cannot drift independently.
 * Request and dashboard helper types that are not part of `PaperDocumentV1`
 * remain here.
 *
 * @module types
 */
export type {
  ChoiceGroup,
  ChoiceOption,
  ContentItem,
  DocPaper,
  DocQuestion,
  DocQuestionContent,
  DocSection,
  DocSlot,
  EditableTextBlock,
  PaperDocument,
  PaperFormat,
  PaperRequest,
  PaperTemplate,
  QuestionMetadata,
  QuestionSource,
  QuestionType,
  SlotEditCapabilities,
  SlotOverrides,
  SubQuestion,
} from './paper-document.schema';

export type {
  EditPatch,
  EditProposal,
  GuardId,
  GuardViolation,
  ProposalResponse,
  ProposalValidation,
  Refusal,
} from './ai-proposal.schema';

export interface Chapter {
  id: number;
  slug: string;
  name: string;
  order: number;
}

export interface AssembleRequest {
  title?: string;
  format_id?: string;
  chapter_slugs?: string[];
  weights?: Record<string, number>;
  difficulty?: 'easy' | 'standard' | 'hard';
}

export interface PaperFormatSummary {
  format_id: string;
  name: string;
}

export type GenerationBatchStatus =
  | 'queued'
  | 'generating_questions'
  | 'validating'
  | 'ready_for_review'
  | 'accepted'
  | 'failed'
  | 'expired';

export type GenerationDifficultyLabel = 'Easy' | 'Standard' | 'Challenging';

export interface GenerationBatchCreateRequest {
  chapter_slugs: string[];
  topic_names?: string[];
  difficulty_preset: string;
}

export interface GenerationBatch {
  id: number;
  status: GenerationBatchStatus;
  chapter_slugs: string[];
  topic_names: string[];
  difficulty_preset: string;
  requested_count: number;
  candidate_count: number;
  error: string;
  ready_at: string | null;
  accepted_at: string | null;
  expired_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GeneratedQuestionPayload {
  chapter_slug?: string;
  qtype?: string;
  marks?: number;
  cognitive_level?: string;
  raw_text?: string;
  content?: {
    stem?: { text?: string }[];
    [key: string]: unknown;
  };
  topic_names?: string[];
  answer?: string;
  source?: Record<string, unknown>;
  grounding_manifest?: unknown;
  grounding_context?: unknown;
  [key: string]: unknown;
}

export interface GeneratedQuestionCandidate {
  id: number;
  status: string;
  payload: GeneratedQuestionPayload;
  grounding_manifest?: unknown;
  question_id: number | null;
  accepted_at: string | null;
  rejected_at?: string | null;
  created_at: string;
  updated_at: string;
}
