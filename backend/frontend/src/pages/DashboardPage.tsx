import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Plus, BookOpen, LayoutDashboard, AlertCircle } from 'lucide-react';
import { AppLayout } from '@/layouts/AppLayout';
import { CourseCard } from '@/components/CourseCard';
import { SkeletonCardGrid } from '@/components/Skeleton';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { api, getErrorMessage } from '@/lib/api';
import type { Course } from '@/types';

export function DashboardPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getCourses();
      setCourses(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AppLayout>
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900">
            Your Learning Space
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Manage your courses and start learning with your AI tutor.
          </p>
        </div>
        <Link to="/courses/new" className="btn-primary shrink-0">
          <Plus className="h-4 w-4" />
          Create Course
        </Link>
      </div>

      {/* Stats row */}
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <div className="card p-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
              <BookOpen className="h-4.5 w-4.5" />
            </span>
            <div>
              <p className="text-2xl font-bold text-ink-900">
                {loading ? '—' : courses.length}
              </p>
              <p className="text-xs text-ink-500">Courses</p>
            </div>
          </div>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-50 text-accent-600">
              <LayoutDashboard className="h-4.5 w-4.5" />
            </span>
            <div>
              <p className="text-2xl font-bold text-ink-900">
                {loading ? '—' : courses.reduce((sum, c) => sum + (c.source_count ?? 0), 0)}
              </p>
              <p className="text-xs text-ink-500">Source files</p>
            </div>
          </div>
        </div>
        <div className="card p-4 col-span-2 sm:col-span-1">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-warn-50 text-warn-600">
              <AlertCircle className="h-4.5 w-4.5" />
            </span>
            <div>
              <p className="text-2xl font-bold text-ink-900">
                {loading ? '—' : courses.reduce((sum, c) => sum + (c.chunk_count ?? 0), 0)}
              </p>
              <p className="text-xs text-ink-500">Knowledge chunks</p>
            </div>
          </div>
        </div>
      </div>

      {/* Courses */}
      <div className="mt-8">
        <h2 className="font-display text-lg font-semibold text-ink-900 mb-4">
          Courses
        </h2>

        {loading && <SkeletonCardGrid />}

        {!loading && error && (
          <ErrorState message={error} onRetry={load} />
        )}

        {!loading && !error && courses.length === 0 && (
          <EmptyState
            icon={<BookOpen className="h-7 w-7" />}
            title="No courses yet"
            description="Create your first course by uploading your study material."
            action={
              <Link to="/courses/new" className="btn-primary">
                <Plus className="h-4 w-4" />
                Create Course
              </Link>
            }
          />
        )}

        {!loading && !error && courses.length > 0 && (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {courses.map((course) => (
              <CourseCard key={course.id} course={course} />
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
