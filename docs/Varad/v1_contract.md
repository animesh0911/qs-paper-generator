# Question Paper Document Contract V1

**Product:** AI-assisted question-paper builder  
**Audience:** Frontend and backend teams  
**Frontend editor:** BlockNote / block-based paper editor  
**Contract goal:** Backend returns one section-wise, slot-based paper document that the frontend can render, edit, validate, swap, and later save/export.

---

## 1. V1 Decision

For V1, use the simple contract shape:

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

Do not include empty placeholder objects in V1:

```json
{
  "validation": {},
  "capabilities": {},
  "extensions": {},
  "extras": {}
}
```

Those concepts may be added later as optional fields. For the MVP, they add noise and make the frontend contract harder to implement.

### V1 flexibility rule

Backend may add optional fields without changing the schema version. Frontend must ignore unknown optional fields and preserve them where practical.

Backend must not remove or rename required fields without changing `schemaVersion`.

---

## 2. Core Principle

Backend must return a ready-to-render, section-wise, slot-based paper document.

The generated paper should preserve the observed format of the source paper
template it is based on. In the future, the backend should derive this format
from uploaded/analysed previous question papers and include the resulting
format instructions in the contract. For V1, this derivation pipeline is not in
scope: the contract may hardcode the CBSE Class 10 Science paper format based
on current observations.

The frontend should not receive only a flat question list. Every question must be placed into a stable slot so the frontend can know:

- which section the question belongs to
- what marks the slot expects
- which question type the slot expects
- whether replacement is safe
- which alternates can be used for instant swap
- what metadata should be preserved during AI/edit actions

The frontend will transform the backend document into:

```text
PaperDocumentV1
  -> runtime validation
  -> normalized questionsById
  -> paper sections and slots
  -> BlockNote document blocks
```

Paper-specific edits must never mutate entries in `questions[]`. `questions[]`
represents source question content. If a teacher edits question text in the
paper editor, the edited content belongs to the slot and is stored as a
slot-level override.

---

## 3. Top-Level Object

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

| Field | Required | Purpose |
|---|---:|---|
| `schemaVersion` | Yes | Identifies the contract version. Must be `paper_document.v1`. |
| `request` | Yes | Teacher/user input that produced the paper. |
| `template` | Yes | Expected paper format and constraints. |
| `format` | Yes | Format intent shared by the editor and print renderer. |
| `paper` | Yes | Actual assembled paper with sections and slots. |
| `questions` | Yes | Every selected and alternate question referenced by slots. |

---

## 4. Request Object

The `request` object records the teacher's input.

```json
{
  "requestId": "req_123",
  "language": "en",
  "classLevel": "10",
  "subject": "Science",
  "examType": "full_term",
  "filters": {
    "chapters": ["Life Processes", "Electricity"],
    "topics": ["Ohm's Law", "Human Brain"],
    "englishOnly": true,
    "difficultyMix": {
      "easy": 30,
      "medium": 50,
      "hard": 20
    }
  }
}
```

| Field | Required | Notes |
|---|---:|---|
| `requestId` | Yes | Stable ID for this generation request. |
| `language` | Yes | For V1 this is usually `en`. |
| `classLevel` | Yes | Example: `10`. |
| `subject` | Yes | Example: `Science`. |
| `examType` | Yes | Example: `unit_test`, `half_term`, `full_term`, `homework`. |
| `filters` | Yes | User-selected chapters/topics/rules. |
| `filters.englishOnly` | Yes | Required for the English-only MVP flow. |

---

## 5. Template Object

The `template` object describes the expected paper format.

```json
{
  "templateId": "cbse_science_class_10_full_term_v1",
  "templateName": "CBSE Class 10 Science Full Term",
  "board": "CBSE",
  "classLevel": "10",
  "subject": "Science",
  "examType": "full_term",
  "totalMarks": 80,
  "durationMinutes": 180,
  "language": "en"
}
```

| Field | Required | Notes |
|---|---:|---|
| `templateId` | Yes | Stable ID for the paper format. |
| `templateName` | Yes | Human-readable name. |
| `classLevel` | Yes | Example: `10`. |
| `subject` | Yes | Example: `Science`. |
| `examType` | Yes | Example: `full_term`. |
| `totalMarks` | Yes | Example: `80`. |
| `durationMinutes` | Yes | Example: `180`. |
| `language` | Yes | Example: `en`. |
| `board` | Optional | Example: `CBSE`. |

Frontend must not hardcode one board pattern forever. It should render from `paper.sections[]` and `paper.sections[].slots[]`.

### V1 format scope

For V1, the only supported paper format is the hardcoded CBSE question-paper
format represented by `template` and `paper.sections[]`. The frontend should
still treat this as data-driven: section order, section labels, directions,
slot order, display numbers, marks, and question types come from the contract.

Later versions may add richer template/format metadata derived from uploaded
previous papers, such as typography, page layout, section-specific numbering
rules, answer-choice layout, page breaks, and print/export rules. Those should
be additive contract fields rather than frontend hardcoding.

### V1 format data required by frontend

For the BlockNote editor to render a faithful CBSE paper without baking format
rules into components, the mocked/backend contract must include:

- paper header text blocks
- general instruction blocks
- ordered sections
- section titles and optional subtitles
- section-specific directions/instructions
- ordered slots within each section
- display numbering for each slot
- marks and question type for each slot
- internal-choice/OR relationships where present
- enough structured question content to derive stable editable regions such as
  stem, MCQ option, passage, subquestion, and internal-choice separator
- a slot-level override location for paper-specific question text edits

For V1, exact typography tokens, margins, page-break rules, uploaded-paper
template metadata, and arbitrary board-specific layout rules are out of scope.

---

## 6. Format Object

The `format` object describes the paper-format intent used by both the
BlockNote editor and the PDF/print renderer. It is not a full design-token
system in V1. It gives the frontend and backend enough shared rules to render
the same CBSE-style paper structure without hardcoding those choices in only
one layer.

```json
{
  "formatId": "cbse_science_class_10_v1",
  "page": {
    "size": "A4",
    "orientation": "portrait"
  },
  "paperChrome": {
    "showOuterBorder": true,
    "sectionStyle": "boxed",
    "marksPlacement": "right"
  },
  "numbering": {
    "scope": "paper",
    "style": "decimal",
    "recomputeOnSectionReorder": true
  },
  "sections": {
    "allowQuestionReorderWithinSection": true,
    "allowCrossSectionMove": false
  },
  "questionRegions": {
    "allowRegionReorder": false,
    "allowRegionDelete": false
  },
  "mcqOptions": {
    "layout": "vertical"
  }
}
```

| Field | Required | Notes |
|---|---:|---|
| `formatId` | Yes | Stable ID for the format rule set. |
| `page.size` | Yes | Example: `A4`. |
| `page.orientation` | Yes | Example: `portrait`. |
| `paperChrome.showOuterBorder` | Yes | Whether the paper canvas/print output uses an outer border. |
| `paperChrome.sectionStyle` | Yes | Example: `boxed`, `plain`. |
| `paperChrome.marksPlacement` | Yes | Example: `right`. |
| `numbering.scope` | Yes | Example: `paper` for continuous numbering across sections. |
| `numbering.style` | Yes | Example: `decimal`. |
| `numbering.recomputeOnSectionReorder` | Yes | Whether display numbers are derived from current section order. |
| `sections.allowQuestionReorderWithinSection` | Yes | V1 allows reordering questions within a section. |
| `sections.allowCrossSectionMove` | Yes | V1 must be `false`; questions cannot move across sections. |
| `questionRegions.allowRegionReorder` | Yes | V1 must be `false`; question internal structure is fixed. |
| `questionRegions.allowRegionDelete` | Yes | V1 must be `false`; question internal regions are not deleted. |
| `mcqOptions.layout` | Yes | Example: `vertical`; richer layout rules can be added later. |

For V1, this object is expected to be hardcoded to the CBSE format. Later
versions may add typography, margins, page breaks, two-column options, diagram
placement, and uploaded-paper-derived template rules as optional fields.

---

## 7. Paper Object

The `paper` object is the assembled paper.

```json
{
  "paperId": "paper_123",
  "title": "Science",
  "subtitle": "Class X",
  "totalMarks": 80,
  "durationMinutes": 180,
  "language": "en",
  "headerBlocks": [],
  "instructionBlocks": [],
  "sections": []
}
```

| Field | Required | Purpose |
|---|---:|---|
| `paperId` | Yes | Stable ID for this generated paper. |
| `title` | Yes | Main paper title. |
| `totalMarks` | Yes | Total marks for display and validation. |
| `durationMinutes` | Yes | Exam duration for display and validation. |
| `language` | Yes | Paper language. |
| `sections` | Yes | Ordered section-wise slots. |
| `subtitle` | Optional | Example: `Class X`. |
| `headerBlocks` | Optional | Editable paper header lines. |
| `instructionBlocks` | Optional | Editable general instructions. |

---

## 8. Editable Text Blocks

Header and instruction text should also be editable. Backend can send simple text blocks.

```json
{
  "blockId": "header_001",
  "blockType": "paper_header",
  "text": "Science - Class X",
  "editable": true
}
```

```json
{
  "blockId": "instruction_001",
  "blockType": "instruction",
  "text": "Maximum Marks: 80. Time allowed: 3 hours.",
  "editable": true
}
```

| Field | Required | Notes |
|---|---:|---|
| `blockId` | Yes | Stable block ID. |
| `blockType` | Yes | Example: `paper_header`, `instruction`, `direction`. |
| `text` | Yes | Rendered text. |
| `editable` | Optional | Defaults to `true`. |

---

## 9. Sections

Each section contains section metadata and ordered slots.

```json
{
  "sectionId": "A",
  "title": "Section A",
  "subtitle": "Biology",
  "marks": 30,
  "instructions": "Questions 1 to 16 are from Biology.",
  "slots": []
}
```

| Field | Required | Notes |
|---|---:|---|
| `sectionId` | Yes | Stable ID, e.g. `A`, `B`, `C`. |
| `title` | Yes | Example: `Section A`. |
| `marks` | Yes | Total section marks. |
| `slots` | Yes | Question slots in display order. |
| `subtitle` | Optional | Example: `Biology`. |
| `instructions` | Optional | Section-specific instruction text. |

---

## 10. Slots

A slot is a position in the paper. It defines what kind of question belongs there.

```json
{
  "slotId": "slot_A_01",
  "displayNumber": "1",
  "marks": 1,
  "questionType": "mcq",
  "selectedQuestionId": "q_001",
  "alternateQuestionIds": ["q_001_alt_1", "q_001_alt_2"],
  "locked": false,
  "overrides": {
    "modifiedFromSource": false,
    "regions": {}
  }
}
```

| Field | Required | Purpose |
|---|---:|---|
| `slotId` | Yes | Stable slot ID for editing, locking, swapping, and save operations. |
| `displayNumber` | Yes | Visible number, e.g. `1`, `16`, `16(a)`. |
| `marks` | Yes | Marks expected for this slot. |
| `questionType` | Yes | Expected type for this slot. |
| `selectedQuestionId` | Yes | Question currently selected for this slot. Field is required; value may be `null` for an unfilled best-effort slot. |
| `alternateQuestionIds` | Yes | Enables instant frontend swap. Use `[]` when no safe alternates exist. |
| `locked` | Yes | If true, replacement/regeneration actions are disabled until unlocked. Manual paper-slot edits remain allowed. |
| `overrides` | Optional | Paper-specific edited regions for this slot. Initial backend generation may omit it or send an empty object. |

`slot.marks` is the paper-slot mark value used for display, validation, save,
and PDF export. `question.marks` is the source question's original/default mark
value. In the normal generated paper they should match. Later editor/AI flows
may change `slot.marks`; that must not mutate `question.marks`.

The selected question should match the slot on:

- `marks`
- `questionType`
- `language`
- selected chapters/topics where applicable

Every non-null `selectedQuestionId` and every ID in `alternateQuestionIds` must
exist in `questions[]`.

### Slot-level overrides

Use slot-level overrides when teacher edits change source question text for this
paper only.

```json
{
  "overrides": {
    "modifiedFromSource": true,
    "regions": {
      "stem": [
        {
          "type": "paragraph",
          "text": "Edited wording for this paper only."
        }
      ],
      "option:A": [
        {
          "type": "paragraph",
          "text": "Edited option text."
        }
      ]
    }
  }
}
```

| Field | Required | Notes |
|---|---:|---|
| `overrides.modifiedFromSource` | Yes when `overrides` exists | Whether this slot renders any paper-specific content instead of source content. |
| `overrides.regions` | Yes when `overrides` exists | Map from stable `regionKey` to replacement content items. |

The original source question in `questions[]` must remain unchanged. Swapping a
slot to a different `selectedQuestionId` should clear old overrides after user
confirmation.

---

## 11. Question Object

Every selected or alternate question must appear in the `questions` array.

```json
{
  "questionId": "q_001",
  "language": "en",
  "marks": 1,
  "questionType": "mcq",
  "rawText": "What is the ratio of GG, Gg and gg in F2 progeny?",
  "content": {},
  "metadata": {},
  "source": {}
}
```

| Field | Required | Purpose |
|---|---:|---|
| `questionId` | Yes | Stable ID. |
| `language` | Yes | For V1, usually `en`. |
| `marks` | Yes | Question marks. |
| `questionType` | Yes | MCQ / short answer / long answer / case-based etc. |
| `rawText` | Yes | Fallback text for display, search, unsupported types, and debugging. |
| `content` | Yes | Structured editable content. |
| `metadata` | Yes | Chapter/topic/difficulty/classification. |
| `source` | Yes | Where the question came from. |

Question content in `questions[]` is treated as source content. The frontend may
allow manual paper-slot edits, but those edits are saved through slot overrides,
not by changing `questions[]`.

---

## 12. Recommended Question Types

Use these V1 values where possible:

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

---

## 13. Content Items

Question content should be structured but simple.

### Stable region keys

Frontend manual edits and AI guardrails need stable region keys. Backend does
not need to precompute these keys in V1; frontend can derive them
deterministically from `content`.

Use these V1 region-key conventions:

| Content region | `regionKey` |
|---|---|
| Stem | `stem` |
| Assertion | `assertion` |
| Reason | `reason` |
| MCQ option A | `option:A` |
| Passage | `passage` |
| Subpart a | `subpart:a` |
| Choice group 1, option A | `choice:1:A` |

If a future question shape cannot be mapped cleanly, frontend should use
`rawText` with a fallback question block and avoid paper-slot overrides for that
question type until the shape is added to the contract.

### Paragraph

```json
{
  "type": "paragraph",
  "text": "State Ohm's law."
}
```

### Equation

```json
{
  "type": "equation",
  "latex": "V = IR",
  "text": "V = IR"
}
```

### Image / diagram reference

```json
{
  "type": "image",
  "assetId": "asset_001",
  "caption": "Circuit diagram"
}
```

### Image placeholder

Use this when asset extraction is not ready.

```json
{
  "type": "image_placeholder",
  "text": "Diagram present in source PDF, extraction pending."
}
```

### Table

```json
{
  "type": "table",
  "rows": [
    ["Material", "Resistance"],
    ["Copper", "Low"]
  ]
}
```

---

## 14. MCQ Format

```json
{
  "questionId": "q_001",
  "language": "en",
  "marks": 1,
  "questionType": "mcq",
  "rawText": "What is the ratio of GG, Gg and gg in F2 progeny?",
  "content": {
    "stem": [
      {
        "type": "paragraph",
        "text": "What is the ratio of GG, Gg and gg in F2 progeny?"
      }
    ],
    "options": [
      { "label": "A", "content": [{ "type": "paragraph", "text": "2 : 1 : 1" }] },
      { "label": "B", "content": [{ "type": "paragraph", "text": "3 : 1 : 0" }] },
      { "label": "C", "content": [{ "type": "paragraph", "text": "1 : 1 : 2" }] },
      { "label": "D", "content": [{ "type": "paragraph", "text": "1 : 2 : 1" }] }
    ]
  },
  "metadata": {
    "classLevel": "10",
    "subject": "Science",
    "subjectArea": "Biology",
    "chapterNames": ["Heredity"],
    "topicNames": ["Monohybrid Cross"],
    "difficulty": "medium"
  },
  "source": {
    "sourceType": "previous_year_paper",
    "sourceName": "31-2-1 Science 2026",
    "fileName": "31-2-1.pdf",
    "pageNumber": 3,
    "originalQuestionNumber": "1"
  }
}
```

---

## 15. Assertion-Reason Format

```json
{
  "questionId": "q_008",
  "language": "en",
  "marks": 1,
  "questionType": "assertion_reason",
  "rawText": "Assertion and reason question...",
  "content": {
    "assertion": [
      { "type": "paragraph", "text": "Assertion (A): Blood plasma transports carbon dioxide in dissolved form." }
    ],
    "reason": [
      { "type": "paragraph", "text": "Reason (R): Carbon dioxide is more soluble in water than oxygen." }
    ],
    "options": [
      { "label": "A", "content": [{ "type": "paragraph", "text": "Both A and R are true and R is the correct explanation of A." }] },
      { "label": "B", "content": [{ "type": "paragraph", "text": "Both A and R are true but R is not the correct explanation of A." }] },
      { "label": "C", "content": [{ "type": "paragraph", "text": "A is true but R is false." }] },
      { "label": "D", "content": [{ "type": "paragraph", "text": "A is false but R is true." }] }
    ]
  },
  "metadata": {
    "classLevel": "10",
    "subject": "Science",
    "subjectArea": "Biology",
    "chapterNames": ["Life Processes"],
    "topicNames": ["Transportation"],
    "difficulty": "medium"
  },
  "source": {
    "sourceType": "previous_year_paper",
    "sourceName": "31-2-1 Science 2026"
  }
}
```

---

## 16. Short / Long Answer Format

```json
{
  "questionId": "q_010",
  "language": "en",
  "marks": 2,
  "questionType": "short_answer",
  "rawText": "State two functions of stomata.",
  "content": {
    "stem": [
      { "type": "paragraph", "text": "State two functions of stomata." }
    ]
  },
  "metadata": {
    "classLevel": "10",
    "subject": "Science",
    "subjectArea": "Biology",
    "chapterNames": ["Life Processes"],
    "topicNames": ["Stomata"],
    "difficulty": "easy"
  },
  "source": {
    "sourceType": "previous_year_paper",
    "sourceName": "31-2-1 Science 2026"
  }
}
```

Long answer with subparts:

```json
{
  "questionId": "q_011",
  "language": "en",
  "marks": 5,
  "questionType": "long_answer",
  "rawText": "Long answer with subparts.",
  "content": {
    "stem": [],
    "subparts": [
      {
        "label": "i",
        "marks": 2,
        "content": [{ "type": "paragraph", "text": "Name the organ involved." }]
      },
      {
        "label": "ii",
        "marks": 2,
        "content": [{ "type": "paragraph", "text": "Write the pathway." }]
      },
      {
        "label": "iii",
        "marks": 1,
        "content": [{ "type": "paragraph", "text": "Mention one feature." }]
      }
    ]
  },
  "metadata": {
    "classLevel": "10",
    "subject": "Science",
    "chapterNames": ["Life Processes"],
    "topicNames": [],
    "difficulty": "medium"
  },
  "source": {
    "sourceType": "question_bank",
    "sourceName": "School Science Question Bank"
  }
}
```

---

## 17. Case-Based Format

Case-based questions need a passage and subparts.

```json
{
  "questionId": "q_015",
  "language": "en",
  "marks": 4,
  "questionType": "case_based",
  "rawText": "Case-based question with passage and subparts.",
  "content": {
    "passage": [
      {
        "type": "paragraph",
        "text": "A middle-aged person is facing some cognitive changes..."
      }
    ],
    "subparts": [
      {
        "label": "a",
        "marks": 1,
        "content": [
          { "type": "paragraph", "text": "What are voluntary actions?" }
        ]
      },
      {
        "label": "b",
        "marks": 1,
        "content": [
          { "type": "paragraph", "text": "Which part of the brain controls precision of voluntary actions?" }
        ]
      },
      {
        "label": "c",
        "marks": 2,
        "content": [
          { "type": "paragraph", "text": "Explain the role of the medulla." }
        ]
      }
    ]
  },
  "metadata": {
    "classLevel": "10",
    "subject": "Science",
    "subjectArea": "Biology",
    "chapterNames": ["Control and Coordination"],
    "topicNames": ["Human Brain"],
    "difficulty": "medium"
  },
  "source": {
    "sourceType": "previous_year_paper",
    "sourceName": "31-2-1 Science 2026"
  }
}
```

---

## 18. Internal Choice / OR Format

For questions with internal OR choice, use `choices` instead of hiding the choice inside `rawText`.

```json
{
  "questionId": "q_016",
  "language": "en",
  "marks": 5,
  "questionType": "long_answer",
  "rawText": "Long answer question with OR choice.",
  "content": {
    "choices": [
      {
        "displayStyle": "or",
        "chooseCount": 1,
        "options": [
          {
            "label": "A",
            "marks": 5,
            "content": [
              { "type": "paragraph", "text": "Explain the process of digestion in human beings." }
            ]
          },
          {
            "label": "B",
            "marks": 5,
            "content": [
              { "type": "paragraph", "text": "Explain the mechanism of breathing in humans." }
            ]
          }
        ]
      }
    ]
  },
  "metadata": {
    "classLevel": "10",
    "subject": "Science",
    "subjectArea": "Biology",
    "chapterNames": ["Life Processes"],
    "topicNames": ["Digestion", "Respiration"],
    "difficulty": "medium"
  },
  "source": {
    "sourceType": "previous_year_paper",
    "sourceName": "31-2-1 Science 2026"
  }
}
```

---

## 19. Assets

If a question has an image, graph, table, or diagram, include an asset reference.

```json
{
  "assetId": "asset_001",
  "assetType": "image",
  "mimeType": "image/png",
  "url": "https://cdn.example.com/assets/asset_001.png",
  "caption": "Circuit diagram",
  "altText": "A circuit diagram showing a resistor connected to a battery."
}
```

Question content can refer to it:

```json
{
  "type": "image",
  "assetId": "asset_001",
  "caption": "Observe the given circuit diagram."
}
```

For V1, if asset handling is not ready, backend should still include `rawText` and an `image_placeholder` content item.

---

## 20. Question Metadata

```json
{
  "classLevel": "10",
  "subject": "Science",
  "subjectArea": "Biology",
  "chapterIds": ["heredity"],
  "chapterNames": ["Heredity"],
  "topicIds": ["monohybrid_cross"],
  "topicNames": ["Monohybrid Cross"],
  "difficulty": "medium",
  "cognitiveLevel": "apply",
  "estimatedMinutes": 1,
  "requiresDiagram": false,
  "requiresCalculation": false,
  "requiresTable": false,
  "keywords": ["genotype", "F2 progeny"]
}
```

| Field | Required | Why |
|---|---:|---|
| `classLevel` | Yes | Filtering and display. |
| `subject` | Yes | Filtering and display. |
| `chapterNames` | Yes | Teacher-facing chapter display. |
| `difficulty` | Yes | Easier/harder swap and validation. |
| `topicNames` | Strongly recommended | Topic-level swap/change. |
| `subjectArea` | Recommended | Useful for CBSE Science sections. |
| `cbseRelevance` | Optional | Useful for inspector display and review. Can be an enum such as `low`, `medium`, `high` or a numeric rating. |
| `cognitiveLevel` | Optional | Useful for review and difficulty analysis. |
| `chapterIds` | Optional | Stable backend filtering. |
| `topicIds` | Optional | Stable backend filtering. |
| `keywords` | Optional | Search and duplicate detection. |

V1 does not include answer-key mutation in this paper editor contract. If answer
keys are returned later, they should be added as a separate, permissioned
extension and should not be edited by the V1 AI editor flow.

---

## 21. Source Object

Teachers trust questions more when they can see where they came from.

```json
{
  "sourceType": "previous_year_paper",
  "sourceName": "31-2-1 Science 2026",
  "fileName": "31-2-1.pdf",
  "pageNumber": 3,
  "originalQuestionNumber": "1"
}
```

| Field | Required | Notes |
|---|---:|---|
| `sourceType` | Yes | Example: `previous_year_paper`, `sample_paper`, `question_bank`, `textbook_exercise`. |
| `sourceName` | Yes | Human-readable source. |
| `fileName` | Recommended | Useful for traceability. |
| `pageNumber` | Recommended | Useful for audits/debugging. |
| `originalQuestionNumber` | Recommended | Useful for teacher trust. |

---

## 22. Alternates for Swapping

For every slot, backend should preferably provide alternate questions.

```json
{
  "slotId": "slot_A_01",
  "displayNumber": "1",
  "marks": 1,
  "questionType": "mcq",
  "selectedQuestionId": "q_001",
  "alternateQuestionIds": ["q_001_alt_1", "q_001_alt_2", "q_001_alt_3"]
}
```

Alternates should match:

- same marks
- same question type
- same language
- same section or subject area where applicable
- same or nearby chapter/topic where possible
- similar or intentionally different difficulty

This powers frontend actions like:

- swap question
- make easier
- make harder
- replace from same topic
- replace from another selected topic

---

## 23. Frontend BlockNote Mapping

The frontend converts backend data into BlockNote blocks. The API payload remains the source of truth for IDs and metadata.

### Backend slot

```json
{
  "slotId": "slot_A_01",
  "displayNumber": "1",
  "marks": 1,
  "questionType": "mcq",
  "selectedQuestionId": "q_001"
}
```

### Frontend BlockNote block

```json
{
  "id": "block_slot_A_01",
  "type": "questionBlock",
  "props": {
    "slotId": "slot_A_01",
    "questionId": "q_001",
    "displayNumber": "1",
    "marks": 1,
    "questionType": "mcq",
    "locked": false
  },
  "content": []
}
```

Recommended custom editor blocks:

```text
paperHeaderBlock
instructionBlock
sectionHeaderBlock
directionBlock
questionBlock
mcqOptionBlock
casePassageBlock
subQuestionBlock
choiceGroupBlock
choiceOptionBlock
assetBlock
fallbackQuestionBlock
```

Frontend must preserve the relationship:

```text
visible editable block <-> slotId <-> selectedQuestionId <-> original backend question
```

---

## 24. Frontend Runtime Validation

Before rendering, frontend should validate:

- `schemaVersion` is `paper_document.v1`
- required top-level objects exist
- every section has stable `sectionId`
- every slot has stable `slotId`
- every slot has `displayNumber`, `marks`, `questionType`, and `selectedQuestionId`
- every slot has `locked` and `alternateQuestionIds`
- every non-null selected question exists in `questions[]`
- every alternate question ID exists in `questions[]`
- selected question marks match slot marks
- selected question type matches slot question type
- selected question language matches paper/request language
- slot overrides reference valid derived `regionKey` values for the selected question
- total slot marks match section and paper totals where possible
- duplicate selected question IDs are flagged
- unknown question/content types render via `rawText`

Runtime validation should fail loud in development and show a safe user-facing error in production.

---

## 25. Frontend Responsibilities

Frontend owns:

- BlockNote rendering
- editable paper UI
- manual editing
- AI editing UI
- swap UI using `alternateQuestionIds`
- lock/unlock UI
- change tracking by `slotId`
- final validation display
- fallback rendering for unknown types
- save/export payload construction later

Frontend does not own:

- question-bank filtering
- metadata quality
- chapter/topic tagging
- difficulty tagging
- duplicate prevention inside backend selection
- source/provenance correctness
- English-only filtering

---

## 26. Suggested Endpoints

Endpoint names can change. Conceptually, the frontend needs these.

### Assemble paper

```http
POST /api/papers/assemble
```

Returns `PaperDocumentV1`.

### Fetch replacement candidates

```http
POST /api/questions/candidates
```

Request:

```json
{
  "slotId": "slot_A_01",
  "marks": 1,
  "questionType": "mcq",
  "language": "en",
  "chapterNames": ["Heredity"],
  "topicNames": ["Monohybrid Cross"],
  "difficulty": "medium",
  "excludeQuestionIds": ["q_001"]
}
```

Response:

```json
{
  "questions": []
}
```

### Save edited paper

```http
POST /api/papers/{paperId}/save
```

Frontend sends canonical edited paper state after teacher edits.

---

## 27. Minimal Valid Payload

```json
{
  "schemaVersion": "paper_document.v1",
  "request": {
    "requestId": "req_123",
    "language": "en",
    "classLevel": "10",
    "subject": "Science",
    "examType": "full_term",
    "filters": {
      "chapters": ["Heredity"],
      "topics": ["Monohybrid Cross"],
      "englishOnly": true
    }
  },
  "template": {
    "templateId": "cbse_science_class_10_full_term_v1",
    "templateName": "CBSE Class 10 Science Full Term",
    "board": "CBSE",
    "classLevel": "10",
    "subject": "Science",
    "examType": "full_term",
    "totalMarks": 80,
    "durationMinutes": 180,
    "language": "en"
  },
  "format": {
    "formatId": "cbse_science_class_10_v1",
    "page": {
      "size": "A4",
      "orientation": "portrait"
    },
    "paperChrome": {
      "showOuterBorder": true,
      "sectionStyle": "boxed",
      "marksPlacement": "right"
    },
    "numbering": {
      "scope": "paper",
      "style": "decimal",
      "recomputeOnSectionReorder": true
    },
    "sections": {
      "allowQuestionReorderWithinSection": true,
      "allowCrossSectionMove": false
    },
    "questionRegions": {
      "allowRegionReorder": false,
      "allowRegionDelete": false
    },
    "mcqOptions": {
      "layout": "vertical"
    }
  },
  "paper": {
    "paperId": "paper_123",
    "title": "Science",
    "subtitle": "Class X",
    "totalMarks": 80,
    "durationMinutes": 180,
    "language": "en",
    "headerBlocks": [
      {
        "blockId": "header_001",
        "blockType": "paper_header",
        "text": "Science - Class X",
        "editable": true
      }
    ],
    "instructionBlocks": [
      {
        "blockId": "instruction_001",
        "blockType": "instruction",
        "text": "Maximum Marks: 80. Time allowed: 3 hours.",
        "editable": true
      }
    ],
    "sections": [
      {
        "sectionId": "A",
        "title": "Section A",
        "subtitle": "Biology",
        "marks": 30,
        "instructions": "Questions 1 to 16 are from Biology.",
        "slots": [
          {
            "slotId": "slot_A_01",
            "displayNumber": "1",
            "marks": 1,
            "questionType": "mcq",
            "selectedQuestionId": "q_001",
            "alternateQuestionIds": ["q_001_alt_1"],
            "locked": false,
            "overrides": {
              "modifiedFromSource": false,
              "regions": {}
            }
          }
        ]
      }
    ]
  },
  "questions": [
    {
      "questionId": "q_001",
      "language": "en",
      "marks": 1,
      "questionType": "mcq",
      "rawText": "What is the ratio of GG, Gg and gg in F2 progeny?",
      "content": {
        "stem": [
          {
            "type": "paragraph",
            "text": "What is the ratio of GG, Gg and gg in F2 progeny?"
          }
        ],
        "options": [
          { "label": "A", "content": [{ "type": "paragraph", "text": "2 : 1 : 1" }] },
          { "label": "B", "content": [{ "type": "paragraph", "text": "3 : 1 : 0" }] },
          { "label": "C", "content": [{ "type": "paragraph", "text": "1 : 1 : 2" }] },
          { "label": "D", "content": [{ "type": "paragraph", "text": "1 : 2 : 1" }] }
        ]
      },
      "metadata": {
        "classLevel": "10",
        "subject": "Science",
        "subjectArea": "Biology",
        "chapterNames": ["Heredity"],
        "topicNames": ["Monohybrid Cross"],
        "difficulty": "medium"
      },
      "source": {
        "sourceType": "previous_year_paper",
        "sourceName": "31-2-1 Science 2026",
        "fileName": "31-2-1.pdf",
        "pageNumber": 3,
        "originalQuestionNumber": "1"
      }
    },
    {
      "questionId": "q_001_alt_1",
      "language": "en",
      "marks": 1,
      "questionType": "mcq",
      "rawText": "In a monohybrid cross, what is the expected phenotypic ratio in F2 generation?",
      "content": {
        "stem": [
          {
            "type": "paragraph",
            "text": "In a monohybrid cross, what is the expected phenotypic ratio in F2 generation?"
          }
        ],
        "options": [
          { "label": "A", "content": [{ "type": "paragraph", "text": "1 : 1" }] },
          { "label": "B", "content": [{ "type": "paragraph", "text": "3 : 1" }] },
          { "label": "C", "content": [{ "type": "paragraph", "text": "1 : 2 : 1" }] },
          { "label": "D", "content": [{ "type": "paragraph", "text": "9 : 3 : 3 : 1" }] }
        ]
      },
      "metadata": {
        "classLevel": "10",
        "subject": "Science",
        "subjectArea": "Biology",
        "chapterNames": ["Heredity"],
        "topicNames": ["Monohybrid Cross"],
        "difficulty": "easy"
      },
      "source": {
        "sourceType": "question_bank",
        "sourceName": "School Science Question Bank"
      }
    }
  ]
}
```

---

## 28. Backend V1 Checklist

- [ ] Return one `PaperDocumentV1` response.
- [ ] Include one `format` object with CBSE V1 page/chrome/numbering/structure rules.
- [ ] Include section-wise paper structure.
- [ ] Include one slot for every question position.
- [ ] Include stable `slotId` for every slot.
- [ ] Include stable `questionId` for every selected and alternate question.
- [ ] Include `displayNumber`, `marks`, and `questionType` for every slot.
- [ ] Include `locked` and `alternateQuestionIds` for every slot.
- [ ] Preserve paper-specific question text edits as slot-level overrides; do not mutate source question content in `questions[]`.
- [ ] Include `rawText` for every question.
- [ ] Include structured `content` for every question.
- [ ] Include chapter/topic metadata for every question.
- [ ] Include difficulty metadata for every question.
- [ ] Include source information for every question.
- [ ] Return English-only questions when `englishOnly` is true.
- [ ] Include alternate questions for swaps where possible.
- [ ] Include asset references or placeholders for diagrams/tables/images where possible.

---

## 29. Final V1 Rule

The frontend can build the MVP if backend reliably provides:

```text
paper.sections[].slots[]
questions[]
format
stable paperId/templateId/formatId/sectionId/slotId/questionId
marks/questionType/language/chapter/topic/difficulty/source/rawText
slot overrides for paper-specific edits
```

Everything else can be additive after the first working block editor flow.
