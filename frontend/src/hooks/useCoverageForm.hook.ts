import { useEffect, useMemo, useState } from 'react';
import { fetchChapters, fetchPaperFormats } from '@/lib/api';
import type { AssembleRequest, Chapter, PaperFormatSummary } from '@/types';

type Difficulty = NonNullable<AssembleRequest['difficulty']>;
export const DIFFICULTIES: Difficulty[] = ['easy', 'standard', 'hard'];

const COVERAGE_FORM_STORAGE_KEY = 'qpg_paper_setup_state';

export interface CoverageForm {
  chapters: Chapter[];
  chaptersLoading: boolean;
  chaptersError: string;
  formats: PaperFormatSummary[];
  selectedFormatId: string;
  chapterNameBySlug: Record<string, string>;
  selectedSlugs: Set<string>;
  difficulty: Difficulty;
  toggleChapter: (slug: string) => void;
  setDifficulty: (d: Difficulty) => void;
  setSelectedFormatId: (formatId: string) => void;
  toAssemblePayload: () => AssembleRequest;
}

export function buildCoverageAssemblePayload({
  selectedFormatId,
  difficulty,
  selectedSlugs,
}: {
  selectedFormatId: string;
  difficulty: Difficulty;
  selectedSlugs: Set<string>;
}): AssembleRequest {
  return {
    ...(selectedFormatId ? { format_id: selectedFormatId } : {}),
    difficulty,
    chapter_slugs: Array.from(selectedSlugs),
  };
}

/**
 * Owns the Slice 3 coverage form: chapter selection and the difficulty profile.
 * Selected chapters are distributed equally by the backend. Builds the payload
 * sent to /papers/assemble so the dashboard page never has to construct it
 * inline.
 */
export function useCoverageForm(): CoverageForm {
  const saved = readSavedCoverageForm();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chaptersLoading, setChaptersLoading] = useState(true);
  const [chaptersError, setChaptersError] = useState('');
  const [formats, setFormats] = useState<PaperFormatSummary[]>([]);
  const [selectedFormatId, setSelectedFormatId] = useState(
    saved.selectedFormatId,
  );
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(
    new Set(saved.selectedSlugs),
  );
  const [difficulty, setDifficulty] = useState<Difficulty>(saved.difficulty);

  useEffect(() => {
    fetchChapters()
      .then((nextChapters) => {
        setChapters(nextChapters);
        setChaptersError('');
      })
      .catch((err) => {
        setChapters([]);
        setChaptersError((err as Error).message);
      })
      .finally(() => setChaptersLoading(false));
    fetchPaperFormats()
      .then((nextFormats) => {
        setFormats(nextFormats);
        setSelectedFormatId(
          (current) => current || nextFormats[0]?.format_id || '',
        );
      })
      .catch(() => setFormats([]));
  }, []);

  useEffect(() => {
    sessionStorage.setItem(
      COVERAGE_FORM_STORAGE_KEY,
      JSON.stringify({
        selectedFormatId,
        selectedSlugs: Array.from(selectedSlugs),
        difficulty,
      }),
    );
  }, [selectedFormatId, selectedSlugs, difficulty]);

  function toggleChapter(slug: string) {
    setSelectedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  function toAssemblePayload(): AssembleRequest {
    return buildCoverageAssemblePayload({
      selectedFormatId,
      difficulty,
      selectedSlugs,
    });
  }

  const chapterNameBySlug = useMemo(
    () => Object.fromEntries(chapters.map((c) => [c.slug, c.name])),
    [chapters],
  );

  return {
    chapters,
    chaptersLoading,
    chaptersError,
    formats,
    selectedFormatId,
    chapterNameBySlug,
    selectedSlugs,
    difficulty,
    toggleChapter,
    setDifficulty,
    setSelectedFormatId,
    toAssemblePayload,
  };
}

function readSavedCoverageForm(): {
  selectedFormatId: string;
  selectedSlugs: string[];
  difficulty: Difficulty;
} {
  if (typeof sessionStorage === 'undefined') {
    return emptySavedCoverageForm();
  }
  try {
    const parsed = JSON.parse(
      sessionStorage.getItem(COVERAGE_FORM_STORAGE_KEY) || '{}',
    ) as Partial<ReturnType<typeof emptySavedCoverageForm>>;
    return {
      selectedFormatId:
        typeof parsed.selectedFormatId === 'string'
          ? parsed.selectedFormatId
          : '',
      selectedSlugs: Array.isArray(parsed.selectedSlugs)
        ? parsed.selectedSlugs.filter(
            (slug): slug is string => typeof slug === 'string',
          )
        : [],
      difficulty: DIFFICULTIES.includes(parsed.difficulty as Difficulty)
        ? (parsed.difficulty as Difficulty)
        : 'standard',
    };
  } catch {
    return emptySavedCoverageForm();
  }
}

function emptySavedCoverageForm() {
  return {
    selectedFormatId: '',
    selectedSlugs: [] as string[],
    difficulty: 'standard' as Difficulty,
  };
}
