import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import type { User, LoginRequest, SignupRequest, UpdateUserPayload } from '@/types';
import { api } from '@/lib/api';
import { tokenStorage, AUTH_UNAUTHORIZED_EVENT } from '@/lib/auth-token';

export interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (payload: LoginRequest) => Promise<void>;
  signup: (payload: SignupRequest) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<User | null>;
  updateProfile: (payload: UpdateUserPayload) => Promise<User>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => tokenStorage.getToken());
  const [user, setUser] = useState<User | null>(() => tokenStorage.getUser());
  const [loading, setLoading] = useState<boolean>(true);

  const logout = useCallback(() => {
    tokenStorage.clearAuth();
    setToken(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<User | null> => {
    const currentToken = tokenStorage.getToken();
    if (!currentToken) {
      setUser(null);
      setToken(null);
      return null;
    }

    try {
      const currentUser = await api.getMe();
      if (currentUser && currentUser.id) {
        tokenStorage.setUser(currentUser);
        setUser(currentUser);
        setToken(currentToken);
        return currentUser;
      } else {
        throw new Error('Invalid user payload');
      }
    } catch {
      // 401 or invalid session
      tokenStorage.clearAuth();
      setUser(null);
      setToken(null);
      return null;
    }
  }, []);

  // Application startup authentication check
  useEffect(() => {
    let mounted = true;

    async function initAuth() {
      const storedToken = tokenStorage.getToken();
      if (!storedToken) {
        if (mounted) {
          setUser(null);
          setToken(null);
          setLoading(false);
        }
        return;
      }

      try {
        const currentUser = await api.getMe();
        if (mounted) {
          if (currentUser && currentUser.id) {
            tokenStorage.setUser(currentUser);
            setUser(currentUser);
            setToken(storedToken);
          } else {
            tokenStorage.clearAuth();
            setUser(null);
            setToken(null);
          }
        }
      } catch {
        if (mounted) {
          tokenStorage.clearAuth();
          setUser(null);
          setToken(null);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    initAuth();

    // Central listener for 401 unauthorized events dispatched by API client
    function handleUnauthorized() {
      if (mounted) {
        setUser(null);
        setToken(null);
      }
    }

    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => {
      mounted = false;
      window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    };
  }, []);

  const login = useCallback(async (payload: LoginRequest): Promise<void> => {
    const res = await api.login(payload);
    const accessToken = res.access_token || (res as unknown as { token?: string }).token;
    if (!accessToken) {
      throw new Error('Authentication succeeded but no access token was returned.');
    }

    tokenStorage.setToken(accessToken);
    setToken(accessToken);

    let resolvedUser = res.user;
    if (!resolvedUser || !resolvedUser.id) {
      // If user object was omitted in response, fetch it from /api/auth/me
      try {
        resolvedUser = await api.getMe();
      } catch {
        // Fallback user placeholder
        resolvedUser = {
          id: 'user',
          email: payload.email,
          display_name: payload.email.split('@')[0],
        };
      }
    }

    tokenStorage.setUser(resolvedUser);
    setUser(resolvedUser);
  }, []);

  const signup = useCallback(async (payload: SignupRequest): Promise<void> => {
    const res = await api.signup(payload);
    const accessToken = res.access_token || (res as unknown as { token?: string }).token;
    if (!accessToken) {
      throw new Error('Registration succeeded but no access token was returned.');
    }

    tokenStorage.setToken(accessToken);
    setToken(accessToken);

    let resolvedUser = res.user;
    if (!resolvedUser || !resolvedUser.id) {
      try {
        resolvedUser = await api.getMe();
      } catch {
        resolvedUser = {
          id: 'user',
          email: payload.email,
          display_name: payload.display_name,
        };
      }
    }

    tokenStorage.setUser(resolvedUser);
    setUser(resolvedUser);
  }, []);

  const updateProfile = useCallback(async (payload: UpdateUserPayload): Promise<User> => {
    const updated = await api.updateMe(payload);
    tokenStorage.setUser(updated);
    setUser(updated);
    return updated;
  }, []);

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!token && !!user,
    loading,
    login,
    signup,
    logout,
    refreshUser,
    updateProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
