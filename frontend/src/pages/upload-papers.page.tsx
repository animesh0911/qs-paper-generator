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
import { FileUp } from 'lucide-react';
import { useIngestionUpload } from '@/hooks/useIngestionUpload.hook';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AppHeader } from '@/components/app-nav';
import {
  IngestionStatusCard,
  PdfDropzone,
  SourceTypeField,
} from '@/components/ingestion';

export default function UploadPapersPage() {
  const navigate = useNavigate();
  const upload = useIngestionUpload();

  return (
    <div className="min-h-screen bg-secondary">
      <AppHeader />

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:py-10">
        <Card className="overflow-hidden rounded-lg border-white/70 bg-white/80 shadow-none backdrop-blur-2xl">
          <CardHeader className="border-b border-white/70 bg-white/60 px-5 py-5 sm:px-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1.5">
                <CardTitle className="text-xl leading-7">
                  Upload previous papers
                </CardTitle>
                <p className="max-w-xl text-[0.9375rem] leading-6 text-muted-foreground">
                  Upload a paper as a PDF and we’ll extract its questions into
                  your bank, ready to use when you generate a new paper.
                </p>
              </div>
              <span className="inline-flex w-fit items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs font-medium text-secondary-foreground">
                <FileUp className="size-3.5" aria-hidden="true" />
                Problem extraction
              </span>
            </div>
          </CardHeader>

          <CardContent className="space-y-6 bg-white/45 px-5 py-6 sm:px-6">
            {upload.job ? (
              <IngestionStatusCard
                job={upload.job}
                pollError={upload.pollError}
                parsedQuestions={upload.parsedQuestions}
                loadingQuestions={upload.loadingQuestions}
                onUploadAnother={upload.reset}
                onGeneratePaper={() => navigate('/')}
              />
            ) : (
              <>
                <PdfDropzone
                  file={upload.file}
                  onSelect={upload.selectFile}
                  validationError={upload.validationError}
                  disabled={upload.uploading}
                />
                <SourceTypeField
                  value={upload.sourceType}
                  onChange={upload.setSourceType}
                  disabled={upload.uploading}
                />
                {upload.uploadError && (
                  <p className="text-sm text-destructive" role="alert">
                    {upload.uploadError}
                  </p>
                )}
                <div className="flex items-center justify-end border-t border-white/70 pt-5">
                  <Button
                    onClick={upload.upload}
                    disabled={!upload.file || upload.uploading}
                  >
                    {upload.uploading ? 'Uploading…' : 'Upload & extract'}
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
