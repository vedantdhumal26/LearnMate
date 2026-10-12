import { useEffect, useState, useCallback } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import {
  Plus,
  BookOpen,
  Layers,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  ArrowRight,
  Target,
} from 'lucide-react';
import { AppLayout } from '@/layouts/AppLayout';
import { CourseCard } from '@/components/CourseCard';
import { SkeletonCardGrid } from '@/components/Skeleton';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { StudyPlanCard, formatActionLabel, getActionIcon } from '@/components/StudyPlanCard';
import { RenameCourseModal } from '@/components/RenameCourseModal';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { useAuth } from '@/contexts/AuthContext';
import { api, getErrorMessage } from '@/lib/api';
import type { Course, StudyPlanResponse, LearnerSummary } from '@/types';

export function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isCoursesPage = location.pathname.startsWith('/courses');
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [selectedCourseId, setSelectedCourseId] = useState<string>('');
  const [studyPlan, setStudyPlan] = useState<StudyPlanResponse | null>(null);
  const [learnerSummary, setLearnerSummary] = useState<LearnerSummary | null>(null);
  const [studyPlanLoading, setStudyPlanLoading] = useState(false);
  const [courseToRename, setCourseToRename] = useState<Course | null>(null);
  const [courseToDelete, setCourseToDelete] = useState<Course | null>(null);
  const [deleteCourseLoading, setDeleteCourseLoading] = useState(false);
  const [deleteCourseError, setDeleteCourseError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getCourses();
      setCourses(data);
      if (data.length > 0) {
        setSelectedCourseId((prev) => (prev && data.some((c) => c.id === prev) ? prev : data[0].id));
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function handleRenameSuccess(updated: Course) {
    setCourses((prev) =>
      prev.map((c) => (c.id === updated.id ? { ...c, ...updated } : c)),
    );
  }

  async function handleConfirmDelete() {
    if (!courseToDelete) return;
    setDeleteCourseLoading(true);
    setDeleteCourseError('');
    try {
      await api.deleteCourse(courseToDelete.id);
      setCourses((prev) => prev.filter((c) => c.id !== courseToDelete.id));
      if (selectedCourseId === courseToDelete.id) {
        setSelectedCourseId('');
      }
      setCourseToDelete(null);
    } catch (err) {
      setDeleteCourseError(getErrorMessage(err));
    } finally {
      setDeleteCourseLoading(false);
    }
  }

  // Load study plan & learner summary for the selected course
  useEffect(() => {
    if (!selectedCourseId || !user?.id) {
      setStudyPlan(null);
      setLearnerSummary(null);
      return;
    }

    let active = true;
    setStudyPlanLoading(true);

    Promise.all([
      api.getStudyPlan(user.id, selectedCourseId).catch(() => null),
      api.getLearnerSummary(user.id, selectedCourseId).catch(() => null),
    ])
      .then(([planData, summaryData]) => {
        if (!active) return;
        setStudyPlan(planData);
        setLearnerSummary(summaryData);
      })
      .finally(() => {
        if (active) setStudyPlanLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedCourseId, user?.id]);

  const activeCourse = courses.find((c) => c.id === selectedCourseId) || courses[0] || null;
  const todayPlan = studyPlan?.plan?.[0] || null;
  const isNewLearner = learnerSummary?.status === 'new_learner' || todayPlan?.action === 'diagnostic';

  const totalSources = courses.reduce((sum, c) => sum + (c.source_count ?? 0), 0);
  const totalChunks = courses.reduce((sum, c) => sum + (c.chunk_count ?? 0), 0);
  const displayName = user?.display_name || (user?.email ? user.email.split('@')[0] : 'Learner');

  function handleStartPractice() {
    if (!activeCourse || !todayPlan) return;
    const params = new URLSearchParams({
      topic: todayPlan.topic,
      difficulty: todayPlan.difficulty,
      count: String(todayPlan.question_count),
    });
    navigate(`/courses/${activeCourse.id}/assessments?${params.toString()}`);
  }

  function handleAskTutor() {
    if (!activeCourse || !todayPlan) return;
    const params = new URLSearchParams({
      topic: todayPlan.topic,
    });
    navigate(`/courses/${activeCourse.id}/tutor?${params.toString()}`);
  }

  return (
    <AppLayout>
      {/* Welcome & Action Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-ink-50">
              {isCoursesPage ? 'Courses' : `Welcome back, ${displayName}!`}
            </h1>
            <span className="inline-flex items-center rounded-full bg-brand-50 dark:bg-brand-950/60 px-2.5 py-0.5 text-xs font-semibold text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-800">
              {isCoursesPage
                ? `${courses.length} ${courses.length === 1 ? 'Course' : 'Courses'}`
                : 'Personalized Hub'}
            </span>
          </div>
          <p className="mt-1 text-sm text-ink-500 dark:text-ink-400">
            {isCoursesPage
              ? 'Explore your enrolled courses, multimodal materials, and personalized AI learning.'
              : 'Multi-modal learning with verified citations across PDFs, slides, videos, and YouTube.'}
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <Link to="/courses/new" className="btn-primary">
            <Plus className="h-4 w-4" />
            Create Course
          </Link>
        </div>
      </div>

      {/* Course Switcher (if user has multiple courses, on dashboard) */}
      {!isCoursesPage && !loading && courses.length > 1 && (
        <div className="mt-6 flex flex-wrap items-center gap-2 p-2 bg-ink-100/60 dark:bg-ink-900/60 rounded-xl border border-ink-200/80 dark:border-ink-800">
          <span className="text-xs font-semibold text-ink-600 dark:text-ink-400 px-2">Active Plan:</span>
          {courses.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedCourseId(c.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                c.id === (activeCourse?.id || '')
                  ? 'bg-white dark:bg-ink-800 text-brand-700 dark:text-brand-300 shadow-xs font-semibold'
                  : 'text-ink-600 dark:text-ink-400 hover:text-ink-900 dark:hover:text-ink-100 hover:bg-white/50 dark:hover:bg-ink-800/50'
              }`}
            >
              {c.title}
            </button>
          ))}
        </div>
      )}

      {/* Continue Learning Banner — based on Day 1 / current recommended action (on dashboard) */}
      {!isCoursesPage && !loading && activeCourse && todayPlan && (
        <div className="mt-6 rounded-2xl bg-gradient-to-r from-brand-900 via-brand-800 to-indigo-900 p-5 text-white shadow-sm">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1.5 flex-1 min-w-0">
              <div className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-0.5 text-[11px] font-medium text-white/90">
                <Sparkles className="h-3 w-3 text-brand-300" />
                Continue Learning &middot; Day 1 Focus
              </div>
              <h2 className="text-xl font-bold tracking-tight text-white truncate">
                Continue Learning: {todayPlan.topic}
              </h2>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="inline-flex items-center gap-1 rounded-md bg-white/15 px-2 py-0.5 text-white font-medium">
                  {getActionIcon(todayPlan.action)}
                  {formatActionLabel(todayPlan.action)}
                </span>
                <span className="rounded-md bg-white/15 px-2 py-0.5 text-white/90 capitalize font-medium">
                  {todayPlan.difficulty} difficulty
                </span>
                <span className="rounded-md bg-white/15 px-2 py-0.5 text-white/90 font-medium">
                  {todayPlan.question_count} questions
                </span>
              </div>
              <p className="text-xs text-white/75 max-w-xl leading-relaxed">
                {todayPlan.reason}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 shrink-0">
              <button
                onClick={handleStartPractice}
                className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3.5 py-2 text-xs font-semibold text-brand-900 shadow hover:bg-brand-50 transition-colors"
              >
                <Target className="h-3.5 w-3.5 text-brand-600" />
                Start Practice
              </button>
              <button
                onClick={handleAskTutor}
                className="inline-flex items-center gap-1.5 rounded-xl bg-white/10 border border-white/20 px-3.5 py-2 text-xs font-semibold text-white hover:bg-white/20 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Ask Tutor
              </button>
              <Link
                to={`/courses/${activeCourse.id}/learning`}
                className="inline-flex items-center gap-1.5 rounded-xl bg-white/10 border border-white/20 px-3.5 py-2 text-xs font-semibold text-white hover:bg-white/20 transition-colors"
              >
                <TrendingUp className="h-3.5 w-3.5" />
                7-Day Plan
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Compact "Your Study Plan" Card (on dashboard) */}
      {!isCoursesPage && !loading && activeCourse && (
        <div className="mt-6">
          <StudyPlanCard
            courseId={activeCourse.id}
            courseTitle={activeCourse.title}
            todayPlan={todayPlan}
            isNewLearner={isNewLearner}
            loading={studyPlanLoading}
          />
        </div>
      )}

      {/* Stats Row */}
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="card p-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400">
              <BookOpen className="h-4.5 w-4.5" />
            </span>
            <div>
              <p className="text-2xl font-bold text-ink-900 dark:text-ink-50">
                {loading ? '—' : courses.length}
              </p>
              <p className="text-xs text-ink-500 dark:text-ink-400 font-medium">Active Courses</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-50 dark:bg-accent-950/60 text-accent-600 dark:text-accent-400">
              <Layers className="h-4.5 w-4.5" />
            </span>
            <div>
              <p className="text-2xl font-bold text-ink-900 dark:text-ink-50">
                {loading ? '—' : totalSources}
              </p>
              <p className="text-xs text-ink-500 dark:text-ink-400 font-medium">Multimodal Sources</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
              <Sparkles className="h-4.5 w-4.5" />
            </span>
            <div>
              <p className="text-2xl font-bold text-ink-900 dark:text-ink-50">
                {loading ? '—' : totalChunks}
              </p>
              <p className="text-xs text-ink-500 dark:text-ink-400 font-medium">Indexed Chunks</p>
            </div>
          </div>
        </div>

        <Link
          to="/evaluation"
          className="card p-4 hover:border-brand-400 dark:hover:border-brand-500 hover:shadow-sm transition-all group block"
          title="Inspect Grounding Evaluation Benchmark"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 group-hover:bg-emerald-100 dark:group-hover:bg-emerald-900/40 transition-colors">
                <ShieldCheck className="h-4.5 w-4.5" />
              </span>
              <div>
                <p className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 uppercase tracking-wide">
                  Grounding Benchmark
                </p>
                <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">Zero Hallucination</p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-ink-400 group-hover:text-ink-700 dark:group-hover:text-ink-200 group-hover:translate-x-0.5 transition-all" />
          </div>
        </Link>
      </div>

      {/* Courses Section */}
      <div className="mt-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-ink-50">
            Your Courses
          </h2>
          <span className="text-xs text-ink-500 dark:text-ink-400">
            {courses.length} course{courses.length !== 1 ? 's' : ''} available
          </span>
        </div>

        {loading && <SkeletonCardGrid />}

        {!loading && error && (
          <ErrorState message={error} onRetry={load} />
        )}

        {!loading && !error && courses.length === 0 && (
          <EmptyState
            icon={<BookOpen className="h-7 w-7" />}
            title="No courses yet"
            description="Create your first course with PDFs, slides, lecture videos, or YouTube links to start learning."
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
              <CourseCard
                key={course.id}
                course={course}
                onRename={(c) => setCourseToRename(c)}
                onDelete={(c) => {
                  setDeleteCourseError('');
                  setCourseToDelete(c);
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Rename Course Modal */}
      <RenameCourseModal
        isOpen={!!courseToRename}
        onClose={() => setCourseToRename(null)}
        course={courseToRename}
        onSuccess={handleRenameSuccess}
      />

      {/* Delete Course Confirmation Dialog */}
      <ConfirmDialog
        isOpen={!!courseToDelete}
        onClose={() => !deleteCourseLoading && setCourseToDelete(null)}
        onConfirm={handleConfirmDelete}
        title="Delete Course"
        description={
          <div>
            Are you sure you want to delete{' '}
            <strong className="text-ink-900 dark:text-ink-100">
              {courseToDelete?.title}
            </strong>
            ?
            <p className="mt-2 text-xs text-err-600 dark:text-err-400 font-medium">
              This will permanently delete the course, all associated learning materials, uploaded files, and indexed vector embeddings. This action cannot be undone.
            </p>
          </div>
        }
        confirmLabel="Delete Course"
        cancelLabel="Keep Course"
        isDanger={true}
        isLoading={deleteCourseLoading}
        error={deleteCourseError}
      />
    </AppLayout>
  );
}
