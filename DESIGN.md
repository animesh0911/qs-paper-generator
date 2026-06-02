---
name: Question Paper Generator
description: A quiet exam-paper review workspace for CBSE teachers.
colors:
  background: "#ffffff"
  foreground: "#020817"
  paper-ink: "#050505"
  paper-mark: "#171717"
  secondary: "#f1f5f9"
  muted-foreground: "#64748b"
  border: "#e2e8f0"
typography:
  paper:
    fontFamily: "Times New Roman, Times, serif"
    fontSize: "12pt"
    fontWeight: 400
    lineHeight: 1.22
  ui-body:
    fontFamily: "system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  ui-label:
    fontFamily: "system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  sm: "4px"
  md: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  editor-mark-chip:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.muted-foreground}"
    rounded: "{rounded.sm}"
  button-primary:
    backgroundColor: "{colors.foreground}"
    textColor: "{colors.background}"
    rounded: "{rounded.md}"
---

# Design System: Question Paper Generator

## 1. Overview

**Creative North Star: "The Exam Desk"**

The interface should feel like a clear review desk for a real exam paper. App chrome stays restrained and familiar, while the paper canvas receives the typographic care and attention. The teacher should always understand what is editable, what is canonical structure, and what will appear in the final paper.

This system rejects marketing-page visuals, playful AI-writing flourishes, heavy gradients, and over-decorated cards. The paper is the main object, and the surrounding tools support careful inspection.

**Key Characteristics:**

- Paper-first hierarchy with quiet app chrome.
- Legible long-session typography.
- Marks, numbering, and edit state shown once, in predictable places.
- Standard product controls with visible focus and hover states.

## 2. Colors

The palette is restrained: white paper, dark ink, cool neutral chrome, and one dark primary action color.

### Primary

- **Action Ink** (#020817): Used for primary buttons, focus rings, and active interface states.

### Neutral

- **Paper White** (#ffffff): The paper and main surface background.
- **Paper Ink** (#050505): Canonical exam-paper text.
- **Paper Mark** (#171717): Marks and structured question metadata that must remain readable but secondary to the question text.
- **Chrome Wash** (#f1f5f9): Sidebars, hover states, selected rows, and non-paper UI surfaces.
- **Quiet Label** (#64748b): Low-priority UI labels only, never long body copy on tinted backgrounds.
- **Hairline Border** (#e2e8f0): Dividers, rails, and low-emphasis component outlines.

**The One-Mark Rule.** A question row should render one marks source: either the slot mark for simple Questions or subpart marks for structured Questions, never both. In the editor, marks are muted metadata chips; in rendered PDFs, marks follow the paper contract.

## 3. Typography

**Display Font:** system UI stack
**Body Font:** system UI stack
**Paper Font:** Times New Roman, with Times fallback

**Character:** The app uses familiar product typography for controls and panels. The paper canvas uses the established Times-style exam-paper stack so teachers can judge the final document without BlockNote changing the look during editing.

### Hierarchy

- **Paper body** (400, 12pt in the editor, 13.5pt in print surfaces, 1.22): Question text, instructions, and editable BlockNote regions.
- **Paper title** (700, 18px to 21pt, tight line-height): Paper and section headings only.
- **Question number** (600, paper body size): Stable row number aligned left of the question.
- **Marks** (600 UI label for editor chips, paper-size for PDF/subpart marks): Slot marks in the editor use a muted chip treatment; rendered PDFs use paper notation. Both are aligned consistently and shown once.
- **UI body** (400, 14px, 1.5): Rails, inspector, action labels, and chat.
- **UI label** (500, 12px, 1.4): Metadata chips, validation labels, and toolbar labels.

**The Inheritance Rule.** Static question text and active BlockNote text must inherit the same paper font, size, and line-height.

## 4. Elevation

The editor is flat by default. Depth is conveyed through layout, borders, and selected-row fills instead of decorative shadows. Shadows are reserved for drag state, overlays, and menus where the element temporarily leaves the document flow.

### Shadow Vocabulary

- **Drag lift** (`0 10px 28px rgba(15, 23, 42, 0.16)`): Used only while a question Slot is actively dragged.

**The Flat Paper Rule.** The paper canvas should not look like a floating marketing card. It is a working document surface.

## 5. Components

### Buttons

- **Shape:** Rounded rectangle, 8px radius.
- **Primary:** Dark ink background with white text.
- **Hover / Focus:** Use existing shadcn focus rings and subtle neutral hover fills.
- **Icon buttons:** Use lucide icons for editor actions and keep text labels for major commands.

### Chips

- **Style:** Small, restrained labels for metadata such as type, lock state, and validation counts.
- **State:** Selected and warning states must not rely on color alone.

### Cards / Containers

- **Corner Style:** 8px or less unless inherited from shadcn components.
- **Background:** White for the paper, cool neutral for app chrome.
- **Shadow Strategy:** Flat at rest, shadow only for drag or overlay state.
- **Border:** Hairline borders for rails and panels.
- **Internal Padding:** Dense but readable, optimized for repeated review.

### Inputs / Fields

- **Style:** Standard shadcn text fields and BlockNote editing surfaces.
- **Focus:** Visible ring or selected-row state.
- **Error / Disabled:** Keep labels readable at WCAG AA contrast.

### Navigation

- **Style:** Left outline rail, top command bar, right inspector.
- **Behavior:** The current paper section and selected Slot should be apparent without hiding paper content.

## 6. Do's and Don'ts

Do keep the paper canvas visually dominant. Do keep thin, light full boundaries around sections and thin separators between question rows in the editor. Do align marks, numbers, and editable regions with stable dimensions. Do keep the slot marks column narrow and visibly quieter than question text so it reads as review metadata, not a second question column. Do allow the editor surface to be wider than the PDF contract when it improves review ergonomics; keep exact dimensions for rendered PDF and print routes. Do verify click-state typography in the browser after changing BlockNote styling.

Do not show both slot marks and structured subpart marks for the same Question. Do not remove editor row boundaries while polishing print styling. Do not use decorative gradients, oversized landing-page type, nested cards, or novelty controls in the editor. Do not let BlockNote introduce a different font when a question becomes editable.
