/**
 * Top-level router for the app shell.
 *
 * `/editor` returns to paper setup. Persisted papers load through
 * authenticated `/editor/:paperId`; `/editor/:paperId/print`
 * remains the print-only route used by backend PDF rendering.
 *
 * @module App
 */
import { lazy, Suspense, useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth.hook';
import {
  AiQaPage,
  DashboardPage,
  LoginPage,
  PrintAnswerKeyPage,
  PrintPaperPage,
  QuestionBankPage,
  UploadPapersPage,
  WelcomePage,
} from '@/pages';

const EditorPage = lazy(() => import('@/pages/editor.page'));
const GenerationProgressPage = lazy(
  () => import('@/pages/generation-progress.page'),
);
const ExtractionReviewPage = lazy(
  () => import('@/pages/extraction-review.page'),
);

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  // A file dropped anywhere outside a dropzone would otherwise navigate the
  // tab to the file, silently discarding all app state. Allow the drag
  // (dragover preventDefault) and swallow stray drops — but never intercept a
  // drop landing on a real file input, which handles it natively.
  useEffect(() => {
    const allowDrag = (event: DragEvent) => {
      event.preventDefault();
    };
    const swallowStrayDrop = (event: DragEvent) => {
      const target = event.target;
      const onFileInput =
        target instanceof HTMLInputElement && target.type === 'file';
      if (!onFileInput) event.preventDefault();
    };
    window.addEventListener('dragover', allowDrag);
    window.addEventListener('drop', swallowStrayDrop);
    return () => {
      window.removeEventListener('dragover', allowDrag);
      window.removeEventListener('drop', swallowStrayDrop);
    };
  }, []);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/editor" element={<Navigate to="/generate" replace />} />
      <Route
        path="/editor/:paperId"
        element={
          <RequireAuth>
            <Suspense
              fallback={
                <div className="min-h-screen bg-secondary p-6 text-sm">
                  Loading editor...
                </div>
              }
            >
              <EditorPage />
            </Suspense>
          </RequireAuth>
        }
      />
      <Route path="/editor/:paperId/print" element={<PrintPaperPage />} />
      <Route
        path="/editor/:paperId/answer-key/print"
        element={<PrintAnswerKeyPage />}
      />
      <Route
        path="/upload"
        element={
          <RequireAuth>
            <UploadPapersPage />
          </RequireAuth>
        }
      />
      <Route
        path="/question-bank"
        element={
          <RequireAuth>
            <QuestionBankPage />
          </RequireAuth>
        }
      />
      <Route
        path="/ai-qa"
        element={
          <RequireAuth>
            <AiQaPage />
          </RequireAuth>
        }
      />
      <Route
        path="/generation-batches/:batchId"
        element={
          <RequireAuth>
            <Suspense
              fallback={
                <div className="min-h-screen bg-secondary p-6 text-sm">
                  Loading generation workspace...
                </div>
              }
            >
              <GenerationProgressPage />
            </Suspense>
          </RequireAuth>
        }
      />
      <Route
        path="/extractions/:jobId"
        element={
          <RequireAuth>
            <Suspense
              fallback={
                <div className="min-h-screen bg-secondary p-6 text-sm">
                  Loading extracted paper...
                </div>
              }
            >
              <ExtractionReviewPage />
            </Suspense>
          </RequireAuth>
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <WelcomePage />
          </RequireAuth>
        }
      />
      <Route
        path="/generate"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
