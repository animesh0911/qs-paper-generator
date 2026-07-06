import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppHeader } from '@/components/app-nav';
import { Button } from '@/components/ui/button';
import { IngestionStatusCard } from '@/components/ingestion';
import {
  fetchIngestionJob,
  fetchIngestionJobAnswers,
  fetchIngestionJobQuestions,
  generateIngestionJobAnswers,
} from '@/lib/api';
import type {
  AnswerGenerationJob,
  BankQuestion,
  GeneratedAnswer,
  IngestionJob,
} from '@/types';

export default function ExtractionReviewPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [parsedQuestions, setParsedQuestions] = useState<BankQuestion[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [answerJob, setAnswerJob] = useState<AnswerGenerationJob | null>(null);
  const [generatedAnswers, setGeneratedAnswers] = useState<GeneratedAnswer[]>([]);
  const [loadingAnswers, setLoadingAnswers] = useState(false);
  const [generatingAnswers, setGeneratingAnswers] = useState(false);
  const [answerGenerationError, setAnswerGenerationError] = useState('');

  const loadReview = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    setError('');
    try {
      const nextJob = await fetchIngestionJob(jobId);
      setJob(nextJob);
      if (nextJob.status === 'done') {
        setLoadingQuestions(true);
        setLoadingAnswers(true);
        const [questions, answerState] = await Promise.all([
          fetchIngestionJobQuestions(jobId).catch(() => []),
          fetchIngestionJobAnswers(jobId).catch((err) => {
            setAnswerGenerationError((err as Error).message);
            return { job: null, answers: [] };
          }),
        ]);
        setParsedQuestions(questions);
        setAnswerJob(answerState.job);
        setGeneratedAnswers(answerState.answers);
      } else {
        setParsedQuestions([]);
        setAnswerJob(null);
        setGeneratedAnswers([]);
      }
    } catch (err) {
      setJob(null);
      setError((err as Error).message);
    } finally {
      setLoading(false);
      setLoadingQuestions(false);
      setLoadingAnswers(false);
    }
  }, [jobId]);

  useEffect(() => {
    void loadReview();
  }, [loadReview]);

  async function generateAnswers() {
    if (!jobId || generatingAnswers) return;
    setGeneratingAnswers(true);
    setAnswerGenerationError('');
    try {
      const queued = await generateIngestionJobAnswers(jobId);
      setAnswerJob(queued);
      setLoadingAnswers(true);
      const answerState = await fetchIngestionJobAnswers(jobId);
      setAnswerJob(answerState.job);
      setGeneratedAnswers(answerState.answers);
    } catch (err) {
      setAnswerGenerationError((err as Error).message);
    } finally {
      setGeneratingAnswers(false);
      setLoadingAnswers(false);
    }
  }

  return (
    <div className="min-h-screen bg-secondary">
      <AppHeader />

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold leading-7">
              Extracted paper review
            </h1>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
              Review the questions imported from this uploaded paper.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => navigate('/generate')}>
            Back to generate
          </Button>
        </div>

        {loading && !job && (
          <p className="rounded-lg border bg-background p-4 text-sm text-muted-foreground">
            Loading extracted paper…
          </p>
        )}

        {error && !job && (
          <div className="space-y-3 rounded-lg border bg-background p-4" role="alert">
            <div>
              <p className="text-sm font-medium">Extraction could not be loaded.</p>
              <p className="mt-1 text-sm text-muted-foreground">{error}</p>
            </div>
            <Button type="button" size="sm" onClick={loadReview} disabled={loading}>
              Try again
            </Button>
          </div>
        )}

        {job && (
          <IngestionStatusCard
            job={job}
            pollError={error}
            parsedQuestions={parsedQuestions}
            loadingQuestions={loadingQuestions}
            answerJob={answerJob}
            generatedAnswers={generatedAnswers}
            loadingAnswers={loadingAnswers}
            generatingAnswers={generatingAnswers}
            answerGenerationError={answerGenerationError}
            onGenerateAnswers={generateAnswers}
            onGeneratePaper={() => navigate('/generate')}
          />
        )}
      </main>
    </div>
  );
}
