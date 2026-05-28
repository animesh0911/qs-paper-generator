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
import { LoginPage, DashboardPage } from '@/pages';

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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
