import { Link } from 'react-router-dom';
import {
  BookOpen,
  FileText,
  Layers,
  ArrowRight,
  Calendar,
  Sparkles,
  BarChart3,
  TrendingUp,
  Edit3,
  Trash2,
} from 'lucide-react';
import type { Course } from '@/types';

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

export interface CourseCardProps {
  course: Course;
  onRename?: (course: Course) => void;
  onDelete?: (course: Course) => void;
}

export function CourseCard({ course, onRename, onDelete }: CourseCardProps) {
  return (
    <div className="card-hover group flex flex-col justify-between p-5 animate-fade-in-up bg-white dark:bg-ink-900">
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <Link to={`/courses/${course.id}`} className="block">
              <h3 className="font-display text-base font-semibold text-ink-900 dark:text-ink-100 truncate hover:text-brand-600 dark:hover:text-brand-400 transition-colors">
                {course.title}
              </h3>
            </Link>
            <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400 line-clamp-2">
              {course.description || 'No description provided.'}
            </p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {onRename && (
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onRename(course);
                }}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-400 hover:bg-ink-100 hover:text-brand-600 dark:hover:bg-ink-800 dark:hover:text-brand-400 transition-colors"
                title="Rename Course"
                aria-label={`Rename ${course.title}`}
              >
                <Edit3 className="h-4 w-4" />
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onDelete(course);
                }}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-400 hover:bg-err-50 hover:text-err-600 dark:hover:bg-err-950/60 dark:hover:text-err-400 transition-colors"
                title="Delete Course"
                aria-label={`Delete ${course.title}`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
            <Link
              to={`/courses/${course.id}`}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-600 hover:bg-brand-100 dark:bg-brand-950/60 dark:text-brand-400 dark:hover:bg-brand-900/60 transition-colors"
              title="Open Course"
              aria-label={`Open ${course.title}`}
            >
              <BookOpen className="h-4 w-4" />
            </Link>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-500 dark:text-ink-400">
          <span className="inline-flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 text-ink-400 dark:text-ink-500" />
            {course.source_count ?? 0} sources
          </span>
          {course.chunk_count != null && (
            <span className="inline-flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5 text-ink-400 dark:text-ink-500" />
              {course.chunk_count} chunks
            </span>
          )}
          <span className="inline-flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5 text-ink-400 dark:text-ink-500" />
            {formatDate(course.created_at)}
          </span>
        </div>
      </div>

      <div className="mt-5 pt-3.5 border-t border-ink-100 dark:border-ink-800">
        <div className="flex items-center justify-between gap-2">
          {/* Direct quick action buttons */}
          <div className="flex items-center gap-1.5">
            <Link
              to={`/courses/${course.id}/tutor`}
              className="inline-flex items-center gap-1 rounded-md bg-brand-50 px-2 py-1 text-[11px] font-semibold text-brand-700 hover:bg-brand-100 dark:bg-brand-950/60 dark:text-brand-300 dark:hover:bg-brand-900/60 transition-colors"
              title="Open AI Tutor"
            >
              <Sparkles className="h-3 w-3" />
              Tutor
            </Link>
            <Link
              to={`/courses/${course.id}/assessments`}
              className="inline-flex items-center gap-1 rounded-md bg-brand-50 px-2 py-1 text-[11px] font-semibold text-brand-700 hover:bg-brand-100 dark:bg-brand-950/60 dark:text-brand-300 dark:hover:bg-brand-900/60 transition-colors"
              title="Quizzes & Assessments"
            >
              <BarChart3 className="h-3 w-3" />
              Quiz
            </Link>
            <Link
              to={`/courses/${course.id}/learning`}
              className="inline-flex items-center gap-1 rounded-md bg-brand-50 px-2 py-1 text-[11px] font-semibold text-brand-700 hover:bg-brand-100 dark:bg-brand-950/60 dark:text-brand-300 dark:hover:bg-brand-900/60 transition-colors"
              title="Track Mastery"
            >
              <TrendingUp className="h-3 w-3" />
              Mastery
            </Link>
          </div>

          <Link
            to={`/courses/${course.id}`}
            className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300 transition-colors ml-auto shrink-0"
          >
            Open
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
