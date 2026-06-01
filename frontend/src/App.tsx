/**
 * Top-level router. Two routes: `/login` (anonymous) and `/` (gated by auth).
 *
 * `RequireAuth` redirects unauthenticated visitors to `/login`. Any unknown
 * path falls back to `/`, which then redirects to login if no token exists.
 *
 * @module App
 */
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth.hook';
import { DashboardPage, LoginPage } from '@/pages';
import { lazy, Suspense } from 'react';

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
        path="/"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />
      <Route
        path="/editor/:paperId?"
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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
