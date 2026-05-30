/**
 * Zod runtime schema for `PaperDocumentV1` — the response shape of
 * `POST /api/papers/assemble`.
 *
 * Mirrors `docs/Varad/v1_contract.md`. Parsed at the API boundary so a
 * backend/frontend contract drift surfaces as a loud error at first call
 * instead of a blank screen downstream.
 *
 * Why a runtime check exists in addition to TypeScript types: TS only
 * verifies that calling code trusts its own annotations. It does not
 * verify that the actual JSON returned by the server matches them.
 * Commit b6384db shipped a backend shape change with no frontend update
 * and no test failed — Zod parsing closes that gap.
 */
import { z } from 'zod';

const contentItemSchema = z
  .object({
    type: z.string(),
    text: z.string().optional(),
    latex: z.string().optional(),
    assetId: z.string().optional(),
    caption: z.string().optional(),
    rows: z.array(z.array(z.string())).optional(),
  })
  .passthrough();

const contentItemArraySchema = z.array(contentItemSchema);

const choiceOptionSchema = z.object({
  label: z.string(),
  marks: z.number().optional(),
  content: contentItemArraySchema,
});

const subQuestionSchema = z.object({
  label: z.string(),
  marks: z.number().optional(),
  content: contentItemArraySchema,
});

const choiceGroupSchema = z.object({
  displayStyle: z.enum(['or', 'choose_any']),
  chooseCount: z.number(),
  options: z.array(choiceOptionSchema),
});

const editableTextBlockSchema = z.object({
  blockId: z.string(),
  blockType: z.string(),
  text: z.string(),
  editable: z.boolean().optional(),
});

const docQuestionContentSchema = z
  .object({
    stem: contentItemArraySchema.optional(),
    assertion: contentItemArraySchema.optional(),
    reason: contentItemArraySchema.optional(),
    passage: contentItemArraySchema.optional(),
    options: z.array(choiceOptionSchema).optional(),
    subparts: z.array(subQuestionSchema).optional(),
    choices: z.array(choiceGroupSchema).optional(),
  })
  .passthrough();

const questionTypeSchema = z.enum([
  'mcq',
  'assertion_reason',
  'very_short_answer',
  'short_answer',
  'long_answer',
  'case_based',
  'internal_choice',
  'diagram_based',
  'table_based',
  'custom',
]);

const questionMetadataSchema = z
  .object({
    classLevel: z.string(),
    subject: z.string(),
    subjectArea: z.string().optional(),
    chapterIds: z.array(z.string()).optional(),
    chapterNames: z.array(z.string()),
    topicIds: z.array(z.string()).optional(),
    topicNames: z.array(z.string()).optional(),
    difficulty: z.string(),
    cognitiveLevel: z.string().optional(),
    cbseRelevance: z
      .union([z.enum(['low', 'medium', 'high']), z.number()])
      .optional(),
    estimatedMinutes: z.number().optional(),
    requiresDiagram: z.boolean().optional(),
    requiresCalculation: z.boolean().optional(),
    requiresTable: z.boolean().optional(),
    keywords: z.array(z.string()).optional(),
  })
  .passthrough();

const questionSourceSchema = z
  .object({
    sourceType: z.string(),
    sourceName: z.string(),
    fileName: z.string().optional(),
    pageNumber: z.number().optional(),
    originalQuestionNumber: z.string().optional(),
  })
  .passthrough();

const slotOverridesSchema = z.object({
  modifiedFromSource: z.boolean(),
  regions: z.record(z.string(), contentItemArraySchema),
});

const docQuestionSchema = z.object({
  questionId: z.string(),
  language: z.string(),
  marks: z.number(),
  questionType: questionTypeSchema,
  rawText: z.string(),
  content: docQuestionContentSchema,
  metadata: questionMetadataSchema,
  source: questionSourceSchema,
});

const docSlotSchema = z.object({
  slotId: z.string(),
  displayNumber: z.string(),
  marks: z.number(),
  questionType: questionTypeSchema,
  selectedQuestionId: z.string().nullable(),
  locked: z.boolean(),
  alternateQuestionIds: z.array(z.string()),
  orGroup: z.number().optional(),
  overrides: slotOverridesSchema.optional(),
});

const docSectionSchema = z.object({
  sectionId: z.string(),
  title: z.string(),
  subtitle: z.string().optional(),
  marks: z.number(),
  instructions: z.string().optional(),
  slots: z.array(docSlotSchema),
});

const docPaperSchema = z.object({
  paperId: z.string(),
  title: z.string(),
  subtitle: z.string().optional(),
  totalMarks: z.number(),
  durationMinutes: z.number(),
  language: z.string(),
  headerBlocks: z.array(editableTextBlockSchema).optional(),
  instructionBlocks: z.array(editableTextBlockSchema).optional(),
  sections: z.array(docSectionSchema),
});

const paperRequestSchema = z.object({
  requestId: z.string(),
  language: z.string(),
  classLevel: z.string(),
  subject: z.string(),
  examType: z.string(),
  filters: z
    .object({
      chapters: z.array(z.string()),
      topics: z.array(z.string()).optional(),
      englishOnly: z.boolean(),
      difficultyMix: z.record(z.string(), z.number()).optional(),
    })
    .passthrough(),
});

const paperTemplateSchema = z.object({
  templateId: z.string(),
  templateName: z.string(),
  board: z.string().optional(),
  classLevel: z.string(),
  subject: z.string(),
  examType: z.string(),
  totalMarks: z.number(),
  durationMinutes: z.number(),
  language: z.string(),
});

const paperFormatSchema = z.object({
  formatId: z.string(),
  page: z.object({
    size: z.string(),
    orientation: z.string(),
  }),
  paperChrome: z.object({
    showOuterBorder: z.boolean(),
    sectionStyle: z.string(),
    marksPlacement: z.string(),
  }),
  numbering: z.object({
    scope: z.string(),
    style: z.string(),
    recomputeOnSectionReorder: z.boolean(),
  }),
  sections: z.object({
    allowQuestionReorderWithinSection: z.boolean(),
    allowCrossSectionMove: z.boolean(),
  }),
  questionRegions: z.object({
    allowRegionReorder: z.boolean(),
    allowRegionDelete: z.boolean(),
  }),
  mcqOptions: z.object({
    layout: z.string(),
  }),
});

export const paperDocumentSchema = z.object({
  schemaVersion: z.literal('paper_document.v1'),
  request: paperRequestSchema,
  template: paperTemplateSchema,
  format: paperFormatSchema,
  paper: docPaperSchema,
  questions: z.array(docQuestionSchema),
});

export type PaperDocumentParsed = z.infer<typeof paperDocumentSchema>;
