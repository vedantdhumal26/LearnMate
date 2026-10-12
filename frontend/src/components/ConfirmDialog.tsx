import React, { useEffect } from 'react';
import { AlertTriangle, Loader2, X } from 'lucide-react';

export interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  isDanger?: boolean;
  isLoading?: boolean;
  error?: string;
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  isDanger = true,
  isLoading = false,
  error = '',
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !isLoading) {
        onClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isLoading, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in"
      onClick={() => !isLoading && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="absolute inset-0 bg-ink-900/40 dark:bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-md rounded-2xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 p-6 shadow-pop animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-4">
          <span
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${
              isDanger
                ? 'bg-err-50 dark:bg-err-950/60 text-err-600 dark:text-err-400'
                : 'bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400'
            }`}
          >
            <AlertTriangle className="h-6 w-6" />
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <h3
                id="confirm-dialog-title"
                className="font-display text-base font-semibold text-ink-900 dark:text-ink-50"
              >
                {title}
              </h3>
              {!isLoading && (
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-600 dark:text-ink-500 dark:hover:bg-ink-800 dark:hover:text-ink-300 transition-colors"
                  aria-label="Close"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <div className="mt-2 text-sm text-ink-500 dark:text-ink-400 leading-relaxed">
              {description}
            </div>

            {error && (
              <div className="mt-3 rounded-lg border border-err-200 dark:border-err-800 bg-err-50 dark:bg-err-950/50 p-2.5 text-xs text-err-600 dark:text-err-400">
                {error}
              </div>
            )}

            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                disabled={isLoading}
                className="btn-secondary text-xs sm:text-sm px-3.5 py-2"
              >
                {cancelLabel}
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={isLoading}
                className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-xs sm:text-sm font-semibold text-white shadow-sm transition-all disabled:opacity-50 ${
                  isDanger
                    ? 'bg-err-600 hover:bg-err-700 active:scale-[0.98]'
                    : 'bg-brand-600 hover:bg-brand-700 active:scale-[0.98]'
                }`}
              >
                {isLoading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {confirmLabel}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
