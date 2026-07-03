import { useEffect, useMemo, useState } from 'react';
import { fetchChapters, fetchPaperFormats, fetchPaperSources } from '@/lib/api';
import type {
  AssembleRequest,
  Chapter,
  PaperFormatSummary,
  PaperSourceSummary,
} from '@/types';

type Difficulty = NonNullable<AssembleRequest['difficulty']>;
export const DIFFICULTIES: Difficulty[] = ['easy', 'standard', 'hard'];

const COVERAGE_FORM_STORAGE_KEY = 'qpg_paper_setup_state';
const DEFAULT_TOTAL_MARKS = 80;

export interface PaperStructureSummary {
  totalMarks: number;
  sectionCount: number;
  approximateQuestionCount: number;
  marksByQuestionType: Record<string, number>;
}

export interface ChapterGroup {
  subjectArea: string;
  chapters: Chapter[];
}

export interface CoverageForm {
  chapters: Chapter[];
  chapterGroups: ChapterGroup[];
  chaptersLoading: boolean;
  chaptersError: string;
  formats: PaperFormatSummary[];
  sources: PaperSourceSummary[];
  sourcesLoading: boolean;
  sourcesError: string;
  selectedFormatId: string;
  selectedFormat?: PaperFormatSummary;
  totalMarks: number;
  structureSummary: PaperStructureSummary;
  chapterNameBySlug: Record<string, string>;
  selectedSlugs: Set<string>;
  difficulty: Difficulty;
  selectedSourceKeys: Set<string>;
  hasSelectedChapters: boolean;
  toggleSource: (key: string) => void;
  selectAllSources: () => void;
  clearAllSources: () => void;
  toggleChapter: (slug: string) => void;
  selectAllChapters: () => void;
  clearAllChapters: () => void;
  toggleChapterGroup: (subjectArea: string) => void;
  setDifficulty: (d: Difficulty) => void;
  setSelectedFormatId: (formatId: string) => void;
  setTotalMarks: (marks: number) => void;
  toAssemblePayload: () => AssembleRequest;
}

export function buildCoverageAssemblePayload({
  selectedFormatId,
  difficulty,
  selectedSlugs,
  selectedSourceKeys,
}: {
  selectedFormatId: string;
  difficulty: Difficulty;
  selectedSlugs: Set<string>;
  selectedSourceKeys: Set<string>;
}): AssembleRequest {
  return {
    ...(selectedFormatId ? { format_id: selectedFormatId } : {}),
    difficulty,
    chapter_slugs: Array.from(selectedSlugs),
    preferred_source_keys: Array.from(selectedSourceKeys),
  };
}

export function buildChapterGroups(chapters: Chapter[]): ChapterGroup[] {
  const knownOrder = ['Chemistry', 'Biology', 'Physics'];
  const byArea = new Map<string, Chapter[]>();
  for (const chapter of chapters) {
    const area = chapter.subject_area || inferSubjectArea(chapter.order);
    byArea.set(area, [...(byArea.get(area) || []), chapter]);
  }
  return Array.from(byArea.entries())
    .sort(([a], [b]) => {
      const ai = knownOrder.indexOf(a);
      const bi = knownOrder.indexOf(b);
      if (ai !== -1 || bi !== -1)
        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
      return a.localeCompare(b);
    })
    .map(([subjectArea, groupChapters]) => ({
      subjectArea,
      chapters: [...groupChapters].sort((a, b) => a.order - b.order),
    }));
}

export function buildPaperStructureSummary({
  selectedFormat,
  totalMarks,
}: {
  selectedFormat?: PaperFormatSummary;
  totalMarks: number;
}): PaperStructureSummary {
  if (
    selectedFormat?.total_marks &&
    selectedFormat.section_count &&
    selectedFormat.question_count &&
    selectedFormat.marks_by_question_type
  ) {
    return {
      totalMarks: selectedFormat.total_marks,
      sectionCount: selectedFormat.section_count,
      approximateQuestionCount: selectedFormat.question_count,
      marksByQuestionType: selectedFormat.marks_by_question_type,
    };
  }

  const preset = selectedFormat?.preset_name || inferPresetName(selectedFormat);
  if (preset === 'unit_test') {
    return scaleSummary(
      {
        sectionCount: 4,
        approximateQuestionCount: 10,
        marksByQuestionType: {
          mcq: 5,
          very_short_answer: 4,
          short_answer: 6,
          long_answer: 5,
        },
      },
      totalMarks,
      20,
    );
  }
  if (preset === 'half_yearly') {
    return scaleSummary(
      {
        sectionCount: 5,
        approximateQuestionCount: 22,
        marksByQuestionType: {
          mcq: 10,
          very_short_answer: 8,
          short_answer: 12,
          long_answer: 10,
          case_based: 8,
        },
      },
      totalMarks,
      48,
    );
  }
  return scaleSummary(
    {
      sectionCount: 3,
      approximateQuestionCount: 39,
      marksByQuestionType: {
        mcq: 20,
        very_short_answer: 12,
        short_answer: 21,
        long_answer: 15,
        case_based: 12,
      },
    },
    totalMarks,
    80,
  );
}

/**
 * Owns the paper setup form: format, total marks display, chapter selection,
 * and the difficulty profile. Selected chapters are sent explicitly; generation
 * is blocked when none are selected so teachers do not accidentally use all.
 */
export function useCoverageForm(): CoverageForm {
  const saved = readSavedCoverageForm();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chaptersLoading, setChaptersLoading] = useState(true);
  const [chaptersError, setChaptersError] = useState('');
  const [formats, setFormats] = useState<PaperFormatSummary[]>([]);
  const [sources, setSources] = useState<PaperSourceSummary[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState('');
  const [selectedFormatId, setSelectedFormatId] = useState(
    saved.selectedFormatId,
  );
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(
    new Set(saved.selectedSlugs),
  );
  const [selectedSourceKeys, setSelectedSourceKeys] = useState<Set<string>>(
    new Set(saved.selectedSourceKeys),
  );
  const [difficulty, setDifficulty] = useState<Difficulty>(saved.difficulty);
  const [totalMarks, setTotalMarks] = useState(saved.totalMarks);

  useEffect(() => {
    fetchChapters()
      .then((nextChapters) => {
        const validSlugs = new Set(nextChapters.map((chapter) => chapter.slug));
        setChapters(nextChapters);
        setSelectedSlugs(
          (current) =>
            new Set([...current].filter((slug) => validSlugs.has(slug))),
        );
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

  const selectedChapterSlugs = useMemo(
    () => Array.from(selectedSlugs).sort(),
    [selectedSlugs],
  );
  const selectedChapterSourceKey = selectedChapterSlugs.join('|');

  useEffect(() => {
    if (selectedChapterSlugs.length === 0) {
      setSources([]);
      setSourcesError('');
      setSourcesLoading(false);
      setSelectedSourceKeys(new Set());
      return;
    }

    let cancelled = false;
    setSourcesLoading(true);
    fetchPaperSources(selectedChapterSlugs)
      .then((nextSources) => {
        if (cancelled) return;
        const validKeys = new Set(nextSources.map((source) => source.key));
        setSources(nextSources);
        setSelectedSourceKeys(
          (current) =>
            new Set([...current].filter((key) => validKeys.has(key))),
        );
        setSourcesError('');
      })
      .catch((err) => {
        if (cancelled) return;
        setSources([]);
        setSourcesError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setSourcesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedChapterSourceKey]);

  useEffect(() => {
    sessionStorage.setItem(
      COVERAGE_FORM_STORAGE_KEY,
      JSON.stringify({
        selectedFormatId,
        selectedSlugs: Array.from(selectedSlugs),
        selectedSourceKeys: Array.from(selectedSourceKeys),
        difficulty,
        totalMarks,
      }),
    );
  }, [selectedFormatId, selectedSlugs, selectedSourceKeys, difficulty, totalMarks]);

  const chapterNameBySlug = useMemo(
    () => Object.fromEntries(chapters.map((c) => [c.slug, c.name])),
    [chapters],
  );
  const selectedFormat = useMemo(
    () => formats.find((format) => format.format_id === selectedFormatId),
    [formats, selectedFormatId],
  );
  const chapterGroups = useMemo(() => buildChapterGroups(chapters), [chapters]);
  const effectiveTotalMarks = selectedFormat?.total_marks || totalMarks;
  const structureSummary = useMemo(
    () =>
      buildPaperStructureSummary({
        selectedFormat,
        totalMarks: effectiveTotalMarks,
      }),
    [selectedFormat, effectiveTotalMarks],
  );

  function toggleSource(key: string) {
    setSelectedSourceKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function selectAllSources() {
    setSelectedSourceKeys(new Set(sources.map((source) => source.key)));
  }

  function clearAllSources() {
    setSelectedSourceKeys(new Set());
  }

  function toggleChapter(slug: string) {
    setSelectedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  function selectAllChapters() {
    setSelectedSlugs(new Set(chapters.map((chapter) => chapter.slug)));
  }

  function clearAllChapters() {
    setSelectedSlugs(new Set());
  }

  function toggleChapterGroup(subjectArea: string) {
    const groupSlugs =
      chapterGroups
        .find((group) => group.subjectArea === subjectArea)
        ?.chapters.map((chapter) => chapter.slug) || [];
    setSelectedSlugs((prev) => {
      const next = new Set(prev);
      const allSelected = groupSlugs.every((slug) => next.has(slug));
      for (const slug of groupSlugs) {
        if (allSelected) next.delete(slug);
        else next.add(slug);
      }
      return next;
    });
  }

  function toAssemblePayload(): AssembleRequest {
    return buildCoverageAssemblePayload({
      selectedFormatId,
      difficulty,
      selectedSlugs,
      selectedSourceKeys,
    });
  }

  return {
    chapters,
    chapterGroups,
    chaptersLoading,
    chaptersError,
    formats,
    sources,
    sourcesLoading,
    sourcesError,
    selectedFormatId,
    selectedFormat,
    totalMarks: structureSummary.totalMarks,
    structureSummary,
    chapterNameBySlug,
    selectedSlugs,
    difficulty,
    selectedSourceKeys,
    hasSelectedChapters: selectedSlugs.size > 0,
    toggleSource,
    selectAllSources,
    clearAllSources,
    toggleChapter,
    selectAllChapters,
    clearAllChapters,
    toggleChapterGroup,
    setDifficulty,
    setSelectedFormatId,
    setTotalMarks: (marks: number) => setTotalMarks(Math.max(1, marks)),
    toAssemblePayload,
  };
}

function inferSubjectArea(order: number): string {
  if (order >= 1 && order <= 4) return 'Chemistry';
  if ((order >= 5 && order <= 8) || order === 13) return 'Biology';
  if (order >= 9 && order <= 12) return 'Physics';
  return 'Science';
}

function inferPresetName(format?: PaperFormatSummary): string {
  const haystack =
    `${format?.format_id || ''} ${format?.name || ''}`.toLowerCase();
  if (haystack.includes('unit')) return 'unit_test';
  if (haystack.includes('half')) return 'half_yearly';
  return 'board';
}

function scaleSummary(
  base: Omit<PaperStructureSummary, 'totalMarks'>,
  totalMarks: number,
  baseMarks: number,
): PaperStructureSummary {
  if (totalMarks === baseMarks) return { totalMarks, ...base };
  const scale = totalMarks / baseMarks;
  return {
    totalMarks,
    sectionCount: base.sectionCount,
    approximateQuestionCount: Math.max(
      1,
      Math.round(base.approximateQuestionCount * scale),
    ),
    marksByQuestionType: Object.fromEntries(
      Object.entries(base.marksByQuestionType).map(([type, marks]) => [
        type,
        Math.max(1, Math.round(marks * scale)),
      ]),
    ),
  };
}

function readSavedCoverageForm(): {
  selectedFormatId: string;
  selectedSlugs: string[];
  selectedSourceKeys: string[];
  difficulty: Difficulty;
  totalMarks: number;
} {
  if (typeof sessionStorage === 'undefined') return emptySavedCoverageForm();
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
      selectedSourceKeys: Array.isArray(parsed.selectedSourceKeys)
        ? parsed.selectedSourceKeys.filter(
            (key): key is string => typeof key === 'string',
          )
        : [],
      difficulty: DIFFICULTIES.includes(parsed.difficulty as Difficulty)
        ? (parsed.difficulty as Difficulty)
        : 'standard',
      totalMarks:
        typeof parsed.totalMarks === 'number' &&
        Number.isFinite(parsed.totalMarks)
          ? parsed.totalMarks
          : DEFAULT_TOTAL_MARKS,
    };
  } catch {
    return emptySavedCoverageForm();
  }
}

function emptySavedCoverageForm() {
  return {
    selectedFormatId: '',
    selectedSlugs: [] as string[],
    selectedSourceKeys: [] as string[],
    difficulty: 'standard' as Difficulty,
    totalMarks: DEFAULT_TOTAL_MARKS,
  };
}
