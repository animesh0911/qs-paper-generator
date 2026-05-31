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

---

## 3. Top-Level Object

```json
{
  "schemaVersion": "paper_document.v1",
  "request": {},
  "template": {},
  "paper": {},
  "questions": []
}
```

| Field | Required | Purpose |
|---|---:|---|
| `schemaVersion` | Yes | Identifies the contract version. Must be `paper_document.v1`. |
| `request` | Yes | Teacher/user input that produced the paper. |
| `template` | Yes | Expected paper format and constraints. |
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

---

## 6. Paper Object

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

## 7. Editable Text Blocks

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
  "blockType": "general_instruction",
  "text": "This question paper contain 39 questions. All questions are compulsory.",
  "editable": true
}
```

| Field | Required | Notes |
|---|---:|---|
| `blockId` | Yes | Stable block ID. |
| `blockType` | Yes | Example: `paper_header`, `note_heading`, `note`, `general_instructions_heading`, `general_instruction`, `direction`. |
| `text` | Yes | Rendered text. |
| `editable` | Optional | Defaults to `true`. |

For the CBSE Class 10 Science MVP, `paper.instructionBlocks[]` should model the
front-matter instructions visible on the paper, not only app help text. The
2026 Science papers use a NOTE block followed by General Instructions. A
representative English-only instruction block sequence is:

- `note_heading`: `NOTE`
- `note`: printed page count / question count / serial-number / reading-time
  notices
- `general_instructions_heading`: `General Instructions`
- `general_instruction`: compulsory questions, section split, question types,
  case-based question rule, answer-sheet sectioning, and internal choice rule

---

## 8. Sections

Each section contains section metadata and ordered slots.

```json
{
  "sectionId": "A",
  "title": "Section A",
  "subtitle": "Biology",
  "marks": 30,
  "instructions": "Answer the Biology questions in this section. Instructions are given with each question, wherever necessary.",
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

## 9. Slots

A slot is a position in the paper. It defines what kind of question belongs there.

```json
{
  "slotId": "slot_A_01",
  "displayNumber": "1",
  "marks": 1,
  "questionType": "mcq",
  "selectedQuestionId": "q_001",
  "alternateQuestionIds": ["q_001_alt_1", "q_001_alt_2"],
  "locked": false
}
```

| Field | Required | Purpose |
|---|---:|---|
| `slotId` | Yes | Stable slot ID for editing, locking, swapping, and save operations. |
| `displayNumber` | Yes | Visible number, e.g. `1`, `16`, `16(a)`. |
| `marks` | Yes | Marks expected for this slot. |
| `questionType` | Yes | Expected type for this slot. |
| `selectedQuestionId` | Yes | Question currently selected for this slot. |
| `alternateQuestionIds` | Optional but recommended | Enables instant frontend swap. |
| `locked` | Optional | If true, frontend should preserve this slot during regeneration. |

The selected question should match the slot on:

- `marks`
- `questionType`
- `language`
- selected chapters/topics where applicable

Every `selectedQuestionId` and every ID in `alternateQuestionIds` must exist in `questions[]`.

---

## 10. Question Object

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

---

## 11. Recommended Question Types

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

## 12. Content Items

Question content should be structured but simple.

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

## 13. MCQ Format

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

## 14. Assertion-Reason Format

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

## 15. Short / Long Answer Format

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

## 16. Case-Based Format

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

## 17. Internal Choice / OR Format

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

## 18. Assets

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

## 19. Question Metadata

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
| `chapterIds` | Optional | Stable backend filtering. |
| `topicIds` | Optional | Stable backend filtering. |
| `keywords` | Optional | Search and duplicate detection. |

---

## 20. Source Object

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

## 21. Alternates for Swapping

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

## 22. Frontend BlockNote Mapping

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

## 23. Frontend Runtime Validation

Before rendering, frontend should validate:

- `schemaVersion` is `paper_document.v1`
- required top-level objects exist
- every section has stable `sectionId`
- every slot has stable `slotId`
- every slot has `displayNumber`, `marks`, `questionType`, and `selectedQuestionId`
- every selected question exists in `questions[]`
- every alternate question ID exists in `questions[]`
- selected question marks match slot marks
- selected question type matches slot question type
- selected question language matches paper/request language
- total slot marks match section and paper totals where possible
- duplicate selected question IDs are flagged
- unknown question/content types render via `rawText`

Runtime validation should fail loud in development and show a safe user-facing error in production.

---

## 24. Frontend Responsibilities

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

## 25. Suggested Endpoints

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

## 26. Minimal Valid Payload

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
        "blockId": "note_heading",
        "blockType": "note_heading",
        "text": "NOTE",
        "editable": true
      },
      {
        "blockId": "note_question_count",
        "blockType": "note",
        "text": "Please check that this question paper contains 39 questions.",
        "editable": true
      },
      {
        "blockId": "general_instructions_heading",
        "blockType": "general_instructions_heading",
        "text": "General Instructions",
        "editable": true
      },
      {
        "blockId": "general_instruction_sections",
        "blockType": "general_instruction",
        "text": "The question paper is divided into three sections — A, B and C. Section A: Biology (30 marks), Section B: Chemistry (25 marks), Section C: Physics (25 marks).",
        "editable": true
      }
    ],
    "sections": [
      {
        "sectionId": "A",
        "title": "Section A",
        "subtitle": "Biology",
        "marks": 30,
        "instructions": "Answer the Biology questions in this section. Instructions are given with each question, wherever necessary.",
        "slots": [
          {
            "slotId": "slot_A_01",
            "displayNumber": "1",
            "marks": 1,
            "questionType": "mcq",
            "selectedQuestionId": "q_001",
            "alternateQuestionIds": ["q_001_alt_1"],
            "locked": false
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

## 27. Backend V1 Checklist

- [ ] Return one `PaperDocumentV1` response.
- [ ] Include section-wise paper structure.
- [ ] Include one slot for every question position.
- [ ] Include stable `slotId` for every slot.
- [ ] Include stable `questionId` for every selected and alternate question.
- [ ] Include `displayNumber`, `marks`, and `questionType` for every slot.
- [ ] Include `rawText` for every question.
- [ ] Include structured `content` for every question.
- [ ] Include chapter/topic metadata for every question.
- [ ] Include difficulty metadata for every question.
- [ ] Include source information for every question.
- [ ] Return English-only questions when `englishOnly` is true.
- [ ] Include alternate questions for swaps where possible.
- [ ] Include asset references or placeholders for diagrams/tables/images where possible.

---

## 28. Final V1 Rule

The frontend can build the MVP if backend reliably provides:

```text
paper.sections[].slots[]
questions[]
stable paperId/templateId/sectionId/slotId/questionId
marks/questionType/language/chapter/topic/difficulty/source/rawText
```

Everything else can be additive after the first working block editor flow.
