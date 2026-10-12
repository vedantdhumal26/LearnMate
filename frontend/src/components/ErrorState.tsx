import type { ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  action?: ReactNode;
}

export function ErrorState({ message, onRetry, action }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-err-200 dark:border-err-800/80 bg-err-50/50 dark:bg-err-950/30 px-6 py-12 text-center animate-fade-in">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-err-100 dark:bg-err-950/70 text-err-500 dark:text-err-400 mb-4">
        <AlertCircle className="h-7 w-7" />
      </div>
      <p className="max-w-sm text-sm text-err-700 dark:text-err-300">{message}</p>
      <div className="mt-5 flex items-center gap-3">
        {onRetry && (
          <button onClick={onRetry} className="btn-secondary">
            <RefreshCw className="h-4 w-4" />
            Try again
          </button>
        )}
        {action}
      </div>
    </div>
  );
}
