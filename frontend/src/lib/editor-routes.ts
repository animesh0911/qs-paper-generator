/**
 * Editor route builders.
 *
 * Keeps deterministic Paper id formatting out of page orchestration.
 *
 * @module editorRoutes
 */

export function generatedPaperEditorPath(paperId: string) {
  return `/editor/${paperId}`;
}
