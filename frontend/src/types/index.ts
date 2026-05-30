/**
 * TypeScript mirrors of the backend's response shapes.
 *
 * Source of truth:
 * - `PaperDocument` mirrors `docs/Varad/v1_contract.md`.
 * - `AssembleRequest` mirrors `AssembleRequestSerializer` input.
 *
 * If the contract doc or backend serializer changes, update this module in the
 * same PR.
 *
 * @module types
 */
export interface Chapter {
  id: number;
  slug: string;
  name: string;
  order: number;
}

// PaperDocumentV1 — returned by POST /api/papers/assemble
export type QuestionType =
  | 'mcq'
  | 'assertion_reason'
  | 'very_short_answer'
  | 'short_answer'
  | 'long_answer'
  | 'case_based'
  | 'internal_choice'
  | 'diagram_based'
  | 'table_based'
  | 'custom';

export interface ContentItem {
  type: string;
  text?: string;
  latex?: string;
  assetId?: string;
  caption?: string;
  rows?: string[][];
}

export interface ChoiceOption {
  label: string;
  marks?: number;
  content: ContentItem[];
}

export interface ChoiceGroup {
  displayStyle: 'or' | 'choose_any';
  chooseCount: number;
  options: ChoiceOption[];
}

export interface SubQuestion {
  label: string;
  marks?: number;
  content: ContentItem[];
}

export interface DocQuestionContent {
  stem?: ContentItem[];
  assertion?: ContentItem[];
  reason?: ContentItem[];
  passage?: ContentItem[];
  options?: ChoiceOption[];
  subparts?: SubQuestion[];
  choices?: ChoiceGroup[];
}

export interface QuestionMetadata {
  classLevel: string;
  subject: string;
  subjectArea?: string;
  chapterIds?: string[];
  chapterNames: string[];
  topicIds?: string[];
  topicNames?: string[];
  difficulty: string;
  cognitiveLevel?: string;
  cbseRelevance?: 'low' | 'medium' | 'high' | number;
  estimatedMinutes?: number;
  requiresDiagram?: boolean;
  requiresCalculation?: boolean;
  requiresTable?: boolean;
  keywords?: string[];
}

export interface QuestionSource {
  sourceType: string;
  sourceName: string;
  fileName?: string;
  pageNumber?: number;
  originalQuestionNumber?: string;
}

export interface DocQuestion {
  questionId: string;
  language: string;
  marks: number;
  questionType: QuestionType;
  rawText: string;
  content: DocQuestionContent;
  metadata: QuestionMetadata;
  source: QuestionSource;
}

export interface SlotOverrides {
  modifiedFromSource: boolean;
  regions: Record<string, ContentItem[]>;
}

export interface DocSlot {
  slotId: string;
  displayNumber: string;
  marks: number;
  questionType: QuestionType;
  selectedQuestionId: string | null;
  locked: boolean;
  alternateQuestionIds: string[];
  orGroup?: number;
  overrides?: SlotOverrides;
}

export interface DocSection {
  sectionId: string;
  title: string;
  subtitle?: string;
  marks: number;
  instructions?: string;
  slots: DocSlot[];
}

export interface DocPaper {
  paperId: string;
  title: string;
  subtitle?: string;
  totalMarks: number;
  durationMinutes: number;
  language: string;
  headerBlocks?: EditableTextBlock[];
  instructionBlocks?: EditableTextBlock[];
  sections: DocSection[];
}

export interface PaperRequest {
  requestId: string;
  language: string;
  classLevel: string;
  subject: string;
  examType: string;
  filters: {
    chapters: string[];
    topics?: string[];
    englishOnly: boolean;
    difficultyMix?: Record<string, number>;
  };
}

export interface PaperTemplate {
  templateId: string;
  templateName: string;
  board?: string;
  classLevel: string;
  subject: string;
  examType: string;
  totalMarks: number;
  durationMinutes: number;
  language: string;
}

export interface PaperFormat {
  formatId: string;
  page: {
    size: string;
    orientation: string;
  };
  paperChrome: {
    showOuterBorder: boolean;
    sectionStyle: string;
    marksPlacement: string;
  };
  numbering: {
    scope: string;
    style: string;
    recomputeOnSectionReorder: boolean;
  };
  sections: {
    allowQuestionReorderWithinSection: boolean;
    allowCrossSectionMove: boolean;
  };
  questionRegions: {
    allowRegionReorder: boolean;
    allowRegionDelete: boolean;
  };
  mcqOptions: {
    layout: string;
  };
}

export interface EditableTextBlock {
  blockId: string;
  blockType: string;
  text: string;
  editable?: boolean;
}

export interface PaperDocument {
  schemaVersion: string;
  request: PaperRequest;
  template: PaperTemplate;
  format: PaperFormat;
  paper: DocPaper;
  questions: DocQuestion[];
}

export interface AssembleRequest {
  title?: string;
  preset?: string;
  chapter_slugs?: string[];
  weights?: Record<string, number>;
  difficulty?: 'easy' | 'standard' | 'hard';
}
