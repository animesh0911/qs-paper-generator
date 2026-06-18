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
