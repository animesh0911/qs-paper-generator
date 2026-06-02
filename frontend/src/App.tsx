/**
 * Top-level router for the app shell.
 *
 * `/editor` stays directly accessible so the paper editor can be opened as a
 * standalone workspace. `/` remains the authenticated dashboard entrypoint,
 * and `/editor/:paperId/print` serves the print view.
 *
 * @module App
 */
import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth.hook';
import { DashboardPage, LoginPage, PrintPaperPage } from '@/pages';

const EditorPage = lazy(() => import('@/pages/editor.page'));

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/editor"
        element={
          <Suspense
            fallback={
              <div className="min-h-screen bg-secondary p-6 text-sm">
                Loading editor...
              </div>
            }
          >
            <EditorPage />
          </Suspense>
        }
      />
      <Route path="/editor/:paperId/print" element={<PrintPaperPage />} />
      <Route
        path="/"
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
