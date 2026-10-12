import { useNavigate } from 'react-router-dom';
import {
  Calendar,
  Sparkles,
  Target,
  Clock,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';
import type { StudyPlanItem } from '@/types';
import {
  formatActionLabel,
  getActionIcon,
  getDifficultyBadge,
  getPriorityBadge,
} from './StudyPlanCard';

interface StudyPlanSectionProps {
  courseId: string;
  plan: StudyPlanItem[];
  isNewLearner?: boolean;
}

export function StudyPlanSection({
  courseId,
  plan,
  isNewLearner = false,
}: StudyPlanSectionProps) {
  const navigate = useNavigate();

  function handleStartPractice(item: StudyPlanItem) {
    const params = new URLSearchParams({
      topic: item.topic,
      difficulty: item.difficulty,
      count: String(item.question_count),
    });
    navigate(`/courses/${courseId}/assessments?${params.toString()}`);
  }

  function handleAskTutor(item: StudyPlanItem) {
    const params = new URLSearchParams({
      topic: item.topic,
    });
    navigate(`/courses/${courseId}/tutor?${params.toString()}`);
  }

  if (!plan || plan.length === 0) {
    return null;
  }

  return (
    <section id="study-plan" className="mt-8">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400 border border-brand-200 dark:border-brand-800">
            <Calendar className="h-5 w-5" />
          </span>
          <div>
            <h2 className="font-display text-lg font-bold text-ink-900 dark:text-ink-50">
              7-Day Personalized Study Plan
            </h2>
            <p className="text-xs text-ink-500 dark:text-ink-400">
              Deterministic learning schedule adapted to your verified topic mastery.
            </p>
          </div>
        </div>

        {isNewLearner && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 dark:bg-brand-950/60 px-3 py-1 text-xs font-semibold text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-800">
            <ShieldCheck className="h-3.5 w-3.5" />
            Diagnostic Baseline Plan
          </span>
        )}
      </div>

      {/* Days Grid / List */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-1">
        {plan.map((item) => {
          const isToday = item.day === 1;

          return (
            <div
              key={`day-${item.day}`}
              className={`card p-5 transition-all duration-200 ${
                isToday
                  ? 'border-l-4 border-l-brand-600 dark:border-l-brand-500 bg-gradient-to-r from-brand-50/30 via-white to-white dark:from-brand-950/40 dark:via-ink-900 dark:to-ink-900 shadow-sm ring-1 ring-brand-100 dark:ring-brand-900/40'
                  : 'hover:border-ink-300 dark:hover:border-ink-700 hover:shadow-card-hover'
              }`}
            >
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                {/* Left side: Day indicator + Topic info */}
                <div className="flex items-start gap-4 flex-1 min-w-0">
                  {/* Day badge column */}
                  <div className="shrink-0 flex flex-col items-center">
                    <div
                      className={`flex h-12 w-12 flex-col items-center justify-center rounded-xl font-display font-bold shadow-xs ${
                        isToday
                          ? 'bg-brand-600 text-white'
                          : 'bg-ink-100 text-ink-700 border border-ink-200 dark:bg-ink-800 dark:text-ink-200 dark:border-ink-700'
                      }`}
                    >
                      <span className="text-[10px] uppercase font-semibold leading-none opacity-80">
                        Day
                      </span>
                      <span className="text-lg leading-tight">{item.day}</span>
                    </div>
                    {isToday && (
                      <span className="mt-1 inline-flex items-center gap-0.5 rounded-full bg-brand-100 dark:bg-brand-950/60 px-1.5 py-0.2 text-[10px] font-bold text-brand-800 dark:text-brand-300">
                        <Clock className="h-2.5 w-2.5" />
                        Today
                      </span>
                    )}
                  </div>

                  {/* Topic and metadata */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="text-xs font-bold text-brand-700 dark:text-brand-300 bg-brand-50 dark:bg-brand-950/60 px-2 py-0.5 rounded-md border border-brand-200 dark:border-brand-800">
                        Day {item.day}
                      </span>
                      <h3 className="font-display text-base font-bold text-ink-900 dark:text-ink-50 truncate">
                        {item.topic}
                      </h3>
                      {getPriorityBadge(item.priority)}
                    </div>

                    {/* Metadata tags */}
                    <div className="flex flex-wrap items-center gap-2 text-xs mb-2">
                      <span className="inline-flex items-center gap-1 rounded-lg bg-ink-100 dark:bg-ink-800 px-2.5 py-0.5 font-medium text-ink-700 dark:text-ink-200">
                        {getActionIcon(item.action)}
                        {formatActionLabel(item.action)}
                      </span>

                      {getDifficultyBadge(item.difficulty)}

                      <span className="inline-flex items-center gap-1 rounded-full bg-ink-100 dark:bg-ink-800 px-2 py-0.5 font-medium text-ink-600 dark:text-ink-300">
                        <Target className="h-3 w-3" />
                        {item.question_count} questions
                      </span>
                    </div>

                    {/* Reason */}
                    {item.reason && (
                      <p className="text-xs text-ink-500 dark:text-ink-400 leading-relaxed">
                        <span className="font-semibold text-ink-600 dark:text-ink-300">Reason: </span>
                        {item.reason}
                      </p>
                    )}
                  </div>
                </div>

                {/* Right side: Action buttons */}
                <div className="flex flex-wrap items-center gap-2 shrink-0 pt-2 lg:pt-0 border-t border-ink-100 dark:border-ink-800 lg:border-t-0">
                  <button
                    onClick={() => handleAskTutor(item)}
                    className="btn-secondary text-xs py-2 px-3 inline-flex items-center gap-1.5"
                    title={`Ask AI Tutor about ${item.topic}`}
                  >
                    <Sparkles className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
                    Ask Tutor
                  </button>

                  <button
                    onClick={() => handleStartPractice(item)}
                    className="btn-primary text-xs py-2 px-3.5 inline-flex items-center gap-1.5"
                  >
                    <Target className="h-3.5 w-3.5" />
                    Start Practice
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
