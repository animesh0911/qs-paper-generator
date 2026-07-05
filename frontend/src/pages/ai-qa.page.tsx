/**
 * AI Q&A — bulk-generate AI questions for a chapter's topics into the bank.
 *
 * Pure orchestration: loads the (MVP-scoped) chapter list and the selected
 * chapter's topics, then queues a generation batch and routes to its progress
 * page. Pre-fills from `location.state.generationPrefill` when arriving via
 * "Generate another batch" on the progress page.
 *
 * @module AiQaPage
 */
import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  createGenerationBatch,
  discardGenerationBatch,
  fetchChapters,
  fetchChapterTopics,
  fetchGenerationBatches,
  retryGenerationBatch,
} from '@/lib/api';
import { buildGenerationBatchPayload } from '@/lib/question-generation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AppHeader } from '@/components/app-nav';
import { BulkQuestionGenerationSetup } from '@/components/question-generation';
import type { Chapter, ChapterTopicNode, GenerationBatch } from '@/types';

const ENABLED_GENERATION_CHAPTER_SLUGS = [
  'carbon-and-its-compounds',
  'human-eye-and-the-colourful-world',
];

interface GenerationPrefill {
  chapterSlug: string;
  topicIds: string[];
}

export default function AiQaPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chaptersLoading, setChaptersLoading] = useState(true);
  const [chaptersError, setChaptersError] = useState('');
  const [chapterSlug, setChapterSlug] = useState('');
  const [topics, setTopics] = useState<ChapterTopicNode[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(false);
  const [topicsError, setTopicsError] = useState('');
  const [selectedTopicIds, setSelectedTopicIds] = useState<Set<string>>(
    new Set(),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [batches, setBatches] = useState<GenerationBatch[]>([]);
  const [batchesLoading, setBatchesLoading] = useState(true);
  const [batchesError, setBatchesError] = useState('');

  const loadBatches = useCallback(async () => {
    try {
      const nextBatches = await fetchGenerationBatches();
      setBatches(nextBatches.slice().reverse());
      setBatchesError('');
    } catch (err) {
      setBatches([]);
      setBatchesError((err as Error).message);
    } finally {
      setBatchesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBatches();
    const timer = window.setInterval(() => void loadBatches(), 5000);
    return () => window.clearInterval(timer);
  }, [loadBatches]);

  const retryBatch = useCallback(
    async (batchId: number) => {
      try {
        await retryGenerationBatch(batchId);
        await loadBatches();
      } catch (err) {
        setBatchesError((err as Error).message);
      }
    },
    [loadBatches],
  );

  const discardBatch = useCallback(
    async (batchId: number) => {
      try {
        await discardGenerationBatch(batchId);
        await loadBatches();
      } catch (err) {
        setBatchesError((err as Error).message);
      }
    },
    [loadBatches],
  );

  useEffect(() => {
    let cancelled = false;
    fetchChapters()
      .then((all) => {
        if (cancelled) return;
        // AI generation is enabled only for chapters with populated corpus
        // retrieval data; the rest of the syllabus is shown as upcoming.
        setChapters(
          all.filter((c) => ENABLED_GENERATION_CHAPTER_SLUGS.includes(c.slug)),
        );
        setChaptersError('');
      })
      .catch((err) => {
        if (cancelled) return;
        setChapters([]);
        setChaptersError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setChaptersLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!chapterSlug) {
      setTopics([]);
      setTopicsError('');
      setTopicsLoading(false);
      return;
    }

    let cancelled = false;
    setTopicsLoading(true);
    setTopicsError('');
    fetchChapterTopics(chapterSlug)
      .then((response) => {
        if (cancelled) return;
        setTopics(response.topics);
      })
      .catch((err) => {
        if (cancelled) return;
        setTopics([]);
        setTopicsError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setTopicsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [chapterSlug]);

  // Pre-fill from "Generate another batch" so the teacher can tweak and re-run.
  useEffect(() => {
    const prefill = (
      location.state as { generationPrefill?: GenerationPrefill }
    )?.generationPrefill;
    if (!prefill) return;
    setChapterSlug(prefill.chapterSlug);
    setSelectedTopicIds(new Set(prefill.topicIds));
    navigate('.', { replace: true, state: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  function selectChapter(slug: string) {
    setChapterSlug(slug);
    setSelectedTopicIds(new Set());
    setError('');
  }

  function toggleTopic(nodeId: string) {
    setSelectedTopicIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }

  async function start() {
    setBusy(true);
    setError('');
    try {
      const payload = buildGenerationBatchPayload({
        chapterSlug,
        chapterMapNodeIds: Array.from(selectedTopicIds),
      });
      const batch = await createGenerationBatch(payload);
      navigate(`/generation-batches/${batch.id}`);
    } catch (err) {
      // A 409 here means the per-teacher queue cap is reached; surface it and
      // refresh the draft list so the teacher can jump to the blocking batch.
      setError((err as Error).message);
      void loadBatches();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-secondary">
      <AppHeader />

      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:py-10">
        <Card className="overflow-hidden rounded-lg border-white/70 bg-white/80 shadow-none backdrop-blur-2xl">
          <CardHeader className="border-b border-white/70 bg-white/60 px-5 py-5 sm:px-6">
            <div className="space-y-1.5">
              <CardTitle className="text-xl leading-7">
                Generate AI Q&amp;A
              </CardTitle>
              <p className="max-w-2xl text-[0.9375rem] leading-6 text-muted-foreground">
                Choose a chapter, select topics, and generate grounded Q&amp;A.
                Review candidates before they enter your bank.
              </p>
            </div>
          </CardHeader>
          <CardContent className="bg-white/45 px-5 py-6 sm:px-6">
            <BulkQuestionGenerationSetup
              batches={batches}
              batchesLoading={batchesLoading}
              batchesError={batchesError}
              chapters={chapters}
              chaptersLoading={chaptersLoading}
              chaptersError={chaptersError}
              selectedChapterSlug={chapterSlug}
              topics={topics}
              topicsLoading={topicsLoading}
              topicsError={topicsError}
              selectedTopicIds={selectedTopicIds}
              busy={busy}
              error={error}
              activeBatchId={null}
              onSelectChapter={selectChapter}
              onToggleTopic={toggleTopic}
              onClearTopics={() => setSelectedTopicIds(new Set())}
              onStart={start}
              onOpenActiveBatch={() => {}}
              onOpenBatch={(batchId) =>
                navigate(`/generation-batches/${batchId}`)
              }
              onRetryBatch={retryBatch}
              onDiscardBatch={discardBatch}
            />
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
