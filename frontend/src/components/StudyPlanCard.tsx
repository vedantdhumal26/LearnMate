import { Link, useNavigate } from 'react-router-dom';
import {
  Calendar,
  Sparkles,
  Target,
  ArrowRight,
  BookOpen,
  Zap,
  HelpCircle,
  Clock,
  Compass,
} from 'lucide-react';
import type { StudyPlanItem } from '@/types';

interface StudyPlanCardProps {
  courseId: string;
  courseTitle?: string;
  todayPlan?: StudyPlanItem | null;
  isNewLearner?: boolean;
  loading?: boolean;
}

export function formatActionLabel(action: string): string {
  switch (action) {
    case 'practice':
      return 'Practice Quiz';
    case 'tutor_review':
      return 'Tutor Review';
    case 'review_material':
      return 'Review Material';
    case 'challenge':
      return 'Challenge Quiz';
    case 'diagnostic':
      return 'Diagnostic Assessment';
    default:
      return action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

export function getActionIcon(action: string) {
  switch (action) {
    case 'practice':
      return <Target className="h-3.5 w-3.5" />;
    case 'tutor_review':
      return <Sparkles className="h-3.5 w-3.5" />;
    case 'review_material':
      return <BookOpen className="h-3.5 w-3.5" />;
    case 'challenge':
      return <Zap className="h-3.5 w-3.5" />;
    case 'diagnostic':
      return <Compass className="h-3.5 w-3.5" />;
    default:
      return <HelpCircle className="h-3.5 w-3.5" />;
  }
}

export function getDifficultyBadge(diff: string) {
  const normalized = diff.toLowerCase();
  if (normalized === 'easy') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-950/60 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60 capitalize">
        Easy
      </span>
    );
  }
  if (normalized === 'hard') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 dark:bg-purple-950/60 px-2.5 py-0.5 text-xs font-semibold text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800/60 capitalize">
        Hard
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 dark:bg-amber-950/60 px-2.5 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/60 capitalize">
      Medium
    </span>
  );
}

export function getPriorityBadge(priority: string) {
  const p = priority.toLowerCase();
  if (p === 'high') return <span className="badge-error">High priority</span>;
  if (p === 'medium') return <span className="badge-warn">Medium priority</span>;
  return <span className="badge-neutral">Low priority</span>;
}

export function StudyPlanCard({
  courseId,
  courseTitle,
  todayPlan,
  isNewLearner = false,
  loading = false,
}: StudyPlanCardProps) {
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="card p-5 animate-pulse">
        <div className="flex items-center justify-between mb-4">
          <div className="h-4 bg-ink-100 rounded w-1/4"></div>
          <div className="h-4 bg-ink-100 rounded w-16"></div>
        </div>
        <div className="h-5 bg-ink-200 rounded w-1/2 mb-3"></div>
        <div className="h-3 bg-ink-100 rounded w-3/4 mb-4"></div>
        <div className="flex gap-2">
          <div className="h-8 bg-ink-200 rounded w-24"></div>
          <div className="h-8 bg-ink-100 rounded w-20"></div>
        </div>
      </div>
    );
  }

  // Handle case where course has no study plan yet
  if (!todayPlan) {
    return (
      <div className="card p-6 border-dashed border-ink-300 dark:border-ink-700">
        <div className="flex items-start gap-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400">
            <Calendar className="h-5 w-5" />
          </span>
          <div>
            <h3 className="font-display text-base font-bold text-ink-900 dark:text-ink-50">
              Your Study Plan
            </h3>
            <p className="mt-1 text-sm text-ink-500 dark:text-ink-400">
              Let&apos;s build your learning plan. Upload materials or complete your first assessment to generate a tailored 7-day schedule.
            </p>
          </div>
        </div>
      </div>
    );
  }

  function handleStartPractice() {
    if (!todayPlan) return;
    const params = new URLSearchParams({
      topic: todayPlan.topic,
      difficulty: todayPlan.difficulty,
      count: String(todayPlan.question_count),
    });
    navigate(`/courses/${courseId}/assessments?${params.toString()}`);
  }

  function handleAskTutor() {
    if (!todayPlan) return;
    const params = new URLSearchParams({
      topic: todayPlan.topic,
    });
    navigate(`/courses/${courseId}/tutor?${params.toString()}`);
  }

  return (
    <div className="card p-5 border-l-4 border-l-brand-600 dark:border-l-brand-500 hover:shadow-card-hover transition-all">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-ink-100 dark:border-ink-800">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400">
            <Calendar className="h-4 w-4" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display text-base font-bold text-ink-900 dark:text-ink-50">
                Your Study Plan
              </h2>
              <span className="inline-flex items-center gap-1 rounded-full bg-brand-100/70 dark:bg-brand-950/60 px-2 py-0.5 text-[11px] font-semibold text-brand-800 dark:text-brand-300">
                <Clock className="h-3 w-3" />
                Day 1 · Today
              </span>
            </div>
            {courseTitle && (
              <p className="text-xs text-ink-500 dark:text-ink-400 line-clamp-1">
                Course: {courseTitle}
              </p>
            )}
          </div>
        </div>

        <Link
          to={`/courses/${courseId}/learning`}
          className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 dark:text-brand-400 hover:text-brand-800 dark:hover:text-brand-300 transition-colors"
        >
          View Full 7-Day Plan
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      {/* New learner notice if applicable */}
      {isNewLearner && (
        <div className="mt-3 rounded-lg bg-brand-50/60 dark:bg-brand-950/40 border border-brand-200/80 dark:border-brand-800/60 p-3 text-xs text-brand-900 dark:text-brand-200">
          <p className="font-semibold flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
            Let&apos;s build your learning plan
          </p>
          <p className="mt-0.5 text-ink-600 dark:text-ink-300">
            Your first assessment will personalize recommendations and set baseline mastery. No mastery is assumed until you test.
          </p>
        </div>
      )}

      {/* Today's Card Details */}
      <div className="mt-4 space-y-3">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-400 dark:text-ink-500">
            Today&apos;s Topic
          </span>
          <div className="flex flex-wrap items-center gap-2 mt-0.5">
            <h3 className="text-lg font-bold text-ink-900 dark:text-ink-50 tracking-tight">
              {todayPlan.topic}
            </h3>
            {getPriorityBadge(todayPlan.priority)}
          </div>
        </div>

        {/* Metadata badges row */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 rounded-lg bg-ink-100 dark:bg-ink-800 px-2.5 py-1 text-ink-700 dark:text-ink-200 font-medium">
            {getActionIcon(todayPlan.action)}
            <span>{formatActionLabel(todayPlan.action)}</span>
          </div>

          <div>{getDifficultyBadge(todayPlan.difficulty)}</div>

          <div className="inline-flex items-center gap-1 rounded-full bg-ink-100 dark:bg-ink-800 px-2.5 py-0.5 font-medium text-ink-600 dark:text-ink-300">
            <Target className="h-3 w-3" />
            {todayPlan.question_count} Questions
          </div>
        </div>

        {/* Reason */}
        {todayPlan.reason && (
          <div className="rounded-lg bg-ink-50 dark:bg-ink-800/70 p-2.5 text-xs text-ink-600 dark:text-ink-300 border border-ink-150 dark:border-ink-700">
            <span className="font-semibold text-ink-700 dark:text-ink-200">Reason: </span>
            {todayPlan.reason}
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="mt-5 flex flex-wrap items-center gap-2 pt-3 border-t border-ink-100 dark:border-ink-800">
        <button
          onClick={handleStartPractice}
          className="btn-primary text-xs py-2 px-3.5 inline-flex items-center gap-1.5"
        >
          <Target className="h-3.5 w-3.5" />
          Start Practice
        </button>

        <button
          onClick={handleAskTutor}
          className="btn-secondary text-xs py-2 px-3.5 inline-flex items-center gap-1.5"
        >
          <Sparkles className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
          Ask Tutor
        </button>
      </div>
    </div>
  );
}
