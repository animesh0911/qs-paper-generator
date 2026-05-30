# PRD: BlockNote Paper Editor MVP

Labels: V

## Problem Statement

Teachers need to review, edit, and finalize generated CBSE-style question papers without dealing with backend JSON or question-bank internals. The generated paper must feel like the final printed paper while still supporting controlled editing, source trust, slot-safe swaps, metadata inspection, review, approval, and exam-ready PDF export.

The current frontend still renders the older flat paper preview. It does not yet consume the richer `PaperDocumentV1` contract as a teacher-facing block editor, and it does not expose the product workflow required for manual review and final approval.

## Solution

Build a React + BlockNote paper editor that consumes a mocked/backend `PaperDocumentV1`, maps it into a print-faithful editable paper canvas, and keeps canonical paper state separate from transient BlockNote document state.

The teacher sees the formatted paper, not JSON. The editor supports selecting a question, showing a contextual question action rail, inspecting metadata, swapping through slot-wise alternatives, changing topic/difficulty by filtering alternates, manually editing question text as paper-slot overrides, locking replacement actions, reordering questions within a section, saving a draft, approving the final paper, and downloading an exam-ready PDF.

AI-facing UI is present as a bottom floating universal chat and review entry point, but live model integration is out of scope for this PRD. AI must not rewrite sourced question text. We are not adopting BlockNote AI packages in this MVP; its preview/accept/reject style may be used as product inspiration only.

## User Stories

1. As a teacher, I want to generate a paper and immediately see it as a formatted exam paper, so that I can review it like the final print artifact.
2. As a teacher, I want the editor to hide canonical JSON, so that I can work in a familiar paper interface.
3. As a teacher, I want section headers, instructions, marks, numbering, and question layout to match the generated CBSE format, so that I can trust the paper structure.
4. As a teacher, I want to select a question and see actions near that question, so that I can work without hunting through menus.
5. As a teacher, I want to inspect question metadata, so that I can understand chapter, topic, difficulty, relevance, source, marks, and type.
6. As a teacher, I want to manually edit question text, so that I can make paper-specific corrections.
7. As a teacher, I want manual edits to belong only to this paper, so that the shared question bank source is not mutated.
8. As a teacher, I want edited sourced questions marked as modified from source, so that trust and provenance remain clear.
9. As a teacher, I want to restore the original question text, so that I can undo manual paper-specific changes.
10. As a teacher, I want to swap a question using safe alternatives, so that marks, type, section, and language remain valid.
11. As a teacher, I want each slot to have its own alternatives, so that replacement safety is enforced by position.
12. As a teacher, I want to change a question topic using available alternatives, so that I can adjust coverage without regenerating the paper.
13. As a teacher, I want to make a question easier or harder using available alternatives, so that I can adjust difficulty deterministically.
14. As a teacher, I want an empty alternatives state, so that I know when no safe option matches the current filter.
15. As a teacher, I want a visible future "find more in question bank" affordance, so that the product direction is clear even though live search is out of scope.
16. As a teacher, I want to lock a question, so that replacement actions do not change it accidentally.
17. As a teacher, I want locked questions to remain manually editable, so that I can correct wording while preventing replacement.
18. As a teacher, I want to unlock a locked question, so that I can resume replacement actions.
19. As a teacher, I want to reorder questions within the same section, so that I can improve paper flow.
20. As a teacher, I do not want questions moved across sections, so that the paper blueprint remains valid.
21. As a teacher, I want question numbers recomputed after in-section reorder, so that the paper stays coherent.
22. As a teacher, I want one-step undo for structured actions, so that accidental swaps, locks, and reorder actions can be reversed quickly.
23. As a teacher, I want BlockNote typing undo to continue working, so that text edits behave naturally.
24. As a teacher, I want validation warnings visible while editing, so that I can catch problems before approval.
25. As a teacher, I want structural errors to block approval, so that invalid papers are not finalized.
26. As a teacher, I want warnings to be non-blocking where appropriate, so that I can approve intentional choices.
27. As a teacher, I want a bottom floating chatbox, so that I can ask about the editor or current paper without losing context.
28. As a teacher, I want a review button for CBSE Class 10 paper analysis, so that I can get paper-level feedback.
29. As a teacher, I want review output to appear in the bottom chat surface, so that AI-facing feedback lives in one place.
30. As a teacher, I want the approval flow to save the final canonical paper state, so that the PDF reflects my final choices.
31. As a teacher, I want the PDF to be exam-ready, so that it can be printed and used in an actual exam.
32. As a teacher, I do not want editor-only UI in the PDF, so that students see only the formal question paper.
33. As a frontend developer, I want a mock `PaperDocumentV1` with broad question variety, so that editor work can proceed without waiting on backend generation.
34. As a frontend developer, I want a clear mapping from contract questions to BlockNote block trees, so that new question types can be added without rewriting the editor.
35. As a frontend developer, I want question text regions keyed by stable region IDs, so that manual edits can be stored as slot-level overrides.
36. As a frontend developer, I want the BlockNote document regenerated from canonical JSON, so that BlockNote JSON does not become the business source of truth.
37. As a backend developer, I want the final PDF rendered from canonical `PaperDocumentV1`, so that export does not depend on transient editor DOM.
38. As a product owner, I want a spike for BlockNote PDF export, so that we can evaluate it without committing the official PDF pipeline to it.

## Implementation Decisions

- `PaperDocumentV1` remains the product source of truth.
- BlockNote document JSON is transient and regenerated from canonical paper state.
- V1 includes a required top-level `format` object carrying CBSE V1 page/chrome/numbering/structure rules.
- The editor is a React app surface inside the existing Vite frontend.
- The central paper canvas should be print-faithful, using the contract format plus the project design direction in `PRODUCT.md` and `DESIGN.md`.
- The V1 question editor uses an extensible block tree:
  - `questionContainerBlock`
  - `questionStemBlock`
  - `mcqOptionBlock`
  - `passageBlock`
  - `subQuestionBlock`
  - `internalChoiceBlock`
- Question internal region order is fixed. Teachers cannot delete or reorder regions inside a question.
- Manual edits are slot-level overrides keyed by `slotId + regionKey`; they never mutate question-bank `Question` content.
- Swapping clears manual edits for the old selected question after warning, with one-step undo available.
- V1 uses slot-wise `alternateQuestionIds`; section-wise candidate pools are future optimization.
- Change topic and easier/harder actions are deterministic filters over slot-wise alternates.
- Live question-bank search and semantic/RAG candidate discovery are out of scope for V1.
- Selecting a question shows a contextual question action rail anchored near the selected question, outside the printable content.
- The action rail contains Info, Swap, Topic, Easier, Harder, Lock/Unlock, and Ask.
- Info and alternatives render in a right inspector.
- Universal chat is always available as a bottom floating surface.
- Review paper action writes output into the bottom chat surface.
- AI cannot rewrite sourced question text.
- V1 may scaffold AI UI and mocked review behavior, but model-provider integration is covered by the separate AI editor integration PRD.
- Do not add `@blocknote/xl-ai` or BlockNote AI server packages in the MVP editor implementation. They are GPL/commercial XL packages and must be treated as inspiration/spike material unless licensing is explicitly resolved.
- BlockNote AI-inspired behavior that is allowed in our own code: scoped proposals, auto-preview, accept, reject, refine, streaming/pending states, and editor highlights for affected fields.
- Reordering questions within the same section is allowed; cross-section moves are not.
- Display numbering is derived from current paper order.
- V1 has one-step app-level undo for structured actions; BlockNote handles normal typing undo.
- Official PDF export is backend-rendered from final canonical paper state.
- BlockNote PDF export is a spike only.

## Testing Decisions

- Tests should verify behavior through public interfaces, not implementation details.
- Frontend contract tests should validate that mocked `PaperDocumentV1` normalizes into sections, slots, questions, alternates, and format rules.
- Mapper tests should verify that each supported question type produces the expected region keys and BlockNote block tree shape.
- Manual edit tests should verify that slot-level overrides render instead of original content while original question-bank content remains unchanged.
- Swap tests should verify slot identity is preserved, selected question changes, old slot edits are cleared, and undo restores previous state.
- Reorder tests should verify questions move only within a section and display numbers recompute.
- Validation tests should cover missing selected questions, mark/type mismatch, duplicate selected questions, empty edited regions, and cross-section move rejection.
- Backend PDF tests should verify approved documents render final selected questions and teacher edits, not stale bank question text.
- Existing backend paper assembly tests provide prior art for contract-level integration tests.

## Out of Scope

- Live model-provider integration for chat/review in this PRD. See the separate AI editor integration PRD.
- AI rewriting of sourced question text.
- Live question-bank search or semantic/RAG candidate discovery.
- Multi-user collaboration.
- Pixel-perfect Word clone behavior.
- Arbitrary board/template support beyond hardcoded CBSE V1.
- Persisting BlockNote document JSON.
- DOCX export.
- Full page-break fidelity inside the editor canvas.
- Answer-key generation.

## Further Notes

The next planning thread should focus on AI integration separately: secure backend model calls, provider/gateway choice, structured outputs, observability, rate limits, and prompt design.
