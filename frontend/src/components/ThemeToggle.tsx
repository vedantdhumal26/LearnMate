import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';

interface ThemeToggleProps {
  id?: string;
  className?: string;
  showLabel?: boolean;
}

export function ThemeToggle({
  id = 'theme-toggle',
  className = '',
  showLabel = false,
}: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();

  const isDark = theme === 'dark';
  const label = isDark ? 'Switch to light mode' : 'Switch to dark mode';

  return (
    <button
      type="button"
      id={id}
      onClick={toggleTheme}
      className={`group relative inline-flex items-center justify-center gap-2 rounded-lg p-2 text-sm font-medium transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 ${
        isDark
          ? 'text-amber-400 hover:bg-ink-800 hover:text-amber-300'
          : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900'
      } ${className}`}
      title={label}
      aria-label={label}
    >
      {isDark ? (
        <Moon className="h-4.5 w-4.5 shrink-0 transition-transform duration-300 group-hover:-rotate-12 text-brand-400" />
      ) : (
        <Sun className="h-4.5 w-4.5 shrink-0 transition-transform duration-300 group-hover:rotate-45 text-amber-500" />
      )}
      {showLabel && (
        <span className="text-xs font-medium text-ink-700 dark:text-ink-200">
          {isDark ? 'Dark Mode' : 'Light Mode'}
        </span>
      )}
    </button>
  );
}
