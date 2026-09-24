import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import { authApi, AuthUser } from '@/lib/api';
import { AxiosError } from 'axios';

// ── Types ─────────────────────────────────────────────────────────────────────

interface AuthState {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string, remember?: boolean) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

// ── Storage helpers ───────────────────────────────────────────────────────────
// "Remember me" → localStorage (persists across browser restarts)
// Default       → sessionStorage (cleared when tab/browser closes)

const TOKEN_KEY = 'crophub_token';
const USER_KEY  = 'crophub_user';

function persistSession(token: string, user: AuthUser, remember: boolean) {
  const store = remember ? localStorage : sessionStorage;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
  store.setItem(TOKEN_KEY, token);
  store.setItem(USER_KEY, JSON.stringify(user));
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

function loadSession(): { token: string | null; user: AuthUser | null } {
  const token = localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
  const raw   = localStorage.getItem(USER_KEY)  || sessionStorage.getItem(USER_KEY);
  let user: AuthUser | null = null;
  try { if (raw) user = JSON.parse(raw) as AuthUser; } catch { user = null; }
  return { token, user };
}

// ── Context ───────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const { token, user } = loadSession();
    return {
      user,
      token,
      isAuthenticated: Boolean(token && user),
      isLoading: Boolean(token),
    };
  });

  useEffect(() => {
    const { token } = loadSession();
    if (!token) { setState((s) => ({ ...s, isLoading: false })); return; }
    authApi.getMe()
      .then(({ data }) => {
        setState({ user: data.data.user, token, isAuthenticated: true, isLoading: false });
      })
      .catch(() => {
        clearSession();
        setState({ user: null, token: null, isAuthenticated: false, isLoading: false });
      });
  }, []);

  const login = useCallback(async (email: string, password: string, remember = false) => {
    const { data } = await authApi.login({ email, password });
    const { token, user } = data.data;
    persistSession(token, user, remember);
    setState({ user, token, isAuthenticated: true, isLoading: false });
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const { data } = await authApi.register({ name, email, password });
    const { token, user } = data.data;
    persistSession(token, user, true);
    setState({ user, token, isAuthenticated: true, isLoading: false });
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setState({ user: null, token: null, isAuthenticated: false, isLoading: false });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

export function getApiError(error: unknown): string {
  if (error instanceof AxiosError) {
    const data = error.response?.data;
    if (Array.isArray(data?.errors)) {
      return data.errors.map((e: { message: string }) => e.message).join(', ');
    }
    return data?.message || error.message;
  }
  return 'An unexpected error occurred';
}