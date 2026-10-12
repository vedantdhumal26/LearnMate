import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';

export type Theme = 'light' | 'dark';

export interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const STORAGE_KEY = 'learnsphere-theme';

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

function getSystemPreference(): Theme {
  if (typeof window === 'undefined') return 'light';
  try {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
  } catch {
    return 'light';
  }
}

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'light' || saved === 'dark') {
      return saved;
    }
  } catch {
    // localStorage disabled or blocked
  }
  return getSystemPreference();
}

function applyThemeToDocument(theme: Theme) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (theme === 'dark') {
    root.classList.add('dark');
    root.setAttribute('data-theme', 'dark');
  } else {
    root.classList.remove('dark');
    root.setAttribute('data-theme', 'light');
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);
  const transitionTimerRef = useRef<number | null>(null);

  // Synchronize documentElement attributes on mount and on theme change
  useEffect(() => {
    applyThemeToDocument(theme);
  }, [theme]);

  // Listen to system preference changes if user hasn't explicitly set localStorage
  useEffect(() => {
    try {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      const handleSystemChange = (e: MediaQueryListEvent) => {
        try {
          const saved = localStorage.getItem(STORAGE_KEY);
          if (!saved) {
            const next = e.matches ? 'dark' : 'light';
            setThemeState(next);
            applyThemeToDocument(next);
          }
        } catch {
          // ignore storage read failure
        }
      };

      mediaQuery.addEventListener('change', handleSystemChange);
      return () => mediaQuery.removeEventListener('change', handleSystemChange);
    } catch {
      // media query unsupported
    }
  }, []);

  const triggerSubtleTransition = useCallback(() => {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    root.classList.add('theme-transitioning');
    if (transitionTimerRef.current) {
      window.clearTimeout(transitionTimerRef.current);
    }
    transitionTimerRef.current = window.setTimeout(() => {
      root.classList.remove('theme-transitioning');
      transitionTimerRef.current = null;
    }, 250);
  }, []);

  const setTheme = useCallback(
    (newTheme: Theme) => {
      triggerSubtleTransition();
      setThemeState(newTheme);
      applyThemeToDocument(newTheme);
      try {
        localStorage.setItem(STORAGE_KEY, newTheme);
      } catch {
        // localStorage not available
      }
    },
    [triggerSubtleTransition],
  );

  const toggleTheme = useCallback(() => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
  }, [theme, setTheme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
