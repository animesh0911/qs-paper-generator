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
import type { ContentItem, PaperDocument } from './paper-document.schema';

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

export type SubjectArea = 'Chemistry' | 'Biology' | 'Physics' | (string & {});

export interface Chapter {
  id: number;
  slug: string;
  name: string;
  order: number;
  subject_area?: SubjectArea;
}

export interface AssembleRequest {
  title?: string;
  format_id?: string;
  chapter_slugs?: string[];
  difficulty?: 'easy' | 'standard' | 'hard';
}

export interface PaperFormatSummary {
  format_id: string;
  name: string;
  preset_name?: string;
  total_marks?: number;
  section_count?: number;
  question_count?: number;
  marks_by_question_type?: Record<string, number>;
}

export type PaperAnswerSource = 'source' | 'generated';

export interface PaperAnswerEntry {
  slotId: string;
  questionId: string;
  content: ContentItem[];
  source: PaperAnswerSource;
  modified: boolean;
}

export interface PaperAnswerDocument {
  schemaVersion: 'paper_answer_document.v1';
  paperId: string;
  answersBySlotId: Record<string, PaperAnswerEntry>;
}

export interface EditorDraftResponse {
  document: PaperDocument;
  answer_document: PaperAnswerDocument;
  status: string;
}

export type GenerationBatchStatus =
  | 'queued'
  | 'generating_questions'
  | 'validating'
  | 'ready_for_review'
  | 'accepted'
  | 'failed'
  | 'expired'
  | 'discarded';

export type GenerationDifficultyLabel = 'Easy' | 'Standard' | 'Challenging';

export interface ChapterTopicNode {
  id: string;
  type: string;
  title: string;
  parent_id: string | null;
  source_element_id: string | null;
  source_range: { start: number; end: number };
  page_range: { start: number; end: number };
  element_count: number;
  preview: string;
}

export interface ChapterTopicsResponse {
  chapter: Chapter;
  document: {
    id: number;
    chapter: Chapter;
    source_file_name: string;
    page_count: number;
  } | null;
  topics: ChapterTopicNode[];
}

export interface GenerationBatchCreateRequest {
  chapter_slugs: string[];
  chapter_map_node_ids?: string[];
  topic_names?: string[];
  difficulty_preset: string;
}

export interface GenerationBatch {
  id: number;
  status: GenerationBatchStatus;
  chapter_slugs: string[];
  chapter_map_node_ids: string[];
  topic_names: string[];
  difficulty_preset: string;
  requested_count: number;
  candidate_count: number;
  error: string;
  ready_at: string | null;
  accepted_at: string | null;
  expired_at: string | null;
  discarded_at: string | null;
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
    stem?: GeneratedQuestionContentItem[];
    options?: {
      label?: string;
      text?: string;
      content?: GeneratedQuestionContentItem[];
    }[];
    [key: string]: unknown;
  };
  topic_names?: string[];
  answer?: string;
  source?: Record<string, unknown>;
  grounding_manifest?: unknown;
  grounding_context?: unknown;
  [key: string]: unknown;
}

export interface GeneratedQuestionContentItem {
  type?: string;
  text?: string;
  latex?: string;
  caption?: string;
  rows?: string[][];
  assetId?: string;
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

/**
 * Provenance of an uploaded PDF, stored on every extracted question. Mirrors
 * the backend `bank.models.SourceType` choices.
 */
export type SourceType =
  | 'previous_year_paper'
  | 'sample_paper'
  | 'question_bank';

/**
 * Lifecycle of an out-of-request PDF ingestion. `pending`/`running` are polled;
 * `done`/`failed` are terminal. Mirrors `bank.models.IngestionJobStatus`.
 */
export type IngestionJobStatus = 'pending' | 'running' | 'done' | 'failed';

/**
 * The job-status shape the frontend polls after uploading a PDF. The stored PDF
 * itself is never exposed. Mirrors `bank.serializers.IngestionJobSerializer`.
 */
export interface IngestionJob {
  id: number;
  status: IngestionJobStatus;
  source_type: SourceType;
  source_file_name: string;
  created_count: number;
  skipped_count: number;
  error: string;
  created_at: string;
  updated_at: string;
}
