# Question Paper Document Contract V1

**Product:** AI-assisted question-paper builder  
**Audience:** Frontend and backend teams  
**Frontend editor:** BlockNote / block-based paper editor  
**Contract goal:** Backend returns one section-wise, slot-based paper document that the frontend can render, edit, validate, swap, and export.

## 1. V1 Shape

```json
{
  "schemaVersion": "paper_document.v1",
  "request": {},
  "template": {},
  "format": {},
  "paper": {},
  "questions": []
}
```

V1 keeps the contract lean. Do not add empty placeholder objects such as `validation`, `capabilities`, `extensions`, or `extras`. Backend may add optional fields without changing `schemaVersion`; frontend must ignore unknown optional fields and preserve them where practical. Backend must not remove or rename required fields without changing `schemaVersion`.

## 2. Core Principle

Backend must return a ready-to-render, section-wise, slot-based paper document. The frontend should not receive only a flat question list.

`format` describes semantic layout roles and selects a known frontend renderer. It does not send arbitrary CSS, React component names, or low-level x/y instructions.

`paper` contains all visible per-paper content: chrome, instructions, sections, and slots.

`questions[]` contains reusable source Question content. Source question text must not include visible marks. Slot marks are canonical and rendered from `slot.marks`.

The frontend flow is:

```text
PaperDocumentV1
  -> runtime validation
  -> normalized questionsById / slotsById
  -> editor view-model
  -> editor renderer and print/download renderer
```

## 3. Format Object

`format.id` selects a known frontend renderer. For V1 MVP, the active renderer is the compact CBSE paper family based on `31-2-1.pdf`.

```json
{
  "id": "cbse_science_class_10_board_compact_2026_v1",
  "page": {
    "size": "CBSE_COMPACT",
    "orientation": "portrait",
    "widthPt": 523.44,
    "heightPt": 693.36,
    "marginPt": { "top": 28, "right": 36, "bottom": 34, "left": 36 }
  },
  "layout": {
    "marks": "right_column",
    "questionNumbers": "left_column",
    "mcqOptions": "two_column",
    "instructions": "note_table_then_general",
    "masthead": "cbse_compact",
    "footer": "code_page_pto"
  }
}
```

Frontend renderer boundary:

```ts
const rendererByFormatId = {
  cbse_science_class_10_board_compact_2026_v1: cbseCompactRenderer,
};
```

If backend sends an unsupported `format.id`, frontend must fail loud instead of guessing a layout.

No page break map is required in V1. Editor pagination and download pagination follow the frontend renderer.

## 4. Paper Object

```json
{
  "id": "paper_123",
  "title": "Science",
  "subtitle": "Class X",
  "totalMarks": 80,
  "durationMinutes": 180,
  "language": "en",
  "chromeBlocks": [],
  "instructionBlocks": [],
  "sections": []
}
```

| Field               | Required | Purpose                                                                                                  |
| ------------------- | -------: | -------------------------------------------------------------------------------------------------------- |
| `id`                |      Yes | Stable ID for this generated paper.                                                                      |
| `title`             |      Yes | Main paper title.                                                                                        |
| `totalMarks`        |      Yes | Total marks for display and validation.                                                                  |
| `durationMinutes`   |      Yes | Exam duration for display and validation.                                                                |
| `language`          |      Yes | Paper language.                                                                                          |
| `chromeBlocks`      | Optional | Visible paper chrome such as series, set, QP code, roll number line, time, max marks, and footer labels. |
| `instructionBlocks` | Optional | Editable note/general instruction text.                                                                  |
| `sections`          |      Yes | Ordered section-wise slots.                                                                              |

## 5. Editable Text Blocks

Chrome and instruction blocks are visible paper text. They are not format rules.

```json
{
  "id": "paper_code",
  "role": "paper_code",
  "text": "31/2/1",
  "can": {
    "editText": true,
    "delete": true,
    "reorder": false
  }
}
```

Required fields: `id`, `role`, `text`.

`can` is optional. If omitted, frontend defaults to:

```json
{ "editText": true, "delete": false, "reorder": false }
```

Recommended CBSE chrome roles for V1:

```text
series
set
paper_code
subject_label
roll_number
paper_meta_left
paper_meta_right
footer_left
footer_right
```

Roll number should be rendered as a blank line/space in V1, not boxes.

Recommended instruction roles:

```text
note_heading
note
general_instructions_heading
general_instruction
```

## 6. Sections

```json
{
  "id": "A",
  "title": "Section A",
  "subtitle": "Biology",
  "marks": 30,
  "instructions": "Questions 1 to 16 are from Biology.",
  "slots": []
}
```

Required fields: `id`, `title`, `marks`, `slots`.

## 7. Slots

A Slot is a position in the paper. It owns visible numbering, marks, selected question reference, alternates, lock state, and slot-level edit overrides.

```json
{
  "id": "slot_A_01",
  "number": "1",
  "marks": 1,
  "type": "mcq",
  "selectedQuestionId": "q_001",
  "alternateQuestionIds": ["q_001_alt_1", "q_001_alt_2"],
  "locked": false,
  "can": {
    "editText": true,
    "editMarks": true,
    "swap": true,
    "lock": true,
    "reorder": true
  },
  "overrides": {
    "modified": false,
    "regions": {}
  }
}
```

Required fields: `id`, `number`, `marks`, `type`, `selectedQuestionId`, `locked`, `alternateQuestionIds`.

If `can` is omitted, frontend defaults all slot actions to enabled. V1 code may support these defaults even when the visible UI does not expose every action yet. Marks editing is contract-supported through `can.editMarks`, but the V1 frontend may leave marks editing hidden.

Every selected or alternate question must exist in `questions[]` and match the Slot on:

- `defaultMarks`
- `type`
- `language`

When a slot swaps to an alternate question, preserve Slot marks by default and clear slot-level text overrides.

## 8. Questions

Every selected or alternate Question must appear in `questions[]`.

```json
{
  "id": "q_001",
  "language": "en",
  "defaultMarks": 1,
  "type": "mcq",
  "rawText": "What is the ratio of GG, Gg and gg in F2 progeny?",
  "content": {},
  "metadata": {},
  "source": {}
}
```

Required fields: `id`, `language`, `defaultMarks`, `type`, `rawText`, `content`, `metadata`, `source`.

`rawText` is a fallback for display, search, unsupported types, and debugging. It must not include visible marks such as `[1]`, `(1 mark)`, or `1`.

Recommended V1 `type` values:

```text
mcq
assertion_reason
very_short_answer
short_answer
long_answer
case_based
internal_choice
diagram_based
table_based
custom
```

If backend adds a new type, it must still include `rawText` so the frontend can render a safe fallback.

## 9. Content Items

Question content should be structured but simple.

```json
{ "type": "paragraph", "text": "State Ohm's law." }
```

```json
{ "type": "equation", "latex": "V = IR", "text": "V = IR" }
```

```json
{
  "type": "image_placeholder",
  "text": "Diagram present in source PDF, extraction pending."
}
```

```json
{
  "type": "table",
  "rows": [
    ["Material", "Resistance"],
    ["Copper", "Low"]
  ]
}
```

A content item is `{ type, text?, latex?, assetId?, caption?, rows? }`. Images reference an asset by `assetId` with an optional `caption`; there is no inline image URL in V1.

### Content container

`question.content` is an object keyed by semantic region, not a flat array. Each region holds content items (or option/subpart objects). Regions are optional; include only those the question type uses. A type the frontend does not model still renders from `rawText`.

| Region      | Shape            | Used by                          |
| ----------- | ---------------- | -------------------------------- |
| `stem`      | `ContentItem[]`  | all types                        |
| `assertion` | `ContentItem[]`  | `assertion_reason`               |
| `reason`    | `ContentItem[]`  | `assertion_reason`               |
| `passage`   | `ContentItem[]`  | `case_based`                     |
| `options`   | `ChoiceOption[]` | `mcq`, `assertion_reason`        |
| `subparts`  | `SubQuestion[]`  | `case_based`, multi-part answers |
| `choices`   | `ChoiceGroup[]`  | `internal_choice`                |

```text
ChoiceOption = { label, marks?, content: ContentItem[] }
SubQuestion  = { label, marks?, content: ContentItem[] }
ChoiceGroup  = { displayStyle: "or" | "choose_any", chooseCount, options: ChoiceOption[] }
```

Example `mcq` content:

```json
{
  "stem": [
    {
      "type": "paragraph",
      "text": "What is the ratio of GG, Gg and gg in F2 progeny?"
    }
  ],
  "options": [
    { "label": "A", "content": [{ "type": "paragraph", "text": "1 : 2 : 1" }] },
    { "label": "B", "content": [{ "type": "paragraph", "text": "3 : 1 : 0" }] }
  ]
}
```

## 10. Question Source

```json
{
  "type": "previous_year_paper",
  "name": "31-2-1 Science 2026",
  "fileName": "31-2-1.pdf",
  "pageNumber": 3,
  "originalQuestionNumber": "1"
}
```

Required fields: `type`, `name`.

## 11. Request And Template

`request` uses simple IDs and teacher inputs:

```json
{
  "id": "req_123",
  "language": "en",
  "classLevel": "10",
  "subject": "Science",
  "examType": "full_term",
  "filters": {
    "chapters": ["Life Processes", "Electricity"],
    "topics": ["Ohm's Law", "Human Brain"],
    "englishOnly": true,
    "difficultyMix": { "easy": 30, "medium": 50, "hard": 20 }
  }
}
```

`template` records the paper family:

```json
{
  "id": "cbse_science_class_10_full_term_v1",
  "name": "CBSE Class 10 Science Full Term",
  "board": "CBSE",
  "classLevel": "10",
  "subject": "Science",
  "examType": "full_term",
  "totalMarks": 80,
  "durationMinutes": 180,
  "language": "en"
}
```

## 12. Frontend Responsibilities

Frontend modules and seams:

- `paper-document.ts`: validates and normalizes `PaperDocumentV1`.
- `editor-paper.ts`: adapts canonical paper data into the editor view-model.
- `PaperDocumentView`: adapts canonical paper data into print/download output.

The editor may keep internal view-model names such as `slotId`, `displayNumber`, and `questionId`, but these are not backend contract fields.

## 13. V2 Notes

Keep these out of V1 implementation unless explicitly prioritized:

- custom user-generated format builder
- LLM/visual QA after download to compare rendered PDF with a reference screenshot or layout map
- user-authored custom format templates
- explicit page-break maps from backend
