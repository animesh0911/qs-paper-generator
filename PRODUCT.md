# Product

## Register

product

## Users

Teachers and paper setters preparing CBSE-style question papers for real exam use. They work in a focused review mode, usually on a laptop or desktop, and need to trust the selected questions, source provenance, marks, section structure, and final print output.

## Product Purpose

Question Paper Generator turns a generated `PaperDocumentV1` contract into a teacher-facing editable paper editor. The product lets teachers review a generated paper, inspect question metadata, manually edit paper-specific question text, swap questions through slot-safe alternatives, lock decisions, review quality, approve the final document, and produce an exam-ready PDF.

Success means a teacher can look at the editor and understand how the printed paper will appear, make controlled changes without damaging the paper structure, and approve a final PDF suitable for actual examination use.

## Brand Personality

Precise, trustworthy, and calm.

The product should feel like a serious exam-preparation tool, not a marketing demo or a playful writing app. It should make complex paper assembly feel inspectable and controlled while keeping the teacher in charge.

## Anti-references

- Generic AI writing tools that rewrite sourced content without preserving trust.
- Dark mode with purple gradients, neon accents, glassmorphism, or chat-first spectacle.
- Spreadsheet-like admin screens that make the paper feel like database rows instead of an exam document.
- Word-clone chrome that overwhelms the teacher with formatting controls before paper review.
- Decorative card-heavy SaaS dashboards that hide the actual paper behind panels.

## Design Principles

1. **The paper is the center.** The main canvas must look close to the final exam paper. Tooling orbits the paper and should not invade the printed document surface.
2. **Trust before cleverness.** Source metadata, slot constraints, lock state, and modified-from-source status must be clear whenever they matter.
3. **Structure is protected.** Teachers can edit text and reorder questions within a section, but they cannot break question-region order, delete required regions, or move questions across sections.
4. **AI advises, it does not silently mutate.** V1 AI can explain, review, and suggest safe alternatives. It cannot rewrite sourced question text.
5. **Print readiness is a product feature.** The editor is not just a drafting surface. Approval must lead to a clean PDF that can be printed and used.

## Accessibility & Inclusion

Target WCAG AA for the editor surface. Body text and controls must meet contrast requirements. Keyboard navigation must reach the paper, question actions, metadata panels, swap alternatives, chat, save, approve, and PDF actions. Motion should be restrained and honor reduced-motion preferences. The product should avoid color-only status signals because teachers may rely on print previews, grayscale output, or reduced color perception.
