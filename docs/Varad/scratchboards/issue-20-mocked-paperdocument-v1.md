# Scratchboard: Issue #20 Mocked PaperDocumentV1

GitHub: https://github.com/animesh0911/qs-paper-generator/issues/20

## Issue Goal

Create the frontend development fixture for the BlockNote paper editor: a mocked
`PaperDocumentV1` with format rules, ordered sections/slots, stable IDs, broad
slot-wise alternatives, and representative CBSE Class 10 Science question types.

## Success Criteria

- Mock payload includes `schemaVersion`, `request`, `template`, `format`,
  `paper`, and `questions`.
- `format` is enough for the editor/PDF renderer to avoid hardcoding CBSE
  structure rules in React components.
- Every selected and alternate question referenced by slots exists in
  `questions[]`.
- Every slot has stable `slotId`, `displayNumber`, `marks`, `questionType`,
  `selectedQuestionId`, `locked`, and `alternateQuestionIds`.
- Alternates carry metadata needed for tray filtering: chapter/topic tags,
  difficulty, optional CBSE relevance, source, language, marks, and type.
- Mock includes representative content shapes:
  - MCQ
  - assertion-reason
  - very short answer / short answer
  - long answer with subparts
  - case-based passage with subquestions
  - internal choice

## Current Code Facts

- Backend `PaperDocumentBuilder` emits `schemaVersion`, `request`, `template`,
  `paper`, and `questions`.
- Backend currently does **not** emit top-level `format`.
- Frontend `paperDocumentSchema` currently accepts only `schemaVersion`,
  `paper`, and `questions`; it is behind the docs and issue requirements.
- Frontend `PaperDocument` types currently miss `request`, `template`, `format`,
  `language`, `source`, `locked`, and richer content regions.
- Existing preview reads `doc.paper.sections[].slots[]` and `doc.questions[]`;
  it can keep working after additive fields if the schema/types are updated.

## Contract Shape To Finalize

```ts
type PaperDocumentV1 = {
  schemaVersion: "paper_document.v1";
  request: PaperRequest;
  template: PaperTemplate;
  format: PaperFormat;
  paper: Paper;
  questions: Question[];
};
```

### `format` Minimum

```ts
type PaperFormat = {
  formatId: "cbse_science_class_10_v1";
  page: {
    size: "A4";
    orientation: "portrait";
  };
  paperChrome: {
    showOuterBorder: boolean;
    sectionStyle: "boxed" | "plain";
    marksPlacement: "right" | "inline";
  };
  numbering: {
    scope: "paper" | "section";
    style: "decimal";
    recomputeOnSectionReorder: boolean;
  };
  sections: {
    allowQuestionReorderWithinSection: boolean;
    allowCrossSectionMove: false;
  };
  questionRegions: {
    allowRegionReorder: false;
    allowRegionDelete: false;
  };
  mcqOptions: {
    layout: "vertical" | "two_column";
  };
};
```

### Slot Minimum

```ts
type PaperSlot = {
  slotId: string;
  displayNumber: string;
  marks: number;
  questionType: QuestionType;
  selectedQuestionId: string | null;
  locked: boolean;
  alternateQuestionIds: string[];
  orGroup?: number;
  overrides?: {
    modifiedFromSource: boolean;
    regions: Record<string, ContentItem[]>;
  };
};
```

### Question Minimum

```ts
type Question = {
  questionId: string;
  language: "en";
  marks: number;
  questionType: QuestionType;
  rawText: string;
  content: QuestionContent;
  metadata: {
    classLevel: "10";
    subject: "Science";
    subjectArea?: "Physics" | "Chemistry" | "Biology";
    chapterNames: string[];
    topicNames: string[];
    difficulty: "easy" | "medium" | "hard";
    cognitiveLevel?: "remember" | "understand" | "apply" | "analyse";
    cbseRelevance?: "low" | "medium" | "high" | number;
  };
  source: {
    sourceType: "previous_year_paper" | "question_bank" | "sample_paper";
    sourceName: string;
    fileName?: string;
    pageNumber?: number;
    originalQuestionNumber?: string;
  };
};
```

## Proposed File Targets

- Add frontend fixture:
  - `frontend/src/mocks/paper-document-v1.mock.ts`
- Update shared types:
  - `frontend/src/types/index.ts`
- Update runtime schema:
  - `frontend/src/types/paper-document.schema.ts`
- Optional export convenience:
  - `frontend/src/mocks/index.ts`

## TDD / Verification Plan

Use Vitest for frontend contract tests. The public interface under test is the
runtime schema plus mock fixture, not implementation details.

Tracer bullet:

1. Add a failing test importing `mockPaperDocumentV1` and parsing it with
   `paperDocumentSchema`.
2. Add the mock fixture with the target top-level fields.
3. Update `paperDocumentSchema`.
4. Run `npm test`, `npm run type-check`, and `npm run build` in `frontend`.

Follow-up checks:

1. Verify the mock parses with `paperDocumentSchema.parse(mockPaperDocumentV1)`.
2. Verify every selected/alternate ID in slots exists in `questions[]`.
3. Verify representative question types exist in the mock.

These are contract tests around the public schema interface, not React
implementation details.

## Low-Level Implementation Notes

- Keep the mock realistic but not huge. Aim for 5 sections and roughly 8-12
  selected slots, with 2-3 alternates per major slot shape.
- Use stable, readable IDs:
  - `paper_mock_cbse_science_001`
  - `slot_A_01`
  - `q_mcq_heredity_001`
- Use `alternateQuestionIds` that match slot marks/type/language.
- Include at least one locked slot to support later tray behavior.
- Preserve both OR concepts separately:
  - template-level OR choice: two slots sharing `orGroup`
  - question-internal choice: one question with `content.choices[]`
- Include one `diagram_based` question with `image_placeholder` and one
  `table_based` question if the fixture remains readable.
- Do not model answer keys in this issue.
- Do not add BlockNote dependency in this issue.
- Do not build normalization yet; that belongs to #21.
- Include an empty `overrides` object on at least one slot and one edited
  example slot override only if it keeps the mock readable. Initial backend
  generation may omit overrides, but the final saved document uses them for
  paper-specific edits.

## Open Checks For Contract Finalizer Subagent

- Use dedicated `assertion` and `reason` content regions for
  `assertion_reason`.
- `selectedQuestionId` field is required but value may be `string | null` for
  unfilled best-effort slots.
- Fixture slots should always include `alternateQuestionIds` and `locked`; empty
  alternates should be `[]`, not omitted.
- Prefer schema support for enum or numeric `cbseRelevance` for V1 flexibility.
- `format.paperChrome.sectionStyle = "boxed"` is enough for issue #20. Richer
  border/label styling can wait for editor shell work.

## Decision Log

- 2026-05-30: Treat `PaperDocumentV1` docs as target contract for the mock.
  Current frontend schema is behind and should be updated as part of this issue.
- 2026-05-30: Keep this issue focused on mock contract/types/schema. No
  normalization, no BlockNote mapping, no editor UI.
- 2026-05-30: Contract finalizer confirms the mock should lead the editor
  contract rather than mirror current backend limitations. Backend currently
  cannot produce all rich content variants yet; that is acceptable for the
  frontend development fixture.
- 2026-05-30: No `docs/V2_contract` needed yet. The V1 backbone remains valid,
  but it now explicitly includes slot-level overrides for paper-specific edits,
  required `locked`, required `alternateQuestionIds`, and required nullable
  `selectedQuestionId`.
- 2026-05-30: Added Vitest to the frontend so #20 can be implemented with a
  real RED/GREEN contract test loop.
