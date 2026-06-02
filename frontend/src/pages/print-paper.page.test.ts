/**
 * Tests for the print-only paper route helpers.
 *
 * These tests pin the mock print route contract: after the mock document is
 * rendered, the browser print dialog should open without requiring Cmd+P.
 *
 * @module printPaperPageTests
 */
import { describe, expect, it, vi } from 'vitest';
import { mockPaperDocumentV1 } from '@/mocks';
import { scheduleMockPrintDialog } from '@/lib/print-paper';

describe('print paper page helpers', () => {
  it('schedules native printing only after a mock paper has rendered', () => {
    const setTimeout = vi.fn((callback: () => void) => {
      callback();
      return 10;
    });
    const clearTimeout = vi.fn();
    const print = vi.fn();

    const cleanup = scheduleMockPrintDialog({
      paper: mockPaperDocumentV1,
      isMockPrint: true,
      print,
      setTimeout,
      clearTimeout,
    });

    expect(print).toHaveBeenCalledOnce();
    cleanup?.();
    expect(clearTimeout).toHaveBeenCalledWith(10);
  });

  it('does not schedule native printing before the paper is available', () => {
    const setTimeout = vi.fn();

    const cleanup = scheduleMockPrintDialog({
      paper: null,
      isMockPrint: true,
      print: vi.fn(),
      setTimeout,
      clearTimeout: vi.fn(),
    });

    expect(cleanup).toBeUndefined();
    expect(setTimeout).not.toHaveBeenCalled();
  });
});
