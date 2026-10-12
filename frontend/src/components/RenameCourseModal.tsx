import React, { useState, useEffect } from 'react';
import { BookOpen, Loader2, AlertCircle, X } from 'lucide-react';
import { api, getErrorMessage } from '@/lib/api';
import type { Course } from '@/types';

export interface RenameCourseModalProps {
  isOpen: boolean;
  onClose: () => void;
  course: Course | null;
  onSuccess: (updated: Course) => void;
}

export function RenameCourseModal({
  isOpen,
  onClose,
  course,
  onSuccess,
}: RenameCourseModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen && course) {
      setTitle(course.title || '');
      setDescription(course.description || '');
      setError('');
      setSaving(false);
    }
  }, [isOpen, course]);

  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !saving) {
        onClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, saving, onClose]);

  if (!isOpen || !course) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!course) return;
    setError('');

    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError('Course title cannot be blank.');
      return;
    }

    setSaving(true);
    try {
      const updated = await api.updateCourse(course.id, {
        title: cleanTitle,
        description: description.trim() || undefined,
      });
      onSuccess(updated);
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in"
      onClick={() => !saving && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="rename-course-title"
    >
      <div className="absolute inset-0 bg-ink-900/40 dark:bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg rounded-2xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 shadow-pop animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-ink-100 dark:border-ink-800 px-6 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-950/60 dark:text-brand-400">
              <BookOpen className="h-5 w-5" />
            </span>
            <h3
              id="rename-course-title"
              className="font-display text-base font-semibold text-ink-900 dark:text-ink-50"
            >
              Rename Course
            </h3>
          </div>
          {!saving && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-600 dark:text-ink-500 dark:hover:bg-ink-800 dark:hover:text-ink-300 transition-colors"
              aria-label="Close"
            >
              <X className="h-4.5 w-4.5" />
            </button>
          )}
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} noValidate className="p-6 space-y-4">
          {error && (
            <div className="flex items-start gap-2.5 rounded-lg border border-err-200 dark:border-err-800 bg-err-50 dark:bg-err-950/40 p-3 text-xs text-err-700 dark:text-err-300">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-err-600 dark:text-err-400" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label htmlFor="course-rename-title" className="label">
              Course Title <span className="text-err-500">*</span>
            </label>
            <input
              id="course-rename-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Advanced Quantum Algorithms"
              required
              disabled={saving}
              maxLength={255}
              autoFocus
              className="input"
            />
          </div>

          <div>
            <label htmlFor="course-rename-description" className="label">
              Description (Optional)
            </label>
            <textarea
              id="course-rename-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief summary of topics covered in this course"
              disabled={saving}
              rows={3}
              className="input resize-none"
            />
          </div>

          <div className="mt-6 flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="btn-primary"
            >
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save Changes'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
