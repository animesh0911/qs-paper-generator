/**
 * Barrel exports for focused editor chrome modules.
 *
 * The editor page imports from this seam so component extraction stays local to
 * `src/components/editor`.
 *
 * @module editorComponents
 */
export { EditorInspector } from './editor-inspector.component';
export { EditorAlternativesOverlay } from './editor-alternatives-overlay.component';
export { QuestionEditOverlay } from './question-edit-overlay.component';
export { EditorOutlineRail } from './editor-outline-rail.component';
export { PaperChromeEditor } from './paper-chrome-editor.component';
export { QuestionActionRail } from './question-action-rail.component';
export { QuestionRegionEditor } from './question-region-editor.component';
export { SortableQuestionSlot } from './sortable-question-slot.component';
export type { AlternativesIntent, InspectorMode } from './editor-types';
