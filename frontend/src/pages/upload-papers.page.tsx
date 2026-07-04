/**
 * Upload Papers — a teacher uploads a previous-year paper (or sample paper /
 * question bank) as a PDF; the backend queues an out-of-request extraction that
 * adds the questions to the school's bank.
 *
 * Pure orchestration: `useIngestionUpload` owns the upload + polling lifecycle;
 * the dropzone, source-type field, and status card render it. Before a job
 * exists we show the picker form; once queued we swap to the live status card.
 *
 * @module UploadPapersPage
 */
import { useNavigate } from 'react-router-dom';
import { FileSearch, ListChecks } from 'lucide-react';
import { useIngestionUpload } from '@/hooks/useIngestionUpload.hook';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AppHeader } from '@/components/app-nav';
import { IngestionStatusCard, PdfDropzone } from '@/components/ingestion';

export default function UploadPapersPage() {
  const navigate = useNavigate();
  const upload = useIngestionUpload();

  return (
    <div className="min-h-screen bg-secondary">
      <AppHeader />

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
        <Card className="overflow-hidden rounded-lg border-input bg-background shadow-none">
          <CardHeader className="border-b border-input bg-background px-5 py-5 sm:px-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1.5">
                <CardTitle className="text-xl leading-7">
                  Upload a PDF
                </CardTitle>
                <p className="max-w-xl text-sm leading-5 text-muted-foreground">
                  AI extracts the questions from your PDF and adds them to your
                  question bank.
                </p>
              </div>
              <span className="inline-flex w-fit items-center gap-1.5 rounded-md border border-input bg-secondary px-2.5 py-1.5 text-xs font-medium text-secondary-foreground">
                <FileSearch className="size-3.5" aria-hidden="true" />
                Question-bank ingestion
              </span>
            </div>
          </CardHeader>

          <CardContent className="px-5 py-6 sm:px-6">
            {upload.job ? (
              <div className="mx-auto max-w-5xl">
                <IngestionStatusCard
                  job={upload.job}
                  pollError={upload.pollError}
                  parsedQuestions={upload.parsedQuestions}
                  loadingQuestions={upload.loadingQuestions}
                  onUploadAnother={upload.reset}
                  onGeneratePaper={() => navigate('/generate')}
                />
              </div>
            ) : (
              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
                <div className="space-y-6">
                  <div className="space-y-3">
                    <div className="text-sm font-medium leading-5">
                      Select a PDF
                    </div>
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
                  <div className="flex flex-col gap-2 border-t border-input pt-5 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-xs leading-5 text-muted-foreground">
                      Extraction continues in the background after upload.
                    </p>
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
                          What gets saved
                        </h2>
                        <p className="mt-1 text-[0.8125rem] leading-5 text-muted-foreground">
                          Questions, marks, chapters, and the PDF name.
                        </p>
                      </div>
                      <ul className="space-y-1.5 text-xs leading-5 text-muted-foreground">
                        <li>• Duplicates are skipped.</li>
                        <li>• You can review extracted questions.</li>
                      </ul>
                    </div>
                  </div>
                </aside>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
