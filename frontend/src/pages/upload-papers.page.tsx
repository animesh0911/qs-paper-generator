/**
 * Upload Papers — a teacher uploads a previous-year paper (or sample paper /
 * question bank) as a PDF; the backend queues an out-of-request extraction that
 * adds the questions to the school's bank.
 *
 * Pure orchestration: `useIngestionUpload` owns the upload + polling lifecycle;
 * the dropzone, source-type field, and status card render it. Active extraction
 * takes over the page; once extraction settles, the picker returns with the
 * latest review tools below it for the current session.
 *
 * @module UploadPapersPage
 */
import { useNavigate } from 'react-router-dom';
import { FileSearch, ListChecks } from 'lucide-react';
import { useIngestionUpload } from '@/hooks/useIngestionUpload.hook';
import { isIngestionTerminal } from '@/lib/ingestion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AppHeader } from '@/components/app-nav';
import {
  ExtractedPaperReviewCard,
  IngestionQueueStrip,
  IngestionStatusCard,
  PdfDropzone,
} from '@/components/ingestion';

export default function UploadPapersPage() {
  const navigate = useNavigate();
  const upload = useIngestionUpload();
  const activeQueuedJob = upload.queuedJobs.find(
    (candidate) => !isIngestionTerminal(candidate.status),
  );
  const activeJob =
    upload.job != null && !isIngestionTerminal(upload.job.status)
      ? upload.job
      : (activeQueuedJob ?? null);
  const failedJob = upload.job?.status === 'failed' ? upload.job : null;
  const queuedJobs = activeJob
    ? upload.queuedJobs.filter((candidate) => candidate.id !== activeJob.id)
    : upload.queuedJobs;

  const uploadForm = (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <div className="space-y-6">
        <div className="space-y-3">
          <div className="text-sm font-medium leading-5">PDF file</div>
          <PdfDropzone
            file={upload.file}
            onSelect={upload.selectFile}
            validationError={upload.validationError}
            disabled={upload.uploading}
          />
        </div>
        {upload.uploadError && (
          <p
            className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
            role="alert"
          >
            {upload.uploadError}
          </p>
        )}
        <div className="flex justify-end border-t border-input pt-5">
          <Button
            onClick={upload.upload}
            disabled={!upload.file || upload.uploading}
            className="sm:min-w-36"
          >
            {upload.uploading ? 'Uploading…' : 'Upload & extract'}
          </Button>
        </div>
      </div>

      <aside className="rounded-lg border border-input bg-secondary/50 p-4">
        <div className="flex items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-background text-foreground">
            <ListChecks className="size-4" aria-hidden="true" />
          </span>
          <div className="space-y-3">
            <div>
              <h2 className="text-sm font-medium leading-5">
                Saved to the bank
              </h2>
              <p className="mt-1 text-[0.8125rem] leading-5 text-muted-foreground">
                Questions, marks, chapter tags, and source file.
              </p>
            </div>
            <ul className="space-y-1.5 text-xs leading-5 text-muted-foreground">
              <li>• Duplicates are skipped.</li>
              <li>• Review the extracted set after upload.</li>
            </ul>
          </div>
        </div>
      </aside>
    </div>
  );

  return (
    <div className="min-h-screen bg-secondary">
      <AppHeader />

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
        <Card className="overflow-hidden rounded-lg border-input bg-background shadow-none">
          <CardHeader className="border-b border-input bg-background px-5 py-5 sm:px-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1.5">
                <CardTitle className="text-xl leading-7">Upload PDF</CardTitle>
                <p className="max-w-xl text-sm leading-5 text-muted-foreground">
                  Extract questions from a paper and add them to the question bank.
                </p>
              </div>
              <span className="inline-flex w-fit items-center gap-1.5 rounded-md border border-input bg-secondary px-2.5 py-1.5 text-xs font-medium text-secondary-foreground">
                <FileSearch className="size-3.5" aria-hidden="true" />
                Question bank
              </span>
            </div>
          </CardHeader>

          <CardContent className="px-5 py-6 sm:px-6">
            {activeJob ? (
              <div className="mx-auto max-w-5xl">
                <IngestionStatusCard
                  job={activeJob}
                  pollError={upload.pollError}
                  parsedQuestions={upload.parsedQuestions}
                  loadingQuestions={upload.loadingQuestions}
                  answerJob={upload.answerJob}
                  generatedAnswers={upload.generatedAnswers}
                  loadingAnswers={upload.loadingAnswers}
                  generatingAnswers={upload.generatingAnswers}
                  answerGenerationError={upload.answerGenerationError}
                  onGenerateAnswers={upload.generateAnswers}
                  onGeneratePaper={() => navigate('/generate')}
                />
              </div>
            ) : (
              <div className="space-y-6">
                {uploadForm}
                {failedJob && (
                  <div className="mx-auto max-w-5xl border-t border-input pt-6">
                    <IngestionStatusCard
                      job={failedJob}
                      pollError={upload.pollError}
                      parsedQuestions={[]}
                      loadingQuestions={false}
                      answerJob={null}
                      generatedAnswers={[]}
                      loadingAnswers={false}
                      generatingAnswers={false}
                      answerGenerationError=""
                      onGenerateAnswers={upload.generateAnswers}
                      onGeneratePaper={() => navigate('/generate')}
                    />
                  </div>
                )}
                {upload.recentExtractedPapers.length > 0 && (
                  <section
                    className="mx-auto max-w-5xl border-t border-input pt-6"
                    aria-labelledby="recent-extracted-papers-heading"
                  >
                    <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                      <div>
                        <h2
                          id="recent-extracted-papers-heading"
                          className="text-sm font-medium leading-5 text-foreground"
                        >
                          Recent extracted papers
                        </h2>
                        <p className="text-xs leading-5 text-muted-foreground">
                          Review the last 3 completed uploads and generate answers when needed.
                        </p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      {upload.recentExtractedPapers.map((paper) => (
                        <ExtractedPaperReviewCard
                          key={paper.job.id}
                          job={paper.job}
                          parsedQuestions={paper.parsedQuestions}
                          loadingQuestions={paper.loadingQuestions}
                          answerJob={paper.answerJob}
                          generatedAnswers={paper.generatedAnswers}
                          loadingAnswers={paper.loadingAnswers}
                          generatingAnswers={paper.generatingAnswers}
                          answerGenerationError={paper.answerGenerationError}
                          onGenerateAnswers={() =>
                            upload.generateAnswersForJob(paper.job.id)
                          }
                        />
                      ))}
                    </div>
                  </section>
                )}
              </div>
            )}

            {queuedJobs.length > 0 && (
              <div className="mx-auto max-w-5xl">
                <IngestionQueueStrip
                  jobs={queuedJobs}
                  onRetry={upload.retryJob}
                  onDismiss={upload.dismissJob}
                />
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
