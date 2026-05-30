import { describe, expect, it } from 'vitest';
import { mockPaperDocumentV1 } from '@/mocks';
import { paperDocumentSchema } from './paper-document.schema';

describe('PaperDocumentV1 mock contract', () => {
  it('accepts the mocked paper document at the API boundary', () => {
    const parsed = paperDocumentSchema.parse(mockPaperDocumentV1);

    expect(parsed.schemaVersion).toBe('paper_document.v1');
    expect(parsed.format.formatId).toBe('cbse_science_class_10_v1');
  });

  it('carries editor format rules instead of requiring CBSE hardcoding in React', () => {
    expect(mockPaperDocumentV1.format).toMatchObject({
      page: {
        size: 'A4',
        orientation: 'portrait',
      },
      paperChrome: {
        showOuterBorder: true,
        sectionStyle: 'boxed',
        marksPlacement: 'right',
      },
      numbering: {
        scope: 'paper',
        style: 'decimal',
        recomputeOnSectionReorder: true,
      },
      sections: {
        allowQuestionReorderWithinSection: true,
        allowCrossSectionMove: false,
      },
      questionRegions: {
        allowRegionReorder: false,
        allowRegionDelete: false,
      },
      mcqOptions: {
        layout: 'vertical',
      },
    });
  });

  it('references only questions included in the document', () => {
    const questionIds = new Set(
      mockPaperDocumentV1.questions.map((question) => question.questionId),
    );

    const referencedQuestionIds = mockPaperDocumentV1.paper.sections.flatMap(
      (section) =>
        section.slots.flatMap((slot) => [
          slot.selectedQuestionId,
          ...slot.alternateQuestionIds,
        ]),
    );

    expect(
      referencedQuestionIds.filter(
        (questionId) => questionId !== null && !questionIds.has(questionId),
      ),
    ).toEqual([]);
  });

  it('covers representative CBSE question shapes needed by the editor', () => {
    const questions = mockPaperDocumentV1.questions;
    const questionTypes = new Set(
      questions.map((question) => question.questionType),
    );

    const assertionReason = questions.find(
      (question) => question.questionType === 'assertion_reason',
    );
    const longWithSubparts = questions.find(
      (question) =>
        question.content.subparts && question.questionType === 'long_answer',
    );
    const caseBased = questions.find(
      (question) => question.questionType === 'case_based',
    );
    const internalChoice = questions.find((question) =>
      Boolean(question.content.choices?.length),
    );
    const diagramBased = questions.find(
      (question) => question.questionType === 'diagram_based',
    );
    const tableBased = questions.find(
      (question) => question.questionType === 'table_based',
    );

    expect(questionTypes.has('mcq')).toBe(true);
    expect(questionTypes.has('assertion_reason')).toBe(true);
    expect(questionTypes.has('short_answer')).toBe(true);
    expect(questionTypes.has('long_answer')).toBe(true);
    expect(questionTypes.has('case_based')).toBe(true);
    expect(assertionReason?.content.assertion?.length).toBeGreaterThan(0);
    expect(assertionReason?.content.reason?.length).toBeGreaterThan(0);
    expect(longWithSubparts?.content.subparts?.length).toBeGreaterThan(0);
    expect(caseBased?.content.passage?.length).toBeGreaterThan(0);
    expect(caseBased?.content.subparts?.length).toBeGreaterThan(0);
    expect(internalChoice?.content.choices?.[0]?.options.length).toBe(2);
    expect(
      diagramBased?.content.stem?.some(
        (contentItem) => contentItem.type === 'image_placeholder',
      ),
    ).toBe(true);
    expect(
      tableBased?.content.stem?.some(
        (contentItem) => contentItem.type === 'table',
      ),
    ).toBe(true);
  });

  it('keeps selected and alternate questions compatible with their slots', () => {
    const questionById = new Map(
      mockPaperDocumentV1.questions.map((question) => [
        question.questionId,
        question,
      ]),
    );

    const mismatches = mockPaperDocumentV1.paper.sections.flatMap((section) =>
      section.slots.flatMap((slot) => {
        const questionIds = [
          slot.selectedQuestionId,
          ...slot.alternateQuestionIds,
        ].filter((questionId): questionId is string => questionId !== null);

        return questionIds
          .map((questionId) => questionById.get(questionId))
          .filter(
            (question) =>
              !question ||
              question.marks !== slot.marks ||
              question.questionType !== slot.questionType ||
              question.language !== mockPaperDocumentV1.paper.language,
          );
      }),
    );

    expect(mismatches).toEqual([]);
  });

  it('gives every slot and alternate the metadata needed by the action tray', () => {
    const questionById = new Map(
      mockPaperDocumentV1.questions.map((question) => [
        question.questionId,
        question,
      ]),
    );

    const invalidSlots = mockPaperDocumentV1.paper.sections.flatMap((section) =>
      section.slots.filter(
        (slot) =>
          !slot.slotId ||
          !slot.displayNumber ||
          !slot.questionType ||
          typeof slot.marks !== 'number' ||
          typeof slot.locked !== 'boolean' ||
          !Array.isArray(slot.alternateQuestionIds),
      ),
    );

    const invalidAlternates = mockPaperDocumentV1.paper.sections.flatMap(
      (section) =>
        section.slots.flatMap((slot) =>
          slot.alternateQuestionIds
            .map((questionId) => questionById.get(questionId))
            .filter(
              (question) =>
                !question ||
                question.metadata.chapterNames.length === 0 ||
                !question.metadata.topicNames?.length ||
                !question.metadata.difficulty ||
                !question.source.sourceName ||
                !question.language ||
                typeof question.marks !== 'number' ||
                !question.questionType,
            ),
        ),
    );

    expect(invalidSlots).toEqual([]);
    expect(invalidAlternates).toEqual([]);
  });
});
