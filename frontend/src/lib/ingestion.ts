/**
 * Pure helpers for the PDF upload (ingestion) flow: source-type vocabulary,
 * client-side file validation, status classification, and display formatting.
 * No React, no network — the page and hook compose these.
 *
 * @module ingestion
 */
import type { IngestionJob, IngestionJobStatus, SourceType } from '@/types';

export interface SourceTypeOption {
  value: SourceType;
  label: string;
  hint: string;
}

/**
 * Provenance choices a teacher can tag an upload with. Order and default
 * (`previous_year_paper`) mirror the backend `SourceType` choices.
 */
export const SOURCE_TYPE_OPTIONS: SourceTypeOption[] = [
  {
    value: 'previous_year_paper',
    label: 'Previous-year paper',
    hint: 'An actual CBSE board exam paper from a past year.',
  },
  {
    value: 'sample_paper',
    label: 'Sample paper',
    hint: 'A CBSE-published sample or model paper.',
  },
  {
    value: 'question_bank',
    label: 'Question bank',
    hint: 'A compiled set of practice questions or reference material.',
  },
];

export const DEFAULT_SOURCE_TYPE: SourceType = 'previous_year_paper';

/**
 * The AI Q&A workflow tags its questions `ai_generated`. Teachers never *upload*
 * a paper with this provenance, so it is deliberately excluded from
 * `SOURCE_TYPE_OPTIONS` (the upload picker). It belongs only where existing bank
 * questions are browsed or filtered.
 */
export const AI_GENERATED_SOURCE_OPTION: SourceTypeOption = {
  value: 'ai_generated',
  label: 'AI-generated',
  hint: 'A question drafted by the AI Q&A workflow.',
};

/**
 * Every source type that can appear on a question already in the bank — the
 * upload provenance choices plus `ai_generated`. Use this for browse/filter
 * surfaces; use `SOURCE_TYPE_OPTIONS` for the upload picker.
 */
export const BANK_SOURCE_TYPE_OPTIONS: SourceTypeOption[] = [
  ...SOURCE_TYPE_OPTIONS,
  AI_GENERATED_SOURCE_OPTION,
];

export function sourceTypeLabel(value: SourceType): string {
  return (
    BANK_SOURCE_TYPE_OPTIONS.find((option) => option.value === value)?.label ??
    value
  );
}

/** Generous ceiling — board papers are small, but scans can be heavy. */
export const MAX_PDF_BYTES = 25 * 1024 * 1024;

/**
 * Validate a chosen file before upload. Returns a human-readable reason, or
 * `null` when the file is acceptable. The backend re-validates; this is a fast,
 * friendly client-side gate.
 */
export function validatePdfFile(file: File): string | null {
  const isPdf =
    file.type === 'application/pdf' || /\.pdf$/i.test(file.name ?? '');
  if (!isPdf) {
    return 'That file isn’t a PDF. Upload a .pdf paper.';
  }
  if (file.size === 0) {
    return 'That file is empty. Choose a different PDF.';
  }
  if (file.size > MAX_PDF_BYTES) {
    return `That PDF is ${formatFileSize(file.size)} — the limit is ${formatFileSize(
      MAX_PDF_BYTES,
    )}.`;
  }
  return null;
}

const TERMINAL_INGESTION_STATUSES = new Set<IngestionJobStatus>([
  'done',
  'failed',
]);

export function isIngestionTerminal(status: IngestionJobStatus): boolean {
  return TERMINAL_INGESTION_STATUSES.has(status);
}

/** True when the job's latest timestamp is inside the supplied recency window. */
export function isIngestionJobRecent(
  job: IngestionJob,
  maxAgeMs: number,
  now = Date.now(),
): boolean {
  const timestamp = Date.parse(job.updated_at || job.created_at);
  return Number.isFinite(timestamp) && now - timestamp <= maxAgeMs;
}

/** Format a byte count as a compact, human-readable size. */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(mb < 10 ? 1 : 0)} MB`;
}
