/**
 * Login / Register page — the only anonymous route.
 *
 * Talks directly to `lib/api.login` / `lib/api.register`, which store the
 * returned token in localStorage. On success, navigates to `/` with a small
 * welcome name for the authenticated welcome screen.
 *
 * @module LoginPage
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, register } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('teacher@example.com');
  const [password, setPassword] = useState('teacher123');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const result =
        mode === 'login'
          ? await login(email, password)
          : await register(email, password);
      const welcomeName = displayNameFromEmail(result.user?.email || email);
      rememberWelcomeName(welcomeName);
      navigate('/', { state: { welcomeName } });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>
            {mode === 'login' ? 'Sign in' : 'Create account'}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Exam Desk — Class 10 Science
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-3">
            <Input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy
                ? 'Please wait…'
                : mode === 'login'
                  ? 'Sign in'
                  : 'Register'}
            </Button>
          </form>
          <button
            className="mt-4 text-sm text-muted-foreground underline w-full text-center"
            onClick={() => {
              setError('');
              setMode(mode === 'login' ? 'register' : 'login');
            }}
          >
            {mode === 'login'
              ? 'Need an account? Register'
              : 'Have an account? Sign in'}
          </button>
        </CardContent>
      </Card>
    </div>
  );
}

const WELCOME_NAME_STORAGE_KEY = 'qpg_welcome_name';

function rememberWelcomeName(name: string) {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.setItem(WELCOME_NAME_STORAGE_KEY, name);
}

function displayNameFromEmail(email: string): string {
  const localPart = email.split('@')[0] || 'teacher';
  const [firstName] = localPart.split(/[._-]+/).filter(Boolean);
  if (!firstName) return 'Teacher';
  return firstName.charAt(0).toUpperCase() + firstName.slice(1);
}
