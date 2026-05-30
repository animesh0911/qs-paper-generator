# BlockNote UI Implementation Handoff

## Purpose

This document explains how we plan to use a **BlockNote-based block UI** to create an editable question paper editor for the MVP.

The backend will return a structured question-paper payload. The frontend will convert that payload into an editable paper UI where every meaningful part of the paper is a block: header, instructions, sections, questions, case passages, internal choices, diagrams, and so on.

The goal is not to build a Word clone. The goal is to build a **teacher-friendly paper editor** where each question or section can be edited, swapped, locked, or modified using AI.

> Note: In earlier discussion, “BlockUI” refers to the block-based editor UI we will build using **BlockNote**.

---

## Product Goal

Teachers should be able to:

1. Generate a question paper from selected chapters/topics.
2. See the generated paper immediately in a clean editable interface.
3. Edit any block manually.
4. Select any question and perform AI actions like:
   - Chat edit
   - Swap question
   - Increase difficulty
   - Decrease difficulty
   - Swap topic
   - Lock question
5. Edit whole sections or the complete paper using AI-assisted commands.
6. Export the final paper to PDF/DOCX later.

For V1, the backend is not generating new questions. It is filtering/selecting questions from a question bank and sending them to the frontend.

For V1, the paper format is assumed to be the hardcoded CBSE question-paper
format already represented in the mocked/backend contract. The longer-term
backend direction is to derive the correct paper format from uploaded or
analysed previous question papers and return that format information as part of
the contract. The frontend should therefore render from contract structure
rather than baking CBSE layout assumptions into components.

The V1 contract must carry the format data the editor needs: paper headers,
instructions, ordered sections, section directions, ordered slots, display
numbers, marks, question types, internal-choice relationships, and structured
question content that can be mapped into stable editable regions.

---

## Core Principle

### Canonical Paper JSON is the source of truth

BlockNote is the editing interface, not the long-term business data model.

We should maintain our own app-level paper state:

```text
Backend Paper Payload
        ↓
Canonical Paper JSON in frontend state
        ↓
BlockNote document blocks
        ↓
Teacher edits / AI actions
        ↓
Canonical Paper JSON updated
        ↓
Preview / export / save
```

This avoids locking our product logic inside one editor library.

---

## Why BlockNote

BlockNote is useful for this MVP because:

- It is block-based, similar to Notion.
- Question papers are naturally block-based.
- It supports custom blocks.
- It gives us a polished editing experience quickly.
- It supports block IDs, props, children, drag/drop, slash commands, and programmatic block updates.
- It is easier to move fast with than building directly on raw ProseMirror or TipTap.

We are **not** planning to use BlockNote’s bundled AI features in V1. We will use our own model/backend through our own AI action system.

---

## What We Are Building

A web editor that renders a generated question paper as editable blocks.

Example high-level paper structure:

```text
Paper
├── Paper Header Block
├── General Instructions Block
├── Section Header Block: Section A - Biology
├── Direction Block: MCQ instructions
├── Question Block: Q1
├── Question Block: Q2
├── Direction Block: Assertion/Reason instructions
├── Question Block: Q8
├── Case Study Block: Q15
├── Internal Choice Block: Q16 OR question
├── Section Header Block: Section B - Chemistry
├── ...
└── Section Header Block: Section C - Physics
```

Every meaningful part should be selectable and editable.

---

## Non-Goals for V1

Do not build these in the first implementation:

- Full AI question generation.
- Word/Google Docs plugin.
- Pixel-perfect Word-like editing.
- Complex multi-user collaboration.
- Advanced page layout engine inside the editor.
- BlockNote bundled AI integration.
- Complex export fidelity from BlockNote directly.

For export, we should later render from canonical JSON into a proper print/PDF/DOCX renderer.

---

## Expected Backend Input

The frontend expects a backend payload similar to:

```json
{
  "schemaVersion": "paper_document.v1",
  "request": {},
  "template": {},
  "paper": {},
  "questions": []
}
```

The frontend should not assume this is final forever. But for V1, the important objects are:

- `template`: exam structure and section/slot blueprint.
- `paper`: actual assembled paper slots.
- `questions`: selected questions and alternates.

Backend should provide stable IDs:

- `paperId`
- `sectionId`
- `slotId`
- `questionId`
- `sourceRef`

These IDs are important because BlockNote blocks must map back to canonical data.

---

## Frontend Data Model

The frontend should keep two related representations:

### 1. Canonical Paper State

This is our app-level state.

Example:

```ts
interface PaperState {
  paperId: string;
  schemaVersion: string;
  metadata: PaperMetadata;
  sections: PaperSection[];
  questionMap: Record<string, Question>;
  slotMap: Record<string, PaperSlot>;
}
```

### 2. BlockNote Document

This is the editor representation.

Each BlockNote block should include enough props to map it back to the canonical state.

Example:

```ts
{
  id: "bn_q_001",
  type: "questionBlock",
  props: {
    blockRole: "question",
    paperId: "paper_001",
    sectionId: "A",
    slotId: "slot_A_01",
    questionId: "q_001",
    displayNumber: "1",
    marks: 1,
    questionType: "mcq",
    locked: false
  },
  content: [],
  children: []
}
```

---

## Block Types Needed

### 1. `paperHeaderBlock`

Represents the top of the paper.

Use for:

- Subject
- Class
- Time
- Maximum marks
- Paper code, if available
- School name, if available later

Suggested props:

```ts
interface PaperHeaderBlockProps {
  blockRole: "paper_header";
  paperId: string;
  editable: boolean;
  aiEditable: boolean;
}
```

Editable content can include rich text rows like:

```text
Class X
Science
Time: 3 Hours
Maximum Marks: 80
```

---

### 2. `generalInstructionsBlock`

Represents general paper instructions.

Suggested props:

```ts
interface GeneralInstructionsBlockProps {
  blockRole: "general_instructions";
  paperId: string;
  editable: boolean;
  aiEditable: boolean;
}
```

This block should allow multiline editing.

AI actions:

- Simplify instructions
- Make instructions formal
- Convert to school style
- Restore template instructions

---

### 3. `sectionHeaderBlock`

Represents section title and section-level metadata.

Example:

```text
SECTION A
Biology
30 Marks
```

Suggested props:

```ts
interface SectionHeaderBlockProps {
  blockRole: "section_header";
  paperId: string;
  sectionId: string;
  sectionLabel: string;
  sectionTitle?: string;
  subjectArea?: string;
  totalMarks?: number;
  questionRangeFrom?: number;
  questionRangeTo?: number;
  editable: boolean;
  aiEditable: boolean;
}
```

AI actions:

- Rename section
- Edit section instructions
- Balance section
- Review section marks

---

### 4. `directionBlock`

Represents instruction blocks inside a section.

Examples:

```text
Questions 1 to 7 are multiple choice questions. Each question carries 1 mark.
```

```text
Questions 8 and 9 are Assertion-Reason based questions.
```

Suggested props:

```ts
interface DirectionBlockProps {
  blockRole: "direction";
  paperId: string;
  sectionId?: string;
  appliesToSlots?: string[];
  editable: boolean;
  aiEditable: boolean;
}
```

---

### 5. `questionBlock`

This is the most important block.

Use one `questionBlock` for each numbered question slot.

Suggested props:

```ts
interface QuestionBlockProps {
  blockRole: "question";
  paperId: string;
  sectionId: string;
  slotId: string;
  questionId: string;
  displayNumber: string;
  marks: number;
  questionType: QuestionType;
  subjectArea?: string;
  chapterNames?: string[];
  topicNames?: string[];
  difficulty?: "easy" | "medium" | "hard" | string;
  sourceRef?: string;
  locked: boolean;
  editable: boolean;
  aiEditable: boolean;
}
```

Recommended `questionType` values for V1:

```ts
type QuestionType =
  | "mcq"
  | "assertion_reason"
  | "very_short_answer"
  | "short_answer"
  | "long_answer"
  | "case_based"
  | "numerical"
  | "diagram_based"
  | string;
```

The open-ended `string` is intentional. We do not want the UI to crash if backend later sends a new type.

---

### 6. `mcqOptionsBlock`

There are two possible approaches for MCQs.

#### Recommended for V1

Render MCQ options inside the `questionBlock` itself.

That keeps Q1 as one block, which makes swap/edit easier.

Example:

```text
Q1. What is ... ?
(A) ...
(B) ...
(C) ...
(D) ...
```

#### Optional later

Use a separate child block for MCQ options if we need per-option editing.

Suggested props:

```ts
interface McqOptionsBlockProps {
  blockRole: "mcq_options";
  paperId: string;
  questionId: string;
  slotId: string;
  editable: boolean;
}
```

---

### 7. `caseStudyBlock`

Used for case-based questions that include a passage and subquestions.

Example:

```text
Q15. Read the following passage and answer the questions below:
[Passage]
(a) ...
(b) ...
(c) ... OR ...
```

For V1, this can be one parent block with nested editable children.

Suggested props:

```ts
interface CaseStudyBlockProps {
  blockRole: "case_study_question";
  paperId: string;
  sectionId: string;
  slotId: string;
  questionId: string;
  displayNumber: string;
  marks: number;
  locked: boolean;
  editable: boolean;
  aiEditable: boolean;
}
```

Potential children:

- Passage block
- Sub-question blocks
- Internal-choice block

---

### 8. `subQuestionBlock`

Used for subparts like `(a)`, `(b)`, `(i)`, `(ii)`.

Suggested props:

```ts
interface SubQuestionBlockProps {
  blockRole: "sub_question";
  paperId: string;
  parentQuestionId: string;
  subQuestionId?: string;
  label: string;
  marks?: number;
  editable: boolean;
  aiEditable: boolean;
}
```

Use for:

- Long-answer subparts
- Case-based subparts
- Questions with mark split like 2 + 2 + 1

---

### 9. `internalChoiceBlock`

Used for OR choices.

Example:

```text
OR
```

Suggested props:

```ts
interface InternalChoiceBlockProps {
  blockRole: "internal_choice";
  paperId: string;
  sectionId: string;
  slotId: string;
  questionId: string;
  chooseCount: number;
  displayStyle: "or" | "any_n" | string;
  editable: boolean;
  aiEditable: boolean;
}
```

For V1, many OR questions can be rendered inside one `questionBlock`, but this block is useful if we want the OR separator and choices to be independently selectable.

---

### 10. `assetBlock`

Used for diagrams, images, equations as image, tables, or visual references.

Suggested props:

```ts
interface AssetBlockProps {
  blockRole: "asset";
  paperId: string;
  questionId?: string;
  assetId: string;
  assetType: "image" | "diagram" | "table" | "equation" | string;
  src?: string;
  altText?: string;
  editable: boolean;
}
```

V1 can keep this simple. If image extraction is not ready, use placeholders:

```text
[Diagram from source paper]
```

---

### 11. `pageBreakBlock`

Optional for preview/export later.

For editor MVP, we do not need strict page breaks.

Suggested props:

```ts
interface PageBreakBlockProps {
  blockRole: "page_break";
  paperId: string;
}
```

---

## Recommended V1 Block Hierarchy

For speed, avoid too much nesting initially.

Use this structure:

```text
paperHeaderBlock
instructionBlock
sectionHeaderBlock
questionBlock
questionBlock
questionBlock
sectionHeaderBlock
questionBlock
...
```

Inside each `questionBlock`, render its own internal content:

- Stem
- MCQ options
- Assertion/Reason
- Case passage
- Subparts
- OR choice
- Source metadata
- Action buttons

This keeps each question self-contained and easier to swap.

---

## Question Card UI

Each `questionBlock` should look like a clean editable card.

Example:

```text
Q. 5        3 marks        Electricity        Medium

[editable question text]

Source: 31-2-1.pdf, Q5

[Chat edit] [Swap] [Make easier] [Make harder] [Change topic] [Lock]
```

The teacher should not feel like they are editing raw JSON or a technical form.

---

## Selected Block Sidebar

When a teacher clicks a block, show a right sidebar.

For a question block, show:

```text
Question Details
- Question number
- Marks
- Type
- Chapter
- Topic
- Difficulty
- Source
- Locked/unlocked

Actions
- Chat edit
- Swap question
- Increase difficulty
- Decrease difficulty
- Swap topic
- Lock question
- Restore original
```

For a section block, show:

```text
Section Details
- Section label
- Subject area
- Total marks
- Question range

Actions
- Edit section title
- Review section marks
- Rebalance section
```

For header/instructions:

```text
Actions
- Edit manually
- Rewrite formally
- Restore template
```

---

## Manual Editing Behavior

Manual editing should be allowed for most blocks.

When a user edits text inside a question block:

1. Update the BlockNote block content.
2. Mark the block as dirty.
3. Update canonical `PaperState.questionMap[questionId].content`.
4. Re-run lightweight validation:
   - Is marks total still correct?
   - Is question empty?
   - Is language still English?
   - Was a locked block edited?

For V1, validation can be simple and non-blocking.

---

## Locking Behavior

Teachers should be able to lock a question.

Locked means:

- It should not be replaced during full-paper regeneration.
- Swap/change-topic actions should be disabled unless the user unlocks it.
- Manual editing can either be disabled or shown with a warning.

Recommended V1 behavior:

- Locked block is visually marked.
- Manual editing remains allowed because edits belong to the paper slot, not the question bank source.
- Replacement actions are disabled except “Unlock”.

---

## AI Action System

We are not using BlockNote bundled AI packages. They can inspire the UX
pattern: scoped proposal, auto-preview, accept, reject, refine, and highlighted
changed regions.

The frontend should call our own Django backend APIs, which use the shared
LiteLLM gateway. AI should work through controlled proposals, not free rewriting
of the full document or raw BlockNote JSON.

### Editor-specific chat edit

Typed chat requests go through backend intent classification. If the request is
an editor edit, the backend creates an async editor-edit job using the full
canonical paper document, product guardrails, and the user instruction.

The model returns a proposed patch, not a full modified paper and not BlockNote
blocks. Allowed patch targets are paper title/header, general instructions,
section titles, section instructions, approved format fields, and marks fields.
AI must not modify source question text, section membership, question count, or
raw BlockNote JSON.

Frontend action:

1. Block other structured mutations while the job is pending.
2. Auto-preview the proposal when the response arrives.
3. Show a two-line summary in the bottom chat and detailed diffs in the right inspector.
4. Apply only after teacher confirmation through local reducers.
5. Re-render BlockNote from canonical paper state.

---

### Swap question

For V1, swap should use preselected alternates from backend wherever possible.

Payload:

```json
{
  "action": "swap_question",
  "paperId": "paper_001",
  "slotId": "slot_A_01",
  "currentQuestionId": "q_001",
  "constraints": {
    "marks": 1,
    "questionType": "mcq",
    "sectionId": "A",
    "chapterNames": ["Heredity"],
    "language": "en"
  }
}
```

Expected response:

```json
{
  "status": "ok",
  "slotId": "slot_A_01",
  "replacementQuestion": {},
  "reason": "Same marks, same type, same chapter."
}
```

Frontend action:

1. Replace question in canonical state.
2. Replace BlockNote question block.
3. Preserve `slotId` and display number.
4. Update `questionId` and metadata props.

---

### Increase/decrease difficulty

This is a special case of swap.

For V1, do not ask AI to rewrite the question harder/easier unless generation/editing is enabled.

Instead:

- Find an alternate question with same marks/type/topic but different difficulty.
- Replace the current question.

---

### Whole-paper chat

Whole-paper AI should be limited to review and structured operations.

Good commands:

```text
Make the paper easier
Balance chapters
Remove duplicate questions
Make Section B slightly harder
Check if total marks are correct
Check if all selected chapters are covered
```

Do not send raw BlockNote HTML to the model.

Send canonical JSON summary:

```json
{
  "paperId": "paper_001",
  "template": {},
  "sections": [],
  "slots": [],
  "questions": []
}
```

Expected AI/backend response should be a scoped proposal:

```json
{
  "status": "proposal",
  "baseRevision": 12,
  "summary": "Rebalanced Biology and Physics questions.",
  "patches": [
    {
      "op": "replace",
      "path": "/paper/sections/1/instructions",
      "value": "Answer any five questions."
    }
  ]
}
```

Frontend validates the proposal against hard invariants and applies it only
after teacher confirmation.

---

## BlockNote Mapping Strategy

Create a mapper:

```ts
function paperBundleToBlockNoteBlocks(bundle: PaperAssemblyBundle): Block[]
```

And reverse/update helpers:

```ts
function updatePaperStateFromBlock(block: Block): void
function replaceQuestionBlock(slotId: string, question: Question): void
function getBlockBySlotId(slotId: string): Block | null
function getBlockByQuestionId(questionId: string): Block | null
```

Recommended internal maps:

```ts
const slotIdToBlockId: Record<string, string>;
const questionIdToBlockId: Record<string, string>;
const blockIdToSlotId: Record<string, string>;
```

These maps are critical for AI actions and fast updates.

---

## Rendering Question Content

Backend question content may come in structured form.

Example MCQ:

```json
{
  "questionType": "mcq",
  "content": {
    "stem": [{ "type": "paragraph", "text": "What is ...?" }],
    "options": [
      { "label": "A", "content": [{ "type": "plain_text", "text": "Option A" }] },
      { "label": "B", "content": [{ "type": "plain_text", "text": "Option B" }] }
    ]
  }
}
```

The frontend should convert this into editable BlockNote content.

For V1, acceptable rendering:

```text
What is ...?
(A) Option A
(B) Option B
(C) Option C
(D) Option D
```

Later we can render options as structured child blocks.

---

## Validation Panel

The editor should include a lightweight validation panel.

V1 checks:

```text
Total marks: 80/80
Section A marks: 30/30
Section B marks: 25/25
Section C marks: 25/25
English only: yes/no
Duplicate questions: yes/no
Empty blocks: yes/no
Locked blocks changed: yes/no
```

The validation panel should not block editing. It should guide the teacher.

---

## Save Model

When saving the paper, save canonical paper JSON. BlockNote document JSON is
transient editor view state and should not be the business source of truth.
Edit history can be kept locally for undo/debugging, but final export and reload
must come from canonical paper state.

Suggested save payload:

```json
{
  "paperId": "paper_001",
  "canonicalPaper": {}
}
```

Canonical JSON is used for future reload/export.

---

## Edit History

Track meaningful edits.

Example:

```ts
interface PaperEditHistoryItem {
  id: string;
  timestamp: string;
  actor: "teacher" | "ai" | "system";
  action:
    | "manual_edit"
    | "swap_question"
    | "ai_preview_proposal"
    | "ai_apply_proposal"
    | "ai_dismiss_proposal"
    | "ai_refine_proposal"
    | "lock_question"
    | "unlock_question"
    | "restore_original";
  blockId?: string;
  slotId?: string;
  questionId?: string;
  before?: unknown;
  after?: unknown;
}
```

This is useful for undo, teacher trust, and debugging.

---

## Export Strategy

Do not rely on BlockNote editor view for final export quality.

Recommended flow:

```text
Canonical Paper JSON
        ↓
Print Renderer
        ↓
PDF / DOCX
```

The editor should be friendly. The export should be formal.

For V1, export may be basic. But the architecture should assume export from canonical JSON.

---

## Suggested Frontend Components

```text
PaperEditorPage
├── TopBar
│   ├── Paper title
│   ├── Save
│   ├── Preview
│   └── Export
├── LeftSidebar
│   ├── Sections
│   ├── Chapters/topics summary
│   └── Validation checklist
├── BlockNotePaperEditor
│   └── Custom block renderers
└── RightSidebar
    ├── Selected block details
    ├── Question metadata
    └── AI actions
```

---

## Suggested File Structure

```text
src/
├── editor/
│   ├── PaperEditorPage.tsx
│   ├── BlockNotePaperEditor.tsx
│   ├── schema/
│   │   ├── paperBlocks.ts
│   │   └── blockSchemas.ts
│   ├── blocks/
│   │   ├── PaperHeaderBlock.tsx
│   │   ├── GeneralInstructionsBlock.tsx
│   │   ├── SectionHeaderBlock.tsx
│   │   ├── DirectionBlock.tsx
│   │   ├── QuestionBlock.tsx
│   │   ├── CaseStudyBlock.tsx
│   │   ├── SubQuestionBlock.tsx
│   │   ├── InternalChoiceBlock.tsx
│   │   └── AssetBlock.tsx
│   ├── mapping/
│   │   ├── paperBundleToBlocks.ts
│   │   ├── blocksToPaperState.ts
│   │   └── questionContentToBlocks.ts
│   ├── actions/
│   │   ├── aiActions.ts
│   │   ├── swapQuestion.ts
│   │   ├── lockQuestion.ts
│   │   └── validation.ts
│   └── state/
│       ├── paperStore.ts
│       └── editorSelectionStore.ts
├── api/
│   ├── paper.ts
│   └── ai.ts
└── types/
    ├── paper.ts
    ├── question.ts
    └── backendContract.ts
```

---

## First Implementation Milestone

Build the smallest useful version:

1. Load sample backend payload JSON.
2. Convert it to canonical `PaperState`.
3. Render paper using BlockNote custom blocks:
   - Header
   - Instructions
   - Section headers
   - Question blocks
4. Allow manual editing of question text.
5. Click question and show sidebar metadata.
6. Implement lock/unlock.
7. Implement swap using local alternates.
8. Implement basic validation panel.
9. Save current canonical JSON and BlockNote JSON.

Do not start with AI chat until these basics are working.

---

## Second Milestone

Add AI actions:

1. Chat edit selected question.
2. Rewrite selected instruction/header block.
3. Review paper.
4. Apply structured operations returned by AI/backend.

---

## Important Implementation Rules

1. Do not use one giant `contenteditable` area.
2. Do not store only HTML.
3. Do not let AI rewrite the whole document directly.
4. Do not lose `slotId` when swapping questions.
5. Do not lose `questionId` when editing questions.
6. Do not let display number and slot identity become the same thing.
7. Keep the paper editable, but validation-aware.
8. Keep final export separate from editor rendering.

---

## Open Questions for Next Agent

The next agent should decide/implement:

1. Exact BlockNote version/package setup.
2. Whether to keep MCQ options inside `questionBlock` or as child blocks.
3. Whether locked blocks are fully read-only or editable with warning.
4. How much of the paper state lives in Zustand/Redux/local React state.
5. First sample payload to use for local development.
6. How to represent math/equations in V1.
7. How to handle diagrams extracted from PDFs.
8. Whether final export starts with HTML print or DOCX template.

---

## Recommended Decision for MVP

Use this simplified V1 approach:

```text
BlockNote custom blocks:
- paperHeaderBlock
- instructionBlock
- sectionHeaderBlock
- directionBlock
- questionBlock

Render all question internals inside questionBlock:
- MCQ options
- Assertion/Reason
- Case passage
- Subparts
- OR choice

Keep canonical PaperState separate.
Use local alternates for swap.
Use our own backend/model for AI actions later.
```

This gives us a working MVP fastest while leaving room to make blocks more granular later.
