import type { User } from '@/types';

const TOKEN_KEY = 'learnsphere_auth_token';
const USER_KEY = 'learnsphere_auth_user';

export const AUTH_UNAUTHORIZED_EVENT = 'learnsphere:unauthorized';

export const tokenStorage = {
  getToken(): string | null {
    try {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token || typeof token !== 'string' || token.trim() === '') {
        return null;
      }
      return token.trim();
    } catch {
      return null;
    }
  },

  setToken(token: string): void {
    try {
      if (token && typeof token === 'string' && token.trim() !== '') {
        localStorage.setItem(TOKEN_KEY, token.trim());
      } else {
        localStorage.removeItem(TOKEN_KEY);
      }
    } catch {
      // Ignore storage errors in restricted contexts
    }
  },

  getUser(): User | null {
    try {
      const raw = localStorage.getItem(USER_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as User;
      if (parsed && typeof parsed.id === 'string') {
        return parsed;
      }
      return null;
    } catch {
      return null;
    }
  },

  setUser(user: User): void {
    try {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } catch {
      // Ignore storage errors
    }
  },

  clearAuth(): void {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      // Clean up legacy demo student ID if present
      localStorage.removeItem('learnsphere_student_id');

      // Clear any session-cached assessment results from previous user
      try {
        const keysToRemove: string[] = [];
        for (let i = 0; i < sessionStorage.length; i++) {
          const k = sessionStorage.key(i);
          if (k && (k.startsWith('assessment_result_') || k.startsWith('learnsphere_'))) {
            keysToRemove.push(k);
          }
        }
        keysToRemove.forEach((k) => sessionStorage.removeItem(k));
      } catch {
        // Ignore sessionStorage errors
      }
    } catch {
      // Ignore storage errors
    }
  },

  notifyUnauthorized(): void {
    this.clearAuth();
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(AUTH_UNAUTHORIZED_EVENT));
    }
  },
};
