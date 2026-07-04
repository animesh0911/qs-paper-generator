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
  preferred_source_keys?: string[];
}

export interface PaperSourceSummary {
  key: string;
  kind: 'bank_source' | 'upload' | 'ai_session';
  title: string;
  detail: string;
  question_count: number;
  matching_question_count?: number;
  created_at: string;
  status: string;
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
  count?: number;
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
  | 'question_bank'
  | 'ai_generated';

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
  /** Live extraction progress while `running` (0 until the drainer plans it). */
  total_pages: number;
  pages_done: number;
  created_count: number;
  skipped_count: number;
  error: string;
  created_at: string;
  updated_at: string;
}

export type AnswerGenerationJobStatus =
  | 'pending'
  | 'running'
  | 'done'
  | 'failed';

export interface AnswerGenerationJob {
  id: number;
  ingestion_job_id: number;
  status: AnswerGenerationJobStatus;
  total_count: number;
  generated_count: number;
  skipped_count: number;
  error: string;
  created_at: string;
  updated_at: string;
}

export interface GeneratedAnswer {
  question_id: number;
  answer: string;
  answer_source: string;
}

export interface IngestionAnswersResponse {
  job: AnswerGenerationJob | null;
  answers: GeneratedAnswer[];
}

/**
 * A bank question as surfaced by the browsable Question Bank view. Mirrors
 * `bank.serializers.BankQuestionSerializer`. The `answer` is never exposed.
 */
export interface BankQuestion {
  id: number;
  section: string;
  qtype: string;
  marks: number;
  chapter: Chapter | null;
  cognitive_level: string;
  text: string;
  /**
   * Structured PaperDocumentV1 `content` (stem, options, etc.). The `stem`
   * items may carry LaTeX, rendered with KaTeX in the bank view. Empty dict
   * means "no structured content" — fall back to `text`.
   */
  content: { stem?: ContentItem[]; [key: string]: unknown };
  options: { label: string; text: string }[];
  primary_form: string;
  topic_names: string[];
  parse_quality: string;
  review_flags: string[];
  verified: boolean;
  source_type: SourceType | '';
  source_name: string;
  source_file_name: string;
  created_at: string;
}

/** Filters accepted by `GET /api/bank/questions/`. All optional. */
export interface BankQuestionFilters {
  chapter?: string;
  section?: string;
  qtype?: string;
  source_type?: SourceType;
  /** A specific paper's `source_name` (see `GET /api/bank/question-sources/`). */
  source?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

/** One selectable source paper, from `GET /api/bank/question-sources/`. */
export interface BankQuestionSource {
  value: string;
  label: string;
  count: number;
}

/** Paginated response shape from `GET /api/bank/questions/`. */
export interface BankQuestionsResponse {
  count: number;
  limit: number;
  offset: number;
  results: BankQuestion[];
}
