/**
 * Zod runtime schema for `PaperDocumentV1` — the response shape of
 * `POST /api/papers/assemble`.
 *
 * Mirrors `contracts/v1_contract.md`. Parsed at the API boundary so a
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

const choiceOptionSchema = z
  .object({
    label: z.string(),
    marks: z.number().optional(),
    content: contentItemArraySchema,
  })
  .passthrough();

const subQuestionSchema = z
  .object({
    label: z.string(),
    marks: z.number().optional(),
    content: contentItemArraySchema,
  })
  .passthrough();

const choiceGroupSchema = z
  .object({
    displayStyle: z.enum(['or', 'choose_any']),
    chooseCount: z.number(),
    options: z.array(choiceOptionSchema),
  })
  .passthrough();

const editableTextBlockSchema = z
  .object({
    id: z.string(),
    role: z.string(),
    text: z.string(),
    can: z
      .object({
        editText: z.boolean().optional(),
        delete: z.boolean().optional(),
        reorder: z.boolean().optional(),
      })
      .optional(),
  })
  .passthrough();

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
    type: z.string(),
    name: z.string(),
    fileName: z.string().optional(),
    pageNumber: z.number().optional(),
    originalQuestionNumber: z.string().optional(),
  })
  .passthrough();

const slotOverridesSchema = z
  .object({
    modified: z.boolean(),
    regions: z.record(z.string(), contentItemArraySchema),
  })
  .passthrough();

const docQuestionSchema = z
  .object({
    id: z.string(),
    language: z.string(),
    defaultMarks: z.number(),
    type: questionTypeSchema,
    rawText: z.string(),
    content: docQuestionContentSchema,
    metadata: questionMetadataSchema,
    source: questionSourceSchema,
  })
  .passthrough();

const docSlotSchema = z
  .object({
    id: z.string(),
    number: z.string(),
    marks: z.number(),
    type: questionTypeSchema,
    selectedQuestionId: z.string().nullable(),
    locked: z.boolean(),
    alternateQuestionIds: z.array(z.string()),
    orGroup: z.number().optional(),
    overrides: slotOverridesSchema.optional(),
    can: z
      .object({
        editText: z.boolean().optional(),
        editMarks: z.boolean().optional(),
        swap: z.boolean().optional(),
        lock: z.boolean().optional(),
        reorder: z.boolean().optional(),
      })
      .optional(),
  })
  .passthrough();

const docSectionSchema = z
  .object({
    id: z.string(),
    title: z.string(),
    subtitle: z.string().optional(),
    marks: z.number(),
    instructions: z.string().optional(),
    slots: z.array(docSlotSchema),
  })
  .passthrough();

const docPaperSchema = z
  .object({
    id: z.string(),
    title: z.string(),
    subtitle: z.string().optional(),
    totalMarks: z.number(),
    durationMinutes: z.number(),
    language: z.string(),
    chromeBlocks: z.array(editableTextBlockSchema).optional(),
    instructionBlocks: z.array(editableTextBlockSchema).optional(),
    sections: z.array(docSectionSchema),
  })
  .passthrough();

const paperRequestSchema = z
  .object({
    id: z.string(),
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
  })
  .passthrough();

const paperTemplateSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    board: z.string().optional(),
    classLevel: z.string(),
    subject: z.string(),
    examType: z.string(),
    totalMarks: z.number(),
    durationMinutes: z.number(),
    language: z.string(),
  })
  .passthrough();

const paperFormatSchema = z
  .object({
    id: z.string(),
    page: z
      .object({
        size: z.string(),
        orientation: z.string(),
      })
      .passthrough(),
    layout: z
      .object({
        marks: z.string(),
        questionNumbers: z.string(),
        mcqOptions: z.string(),
        instructions: z.string(),
        masthead: z.string(),
        footer: z.string(),
      })
      .passthrough(),
  })
  .passthrough();

export const paperDocumentSchema = z
  .object({
    schemaVersion: z.literal('paper_document.v1'),
    request: paperRequestSchema,
    template: paperTemplateSchema,
    format: paperFormatSchema,
    paper: docPaperSchema,
    questions: z.array(docQuestionSchema),
  })
  .passthrough()
  .superRefine((document, ctx) => {
    const questionsById = new Map(
      document.questions.map((question) => [question.id, question]),
    );

    document.paper.sections.forEach((section, sectionIndex) => {
      section.slots.forEach((slot, slotIndex) => {
        const referencedQuestionIds = [
          slot.selectedQuestionId,
          ...slot.alternateQuestionIds,
        ].filter((questionId): questionId is string => questionId !== null);

        if (
          slot.selectedQuestionId !== null &&
          !questionsById.has(slot.selectedQuestionId)
        ) {
          ctx.addIssue({
            code: 'custom',
            message:
              'selectedQuestionId must reference a question in questions[]',
            path: [
              'paper',
              'sections',
              sectionIndex,
              'slots',
              slotIndex,
              'selectedQuestionId',
            ],
          });
        }

        slot.alternateQuestionIds.forEach((questionId, alternateIndex) => {
          if (!questionsById.has(questionId)) {
            ctx.addIssue({
              code: 'custom',
              message:
                'alternateQuestionIds must reference questions in questions[]',
              path: [
                'paper',
                'sections',
                sectionIndex,
                'slots',
                slotIndex,
                'alternateQuestionIds',
                alternateIndex,
              ],
            });
          }
        });

        const hasIncompatibleQuestion = referencedQuestionIds.some(
          (questionId) => {
            const question = questionsById.get(questionId);
            return (
              question &&
              (question.defaultMarks !== slot.marks ||
                question.type !== slot.type ||
                question.language !== document.paper.language)
            );
          },
        );

        if (hasIncompatibleQuestion) {
          ctx.addIssue({
            code: 'custom',
            message:
              'referenced questions must match slot marks, type, and paper language',
            path: ['paper', 'sections', sectionIndex, 'slots', slotIndex],
          });
        }
      });
    });
  });

export type PaperDocumentParsed = z.infer<typeof paperDocumentSchema>;
