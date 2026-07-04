/**
 * Owns the browsable Question Bank view: loads chapter + metadata vocabulary
 * for the filter controls, and fetches a paginated, filtered slice of questions
 * from `GET /api/bank/questions/`.
 *
 * Filters (chapter / section / qtype / source / search) reset the offset to the
 * first page; paging keeps the active filters. The fetch is debounced lightly so
 * typing in the search box doesn't fire a request per keystroke.
 *
 * @module useQuestionBank.hook
 */
import { useEffect, useMemo, useState } from 'react';
import type { Metadata } from '@/lib/api';
import {
  fetchBankQuestions,
  fetchBankQuestionSources,
  fetchChapters,
  fetchMetadata,
} from '@/lib/api';
import type {
  BankQuestion,
  BankQuestionFilters,
  BankQuestionSource,
  Chapter,
  SourceType,
} from '@/types';

export const QUESTION_BANK_PAGE_SIZE = 50;

export interface QuestionBankFilterState {
  chapter: string;
  section: string;
  qtype: string;
  source_type: SourceType | '';
  source: string;
  search: string;
}

const EMPTY_FILTERS: QuestionBankFilterState = {
  chapter: '',
  section: '',
  qtype: '',
  source_type: '',
  source: '',
  search: '',
};

export interface QuestionBank {
  questions: BankQuestion[];
  count: number;
  offset: number;
  pageSize: number;
  loading: boolean;
  error: string;
  chapters: Chapter[];
  sources: BankQuestionSource[];
  metadata: Metadata | null;
  filters: QuestionBankFilterState;
  setFilter: <K extends keyof QuestionBankFilterState>(
    key: K,
    value: QuestionBankFilterState[K],
  ) => void;
  resetFilters: () => void;
  hasActiveFilters: boolean;
  goToPage: (offset: number) => void;
}

export function useQuestionBank(): QuestionBank {
  const [questions, setQuestions] = useState<BankQuestion[]>([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [sources, setSources] = useState<BankQuestionSource[]>([]);
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [filters, setFilters] =
    useState<QuestionBankFilterState>(EMPTY_FILTERS);

  // Vocabulary for the filter controls — loaded once.
  useEffect(() => {
    fetchChapters()
      .then(setChapters)
      .catch(() => setChapters([]));
    fetchMetadata()
      .then(setMetadata)
      .catch(() => setMetadata(null));
    fetchBankQuestionSources()
      .then(setSources)
      .catch(() => setSources([]));
  }, []);

  const hasActiveFilters = useMemo(
    () => Object.values(filters).some((value) => value !== ''),
    [filters],
  );

  // Fetch the current page whenever filters or offset change. A short debounce
  // keeps search-box typing from firing one request per keystroke.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const payload: BankQuestionFilters = {
      limit: QUESTION_BANK_PAGE_SIZE,
      offset,
    };
    if (filters.chapter) payload.chapter = filters.chapter;
    if (filters.section) payload.section = filters.section;
    if (filters.qtype) payload.qtype = filters.qtype;
    if (filters.source_type) payload.source_type = filters.source_type;
    if (filters.source) payload.source = filters.source;
    if (filters.search) payload.search = filters.search;

    const timer = setTimeout(
      () => {
        fetchBankQuestions(payload)
          .then((res) => {
            if (cancelled) return;
            setQuestions(res.results);
            setCount(res.count);
            setError('');
          })
          .catch((err) => {
            if (cancelled) return;
            setQuestions([]);
            setCount(0);
            setError((err as Error).message);
          })
          .finally(() => {
            if (!cancelled) setLoading(false);
          });
      },
      filters.search ? 300 : 0,
    );

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [filters, offset]);

  function setFilter<K extends keyof QuestionBankFilterState>(
    key: K,
    value: QuestionBankFilterState[K],
  ) {
    setOffset(0);
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function resetFilters() {
    setOffset(0);
    setFilters(EMPTY_FILTERS);
  }

  return {
    questions,
    count,
    offset,
    pageSize: QUESTION_BANK_PAGE_SIZE,
    loading,
    error,
    chapters,
    sources,
    metadata,
    filters,
    setFilter,
    resetFilters,
    hasActiveFilters,
    goToPage: setOffset,
  };
}
