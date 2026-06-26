/**
 * Single source of truth: generate the backend's JSON Schema from the Zod
 * schema, and guard against drift.
 *
 * The Zod schema in `paper-document.schema.ts` is the one definition of the
 * PaperDocumentV1 *shape*. The Python backend can't import Zod, so it validates
 * against a JSON Schema generated from it (committed at
 * `backend/papers/paper_document_v1.schema.json`). This test regenerates that
 * artifact and asserts the committed copy matches — so the two sides can never
 * silently diverge. Run `npm run schema:export` to update the committed file
 * after intentionally changing the Zod schema.
 *
 * Note: Zod `.superRefine` (the slot↔question referential-integrity checks)
 * cannot be expressed in JSON Schema and is intentionally dropped here; the
 * backend mirrors it as a separate Python check in `papers/document_contract`.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { z } from 'zod';
import { describe, expect, it } from 'vitest';
import { paperDocumentSchema } from './paper-document.schema';

const SCHEMA_PATH = fileURLToPath(
  new URL(
    '../../../backend/papers/paper_document_v1.schema.json',
    import.meta.url,
  ),
);

function generateJsonSchema(): string {
  const jsonSchema = z.toJSONSchema(paperDocumentSchema, {
    // Unrepresentable pieces (none expected) should error loudly rather than
    // silently produce a permissive schema.
    unrepresentable: 'throw',
  });
  return `${JSON.stringify(jsonSchema, null, 2)}\n`;
}

describe('paper-document JSON Schema export', () => {
  it('matches the committed backend artifact (run npm run schema:export to update)', () => {
    const generated = generateJsonSchema();
    if (process.env.UPDATE_SCHEMA) {
      writeFileSync(SCHEMA_PATH, generated);
      return;
    }
    const committed = readFileSync(SCHEMA_PATH, 'utf8');
    expect(generated).toEqual(committed);
  });
});
