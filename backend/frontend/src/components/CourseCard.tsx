import { Link } from 'react-router-dom';
import { BookOpen, FileText, Layers, ArrowRight, Calendar } from 'lucide-react';
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

export function CourseCard({ course }: { course: Course }) {
  return (
    <Link
      to={`/courses/${course.id}`}
      className="card-hover group block p-5 animate-fade-in-up"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-display text-base font-semibold text-ink-900 truncate group-hover:text-brand-700 transition-colors">
            {course.title}
          </h3>
          <p className="mt-1.5 text-sm text-ink-500 line-clamp-2">
            {course.description || 'No description provided.'}
          </p>
        </div>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
          <BookOpen className="h-5 w-5" />
        </span>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-500">
        <span className="inline-flex items-center gap-1.5">
          <FileText className="h-3.5 w-3.5" />
          {course.source_count ?? 0} sources
        </span>
        {course.chunk_count != null && (
          <span className="inline-flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5" />
            {course.chunk_count} chunks
          </span>
        )}
        <span className="inline-flex items-center gap-1.5">
          <Calendar className="h-3.5 w-3.5" />
          {formatDate(course.created_at)}
        </span>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-ink-100 pt-3.5">
        <span className="text-xs font-medium text-ink-400">
          Created {formatDate(course.created_at)}
        </span>
        <span className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 group-hover:text-brand-700 transition-colors">
          Open Course
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </span>
      </div>
    </Link>
  );
}
