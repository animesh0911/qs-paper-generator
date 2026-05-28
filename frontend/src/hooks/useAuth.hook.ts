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
