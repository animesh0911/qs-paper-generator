/**
 * Auth state for the frontend.
 *
 * Reads the token from localStorage (via `lib/api`) — no React state, so
 * the hook is cheap to call from any component. `logout` clears the token
 * and routes back to /login.
 *
 * Login itself doesn't happen here; the login page calls `lib/api.login`
 * directly, which sets the token before navigating.
 *
 * @module useAuth.hook
 */
import { useNavigate } from 'react-router-dom';
import { clearToken, getToken } from '@/lib/api';

export function useAuth() {
  const navigate = useNavigate();

  function logout() {
    clearToken();
    navigate('/login');
  }

  return {
    isAuthenticated: !!getToken(),
    logout,
  };
}
