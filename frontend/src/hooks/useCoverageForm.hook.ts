import { useEffect, useMemo, useState } from 'react';
import { fetchChapters, fetchPaperFormats } from '@/lib/api';
import type { AssembleRequest, Chapter, PaperFormatSummary } from '@/types';

type Difficulty = NonNullable<AssembleRequest['difficulty']>;
export const DIFFICULTIES: Difficulty[] = ['easy', 'standard', 'hard'];

export interface CoverageForm {
  chapters: Chapter[];
  formats: PaperFormatSummary[];
  selectedFormatId: string;
  chapterNameBySlug: Record<string, string>;
  selectedSlugs: Set<string>;
  weights: Record<string, string>;
  difficulty: Difficulty;
  toggleChapter: (slug: string) => void;
  setWeight: (slug: string, value: string) => void;
  setDifficulty: (d: Difficulty) => void;
  setSelectedFormatId: (formatId: string) => void;
  toAssemblePayload: () => AssembleRequest;
}

/**
 * Owns the Slice 3 coverage form: chapter selection, per-chapter weights, and
 * the difficulty profile. Builds the payload sent to /papers/assemble so the
 * dashboard page never has to construct it inline.
 */
export function useCoverageForm(): CoverageForm {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [formats, setFormats] = useState<PaperFormatSummary[]>([]);
  const [selectedFormatId, setSelectedFormatId] = useState('');
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(new Set());
  const [weights, setWeights] = useState<Record<string, string>>({});
  const [difficulty, setDifficulty] = useState<Difficulty>('standard');

  useEffect(() => {
    fetchChapters()
      .then(setChapters)
      .catch(() => setChapters([]));
    fetchPaperFormats()
      .then((nextFormats) => {
        setFormats(nextFormats);
        setSelectedFormatId((current) => current || nextFormats[0]?.format_id || '');
      })
      .catch(() => setFormats([]));
  }, []);

  function toggleChapter(slug: string) {
    setSelectedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  function setWeight(slug: string, value: string) {
    setWeights((prev) => ({ ...prev, [slug]: value }));
  }

  function toAssemblePayload(): AssembleRequest {
    return {
      ...(selectedFormatId ? { format_id: selectedFormatId } : {}),
      difficulty,
      chapter_slugs: Array.from(selectedSlugs),
      weights: Object.fromEntries(
        Array.from(selectedSlugs).flatMap((slug) => {
          const raw = weights[slug];
          const value = raw === undefined || raw === '' ? 1 : Number(raw);
          return Number.isFinite(value) ? [[slug, value]] : [];
        }),
      ),
    };
  }

  const chapterNameBySlug = useMemo(
    () => Object.fromEntries(chapters.map((c) => [c.slug, c.name])),
    [chapters],
  );

  return {
    chapters,
    formats,
    selectedFormatId,
    chapterNameBySlug,
    selectedSlugs,
    weights,
    difficulty,
    toggleChapter,
    setWeight,
    setDifficulty,
    setSelectedFormatId,
    toAssemblePayload,
  };
}
