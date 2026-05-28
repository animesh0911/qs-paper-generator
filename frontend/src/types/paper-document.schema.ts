/**
 * Zod runtime schema for `PaperDocumentV1` — the response shape of
 * `POST /api/papers/assemble`.
 *
 * Mirrors `backend/papers/document.py::PaperDocumentV1`. Parsed at the
 * API boundary so a backend/frontend contract drift surfaces as a loud
 * error at first call instead of a blank screen downstream.
 *
 * Why a runtime check exists in addition to TypeScript types: TS only
 * verifies that calling code trusts its own annotations. It does not
 * verify that the actual JSON returned by the server matches them.
 * Commit b6384db shipped a backend shape change with no frontend update
 * and no test failed — Zod parsing closes that gap.
 */
import { z } from 'zod';

const blockSchema = z.object({
  type: z.string(),
  text: z.string(),
});

const docQuestionContentSchema = z.object({
  stem: z.array(blockSchema),
  options: z
    .array(
      z.object({
        label: z.string(),
        content: z.array(blockSchema),
      }),
    )
    .optional(),
});

const docQuestionSchema = z.object({
  questionId: z.string(),
  marks: z.number(),
  questionType: z.string(),
  rawText: z.string(),
  content: docQuestionContentSchema,
  metadata: z.object({
    chapterNames: z.array(z.string()),
    difficulty: z.string(),
  }),
});

const docSlotSchema = z.object({
  slotId: z.string(),
  displayNumber: z.string(),
  marks: z.number(),
  questionType: z.string(),
  selectedQuestionId: z.string().nullable(),
  orGroup: z.number().optional(),
  alternateQuestionIds: z.array(z.string()).optional(),
});

const docSectionSchema = z.object({
  sectionId: z.string(),
  title: z.string(),
  marks: z.number(),
  instructions: z.string(),
  slots: z.array(docSlotSchema),
});

const docPaperSchema = z.object({
  paperId: z.string(),
  title: z.string(),
  totalMarks: z.number(),
  durationMinutes: z.number(),
  sections: z.array(docSectionSchema),
});

export const paperDocumentSchema = z.object({
  schemaVersion: z.literal('paper_document.v1'),
  paper: docPaperSchema,
  questions: z.array(docQuestionSchema),
});

export type PaperDocumentParsed = z.infer<typeof paperDocumentSchema>;
