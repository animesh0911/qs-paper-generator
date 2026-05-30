---
name: Question Paper Generator
description: A print-faithful React editor for teacher-reviewed CBSE question papers.
colors:
  background: "hsl(0 0% 100%)"
  foreground: "hsl(222.2 84% 4.9%)"
  surface: "hsl(0 0% 100%)"
  surface-muted: "hsl(210 40% 96.1%)"
  border-soft: "hsl(214.3 31.8% 91.4%)"
  ink-muted: "hsl(215.4 16.3% 46.9%)"
  primary: "hsl(222.2 47.4% 11.2%)"
  destructive: "hsl(0 84.2% 60.2%)"
typography:
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: "1.5"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: "1.25"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    background: "{colors.primary}"
    foreground: "hsl(210 40% 98%)"
    rounded: "{rounded.md}"
  button-outline:
    background: "{colors.background}"
    foreground: "{colors.foreground}"
    border: "{colors.border-soft}"
    rounded: "{rounded.md}"
---

# Design System: Question Paper Generator

## 1. Overview

**Creative North Star: "The Exam Desk"**

The interface should feel like a well-organized exam desk: the paper is centered, controls are close at hand, and nothing decorative competes with the document. The teacher should immediately understand that the editor is a working surface for a real paper, not a chat toy or a database admin screen.

The system rejects generic AI writing-tool spectacle. AI affordances are present, but quiet. The visible center of gravity is the A4-like paper canvas, with section borders, question numbering, marks, and instructions matching the final printed artifact as closely as V1 allows.

**Key Characteristics:**

- Print-faithful center canvas.
- Restrained product chrome around the paper.
- High-trust metadata surfaces.
- Fast, explicit actions for swap, info, lock, review, save, and approve.
- No decorative gradients, glass panels, or marketing-style cards.

## 2. Colors

The palette is restrained: neutral document surfaces, near-black ink, soft dividers, and one dark primary action color.

### Primary

- **Exam Ink** (`hsl(222.2 47.4% 11.2%)`): primary buttons, selected command emphasis, and high-confidence actions.

### Neutral

- **Paper Surface** (`hsl(0 0% 100%)`): the editable paper canvas and printable regions.
- **Workspace Wash** (`hsl(210 40% 96.1%)`): app background, tool rails, and inactive utility areas.
- **Soft Rule** (`hsl(214.3 31.8% 91.4%)`): borders, dividers, section outlines, and low-emphasis containers.
- **Muted Ink** (`hsl(215.4 16.3% 46.9%)`): secondary labels and metadata. Do not use it for long body copy unless contrast is verified.

### Named Rules

**The Paper First Rule.** The paper canvas stays white or near-white. Product chrome may tint, but the exam document surface remains visually printable.

**The Rare Accent Rule.** Accent color is used for selected state, primary actions, and validation status only. It is not decoration.

## 3. Typography

**Display Font:** system sans-serif stack.
**Body Font:** system sans-serif stack.
**Label/Mono Font:** system sans-serif stack unless code-like IDs need a monospace treatment later.

**Character:** Native, quiet, and familiar. The editor should feel closer to a document tool than a branded website.

### Hierarchy

- **Page Title** (600, 18px, 1.3): paper name in the top bar.
- **Section Heading** (700, 16px, 1.35): printed section labels inside the paper.
- **Question Text** (400, 15px to 16px, 1.55): editable question regions.
- **Metadata Label** (500, 12px to 13px, 1.25): compact tray and inspector labels.
- **Button Label** (500, 14px, 1.25): command text.

### Named Rules

**The Exam Legibility Rule.** Question text must read comfortably at print scale. Never shrink core question text to fit more controls.

**The Tooling Is Smaller Rule.** Inspector labels, trays, and chat UI are visually secondary to the paper body.

## 4. Elevation

The system is flat by default. Depth comes from layout, borders, and tonal separation. Shadows may appear only for floating action trays, popovers, and active drag states, and should stay tight enough to feel functional.

### Shadow Vocabulary

- **Floating Tray** (`0 8px 24px rgba(15, 23, 42, 0.12)`): contextual question tray and popover surfaces only.
- **Drag Lift** (`0 10px 28px rgba(15, 23, 42, 0.16)`): temporary state while moving a question within a section.

### Named Rules

**The Flat Document Rule.** The paper itself is not a card stack. Borders and spacing define structure; shadows are reserved for transient UI.

## 5. Components

### Buttons

- **Shape:** modest radius (6px). Full pills are allowed only for compact metadata chips.
- **Primary:** Exam Ink background, light text, compact height for toolbars.
- **Hover / Focus:** color shift and visible focus ring. No animated scale on standard buttons.
- **Secondary / Ghost:** neutral surface with clear hover background. Use for utilities and tray actions.

### Chips

- **Style:** small rounded pills for chapter, topic, difficulty, source, lock state, and modified-from-source state.
- **State:** selected filters use a filled or stronger border treatment. Unselected metadata chips stay quiet.

### Cards / Containers

- **Corner Style:** 8px maximum for panels. The paper canvas can use square or near-square corners to feel printable.
- **Background:** white paper, tinted workspace, neutral inspectors.
- **Shadow Strategy:** no resting shadows on ordinary panels.
- **Border:** one-pixel neutral rules for panels, section boxes, and paper outlines.
- **Internal Padding:** dense but readable. Paper content gets more vertical rhythm than side panels.

### Inputs / Fields

- **Style:** neutral background, one-pixel border, 6px radius.
- **Focus:** clear ring using the primary ink family.
- **Error / Disabled:** error text and border must not rely on color alone. Disabled controls show reason text when the action is important.

### Navigation

- **Style:** top bar for document-level actions; left rail for outline and validation; right panel for selected context. The center paper canvas remains the visual anchor.

### Signature Component: Paper Canvas

The paper canvas is an A4-like editable document surface. It shows headers, instructions, section boundaries, questions, marks, internal choices, and options in a print-faithful layout. Contextual actions appear around selected questions and disappear from the paper print surface.

## 6. Do's and Don'ts

### Do:

- **Do** make the center canvas look close to the final printed paper.
- **Do** keep source, difficulty, tags, relevance, and modified status available near the selected question.
- **Do** use stable region blocks for stem, options, passages, subquestions, and internal-choice separators.
- **Do** keep AI affordances secondary unless the teacher explicitly opens chat or review.
- **Do** verify contrast for muted labels against tinted workspace backgrounds.

### Don't:

- **Don't** use generic AI writing-tool patterns that rewrite sourced content without preserving trust.
- **Don't** use dark mode with purple gradients, neon accents, glassmorphism, or chat-first spectacle.
- **Don't** turn the paper into a spreadsheet-like admin screen.
- **Don't** overwhelm the teacher with Word-clone chrome before paper review.
- **Don't** hide the actual paper behind decorative card-heavy SaaS dashboard layouts.
