import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-ink-300 dark:border-ink-800 bg-white/60 dark:bg-ink-900/60 px-6 py-16 text-center animate-fade-in">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-ink-100 dark:bg-ink-800 text-ink-400 dark:text-ink-500 mb-5">
        {icon}
      </div>
      <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-sm text-sm text-ink-500 dark:text-ink-400">{description}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
