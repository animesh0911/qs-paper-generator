/**
 * Shared editor chrome interaction types.
 *
 * These UI modes are used by the editor page and its focused chrome modules.
 *
 * @module editorTypes
 */

import type { EditorAlternativesIntent } from '@/lib/editor-paper';

export type InspectorMode = 'info' | 'alternatives';
export type AlternativesIntent = EditorAlternativesIntent;
