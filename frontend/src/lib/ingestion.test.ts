import { describe, expect, it } from 'vitest';
import {
  MAX_PDF_BYTES,
  SOURCE_TYPE_OPTIONS,
  formatFileSize,
  isIngestionTerminal,
  sourceTypeLabel,
  validatePdfFile,
} from './ingestion';

function fakeFile({
  name = 'paper.pdf',
  type = 'application/pdf',
  size = 1024,
}: {
  name?: string;
  type?: string;
  size?: number;
} = {}): File {
  return { name, type, size } as File;
}

describe('validatePdfFile', () => {
  it('accepts a PDF by mime type', () => {
    expect(validatePdfFile(fakeFile())).toBeNull();
  });

  it('accepts a PDF by extension when mime is missing', () => {
    expect(
      validatePdfFile(fakeFile({ type: '', name: 'CBSE-2023.PDF' })),
    ).toBeNull();
  });

  it('rejects non-PDF files', () => {
    expect(validatePdfFile(fakeFile({ name: 'paper.docx', type: '' }))).toMatch(
      /isn.t a PDF/i,
    );
  });

  it('rejects empty files', () => {
    expect(validatePdfFile(fakeFile({ size: 0 }))).toMatch(/empty/i);
  });

  it('rejects files over the size limit', () => {
    expect(validatePdfFile(fakeFile({ size: MAX_PDF_BYTES + 1 }))).toMatch(
      /limit/i,
    );
  });
});

describe('sourceTypeLabel', () => {
  it('maps every option value to its label', () => {
    for (const option of SOURCE_TYPE_OPTIONS) {
      expect(sourceTypeLabel(option.value)).toBe(option.label);
    }
  });

  it('defaults to previous-year paper as the first option', () => {
    expect(SOURCE_TYPE_OPTIONS[0].value).toBe('previous_year_paper');
  });
});

describe('isIngestionTerminal', () => {
  it('treats done and failed as terminal', () => {
    expect(isIngestionTerminal('done')).toBe(true);
    expect(isIngestionTerminal('failed')).toBe(true);
  });

  it('treats pending and running as non-terminal', () => {
    expect(isIngestionTerminal('pending')).toBe(false);
    expect(isIngestionTerminal('running')).toBe(false);
  });
});

describe('formatFileSize', () => {
  it('formats bytes, kilobytes, and megabytes', () => {
    expect(formatFileSize(512)).toBe('512 B');
    expect(formatFileSize(2048)).toBe('2 KB');
    expect(formatFileSize(5 * 1024 * 1024)).toBe('5.0 MB');
  });
});
