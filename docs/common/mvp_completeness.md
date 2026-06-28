# MVP Completeness

Goal: teacher can grow the bank with generated Q&A, assemble a paper, review it with answers visible, and export usable final artifacts.

## Required loops

1. **Bank-growth loop**: Generate AI Q&A → review candidates → import accepted Q&A → persisted as `Question` rows with answers.
2. **Paper artifact loop**: Setup → generate paper → review/edit/swap questions → view answers → save → preview/download question paper + answer key.

## Next issues, in order

1. **#110 — Editor answer review**
   - Add `Show answer` to the selected-question tray.
   - Open an alternatives-style answer overlay.
   - Load paper-local answers via `GET /api/papers/{id}/editor-draft/`.
   - Warn only for AI-generated/unverified answers.
   - No answer editing in this slice.

2. **#148 — Paper setup product shape**
   - Replace the old coverage form with minimal paper setup.
   - Show fixed Class 10 Science context, format/chapters, and live structure summary.
   - Keep AI Q&A generation as a distinct secondary workflow.

3. **#121 + #197 — Answer-key print surface**
   - Frontend answer-key print route from saved `answer_document`.
   - Backend answer-key PDF should use browser print route first, ReportLab fallback.

4. **#118 + #123 — Final download flow**
   - Simplify editor command bar.
   - One final download action should save dirty state first, then download the final artifact package.

5. **#135 — Real-corpus paper generation confidence**
   - Verify generated paper JSON from the loaded real corpus is contract-compliant and usable.

6. **#152 — Incomplete assembly recovery**
   - If paper assembly cannot fill slots, guide teacher into AI Q&A generation for missing needs instead of opening an incomplete paper.

## Stale / likely close or update

- **#146**: Q&A import persistence appears implemented and manually verified.
- **#141**: likely superseded by later grounded-generation/model evaluation work.
- **#130**: upload UI appears implemented.
- **#125**: backend validation decision appears implemented via `validate_answer_document`.
- **#145/#147**: check exact acceptance, then close/update if covered by current generation batch flow.

## Deferred beyond current MVP slice

- Answer editing in the editor.
- AI editor proposal flows (#30–36).
- Advanced question-type/source-mix controls unless needed for demo fidelity.
- V2 editor overlay/schema polish beyond current question editing.
