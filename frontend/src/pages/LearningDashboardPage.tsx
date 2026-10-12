import { useCallback, useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  TrendingUp,
  Award,
  Target,
  Zap,
  CheckCircle,
  AlertTriangle,
  Clock,
  Sparkles,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';
import { AppLayout } from '@/layouts/AppLayout';
import { ErrorState } from '@/components/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { api, getErrorMessage } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import type {
  Course,
  LearnerMastery,
  LearnerSummary,
  LearnerRecommendations,
  Recommendation,
  StudyPlanResponse,
  StudyPlanItem,
} from '@/types';
import { StudyPlanSection } from '@/components/StudyPlanSection';
import {
  formatActionLabel,
  getActionIcon,
} from '@/components/StudyPlanCard';

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function masteryColor(pct: number): string {
  if (pct >= 80) return 'bg-accent-500';
  if (pct >= 50) return 'bg-warn-500';
  return 'bg-err-500';
}

function masteryTextColor(pct: number): string {
  if (pct >= 80) return 'text-accent-600 dark:text-accent-400';
  if (pct >= 50) return 'text-warn-600 dark:text-warn-400';
  return 'text-err-600 dark:text-err-400';
}

function priorityBadge(priority: string): string {
  if (priority === 'high') return 'badge-error';
  if (priority === 'medium') return 'badge-warn';
  return 'badge-neutral';
}

export function LearningDashboardPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [course, setCourse] = useState<Course | null>(null);
  const [summary, setSummary] = useState<LearnerSummary | null>(null);
  const [mastery, setMastery] = useState<LearnerMastery | null>(null);
  const [recommendations, setRecommendations] = useState<LearnerRecommendations | null>(null);
  const [studyPlan, setStudyPlan] = useState<StudyPlanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const loadAll = useCallback(
    async (isRefresh = false) => {
      if (!courseId) return;
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError('');
      const studentId = user?.id || '';
      try {
        const [courseData, summaryData, masteryData, recData, planData] = await Promise.all([
          api.getCourse(courseId),
          api.getLearnerSummary(studentId, courseId),
          api.getLearnerMastery(studentId, courseId),
          api.getLearnerRecommendations(studentId, courseId),
          api.getStudyPlan(studentId, courseId).catch(() => null),
        ]);
        setCourse(courseData);
        setSummary(summaryData);
        setMastery(masteryData);
        setRecommendations(recData);
        setStudyPlan(planData);
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [courseId, user?.id],
  );

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const day1Plan = studyPlan?.plan?.[0] || null;

  function handleStartPractice(rec: Recommendation) {
    const params = new URLSearchParams({
      topic: rec.topic,
      difficulty: rec.recommended_difficulty,
      count: String(rec.recommended_question_count),
    });
    navigate(`/courses/${courseId}/assessments?${params.toString()}`);
  }

  function handleStartStudyPlanAction(item: StudyPlanItem) {
    if (!courseId) return;
    const params = new URLSearchParams({
      topic: item.topic,
      difficulty: item.difficulty,
      count: String(item.question_count),
    });
    navigate(`/courses/${courseId}/assessments?${params.toString()}`);
  }

  function handleAskTutorStudyPlan(item: StudyPlanItem) {
    if (!courseId) return;
    const params = new URLSearchParams({
      topic: item.topic,
    });
    navigate(`/courses/${courseId}/tutor?${params.toString()}`);
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center gap-2 text-ink-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading your learning profile…
        </div>
      </AppLayout>
    );
  }

  if (error && !summary) {
    return (
      <AppLayout>
        <ErrorState message="Unable to load your learning profile." onRetry={() => loadAll()} />
      </AppLayout>
    );
  }

  if (!summary) {
    return (
      <AppLayout>
        <ErrorState message="Unable to load your learning profile." onRetry={() => loadAll()} />
      </AppLayout>
    );
  }

  const isNewLearner = summary.status === 'new_learner';
  const overallPct = Math.round(summary.overall_mastery * 100);

  return (
    <AppLayout>
      <Link
        to={courseId ? `/courses/${courseId}` : '/dashboard'}
        className="inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-700 dark:text-ink-400 dark:hover:text-ink-200 transition-colors mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Course
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-white">
            {course?.title ? `${course.title} — Learning & Mastery` : 'My Learning & Mastery'}
          </h1>
          <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400 max-w-lg">
            Track your topic mastery and receive targeted practice recommendations based on verified assessment performance.
          </p>
        </div>
        <button
          onClick={() => loadAll(true)}
          disabled={refreshing}
          className="btn-secondary shrink-0"
        >
          {refreshing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Refresh
        </button>
      </div>

      {/* Continue Learning based on Day 1 / current recommended action */}
      {day1Plan && (
        <div className="mt-4 rounded-2xl bg-gradient-to-r from-brand-900 via-brand-800 to-indigo-900 p-5 text-white shadow-sm animate-fade-in">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1.5 flex-1 min-w-0">
              <div className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-0.5 text-[11px] font-medium text-white/90">
                <Sparkles className="h-3 w-3 text-brand-300" />
                Continue Learning &middot; Day 1 Focus
              </div>
              <h2 className="text-xl font-bold tracking-tight text-white truncate">
                Continue Learning: {day1Plan.topic}
              </h2>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="inline-flex items-center gap-1 rounded-md bg-white/15 px-2 py-0.5 text-white font-medium">
                  {getActionIcon(day1Plan.action)}
                  {formatActionLabel(day1Plan.action)}
                </span>
                <span className="rounded-md bg-white/15 px-2 py-0.5 text-white/90 capitalize font-medium">
                  {day1Plan.difficulty} difficulty
                </span>
                <span className="rounded-md bg-white/15 px-2 py-0.5 text-white/90 font-medium">
                  {day1Plan.question_count} questions
                </span>
              </div>
              <p className="text-xs text-white/75 max-w-xl leading-relaxed">
                {day1Plan.reason}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 shrink-0">
              <button
                onClick={() => handleStartStudyPlanAction(day1Plan)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-white dark:bg-ink-900 px-3.5 py-2 text-xs font-semibold text-brand-900 dark:text-brand-300 shadow hover:bg-brand-50 dark:hover:bg-ink-800 transition-colors"
              >
                <Target className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
                Start Practice
              </button>
              <button
                onClick={() => handleAskTutorStudyPlan(day1Plan)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-white/10 border border-white/20 px-3.5 py-2 text-xs font-semibold text-white hover:bg-white/20 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Ask Tutor
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Adaptive Mastery Core Story Banner */}
      <div className="mt-4 rounded-xl border border-brand-200 dark:border-brand-800 bg-brand-50/50 dark:bg-brand-950/30 p-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-brand-600 dark:text-brand-400 shrink-0" />
          <p className="text-xs font-semibold text-brand-900 dark:text-brand-300">
            Adaptive Mastery Engine
          </p>
        </div>
        <p className="mt-1 text-xs text-ink-600 dark:text-ink-300 leading-relaxed">
          LearnMate does not just answer questions — it tracks what you understand across course materials and adapts what you should study next.
        </p>
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-err-200 dark:border-err-800 bg-err-50 dark:bg-err-950/40 px-4 py-3 animate-fade-in">
          <AlertCircle className="h-5 w-5 text-err-500 shrink-0 mt-0.5" />
          <p className="text-sm text-err-700 dark:text-err-300">{error}</p>
        </div>
      )}

      {/* New learner empty state */}
      {isNewLearner ? (
        <div className="mt-8 space-y-6">
          <div className="card p-8 text-center animate-fade-in border-brand-200 dark:border-brand-800 bg-gradient-to-b from-brand-50/20 to-white dark:from-brand-950/20 dark:to-ink-900">
            <span className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400 mb-4 border border-brand-200 dark:border-brand-800">
              <Sparkles className="h-8 w-8" />
            </span>
            <h2 className="font-display text-xl font-bold text-ink-900 dark:text-white mb-2">
              Let&apos;s build your learning plan
            </h2>
            <p className="text-sm text-ink-500 dark:text-ink-400 max-w-lg mx-auto leading-relaxed">
              Your first assessment will personalize recommendations and evaluate your baseline mastery across course topics. We do not fabricate or estimate mastery without real assessment performance.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
              <button
                onClick={() => {
                  if (day1Plan) {
                    handleStartStudyPlanAction(day1Plan);
                  } else {
                    navigate(`/courses/${courseId}/assessments`);
                  }
                }}
                className="btn-primary"
              >
                <Target className="h-4 w-4" />
                Start Diagnostic Assessment
              </button>
              {courseId && (
                <Link
                  to={`/courses/${courseId}/tutor`}
                  className="btn-secondary"
                >
                  <Sparkles className="h-4 w-4 text-brand-600 dark:text-brand-400" />
                  Ask AI Tutor
                </Link>
              )}
            </div>
          </div>

          {/* Full 7-Day Study Plan section for new learner */}
          {studyPlan?.plan && studyPlan.plan.length > 0 && courseId && (
            <StudyPlanSection
              courseId={courseId}
              plan={studyPlan.plan}
              isNewLearner={true}
            />
          )}

          {/* Show diagnostic recommendation if available */}
          {recommendations?.recommendations && recommendations.recommendations.length > 0 && (
            <section className="mt-8">
              <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4 flex items-center gap-2">
                <Zap className="h-5 w-5 text-brand-600 dark:text-brand-400" />
                Recommended Next
              </h2>
              <div className="space-y-3">
                {recommendations.recommendations.map((rec, i) => (
                  <RecommendationCard
                    key={`${rec.topic}-${i}`}
                    rec={rec}
                    courseId={courseId}
                    onStart={() => handleStartPractice(rec)}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      ) : (
        <>
          {/* Full 7-Day Study Plan Section for active learner */}
          {studyPlan?.plan && studyPlan.plan.length > 0 && courseId && (
            <StudyPlanSection
              courseId={courseId}
              plan={studyPlan.plan}
              isNewLearner={false}
            />
          )}

          {/* Overall Mastery */}
          <section className="mt-8">
            <div className="card p-6 animate-fade-in">
              <div className="flex items-center gap-2 mb-4">
                <Award className="h-5 w-5 text-brand-600 dark:text-brand-400" />
                <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
                  Overall Mastery
                </h2>
              </div>
              <div className="flex items-center gap-6">
                <div className="shrink-0">
                  <p className={`font-display text-4xl font-bold ${masteryTextColor(overallPct)}`}>
                    {overallPct}%
                  </p>
                </div>
                <div className="flex-1">
                  <div className="h-3 overflow-hidden rounded-full bg-ink-100 dark:bg-ink-800">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${masteryColor(overallPct)}`}
                      style={{ width: `${overallPct}%` }}
                    />
                  </div>
                  <p className="mt-2 text-xs text-ink-500 dark:text-ink-400">
                    Across all topics in this course
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Topic Mastery */}
          {mastery && mastery.topics && mastery.topics.length > 0 && (
            <section className="mt-6">
              <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4 flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-brand-600 dark:text-brand-400" />
                Topic Mastery
              </h2>
              <div className="space-y-3">
                {mastery.topics.map((tm, i) => {
                  const pct = Math.round(tm.mastery_score * 100);
                  return (
                    <div key={`${tm.topic}-${i}`} className="card p-4 animate-fade-in">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-ink-800 dark:text-ink-200 truncate">
                          {tm.topic}
                        </span>
                        <span className={`text-sm font-semibold shrink-0 ${masteryTextColor(pct)}`}>
                          {pct}%
                        </span>
                      </div>
                      <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-ink-100 dark:bg-ink-800">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${masteryColor(pct)}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-400 dark:text-ink-500">
                        <span>{tm.attempts} attempt{tm.attempts !== 1 ? 's' : ''}</span>
                        <span>{tm.correct_attempts} correct</span>
                        <span>Confidence: {Math.round(tm.confidence * 100)}%</span>
                        {tm.last_interaction && (
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatTimestamp(tm.last_interaction)}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Weak Topics */}
          {summary.weak_topics && summary.weak_topics.length > 0 && (
            <section className="mt-6">
              <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-warn-600 dark:text-warn-400" />
                Needs Attention
              </h2>
              <div className="space-y-3">
                {summary.weak_topics.map((wt, i) => {
                  const pct = Math.round(wt.mastery_score * 100);
                  return (
                    <div key={`${wt.topic}-${i}`} className="card p-4 border-l-4 border-l-warn-400 animate-fade-in">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-ink-800 dark:text-ink-200">
                          {wt.topic}
                        </span>
                        <span className={`text-sm font-semibold shrink-0 ${masteryTextColor(pct)}`}>
                          {pct}%
                        </span>
                      </div>
                      {wt.reason && (
                        <p className="mt-2 text-xs text-ink-500 dark:text-ink-400 leading-relaxed">
                          {wt.reason}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Strong Topics */}
          {summary.strong_topics && summary.strong_topics.length > 0 && (
            <section className="mt-6">
              <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4 flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-accent-600 dark:text-accent-400" />
                Strong Areas
              </h2>
              <div className="space-y-3">
                {summary.strong_topics.map((st, i) => {
                  const pct = Math.round(st.mastery_score * 100);
                  return (
                    <div key={`${st.topic}-${i}`} className="card p-4 border-l-4 border-l-accent-400 animate-fade-in">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-ink-800 dark:text-ink-200">
                          {st.topic}
                        </span>
                        <span className={`text-sm font-semibold shrink-0 ${masteryTextColor(pct)}`}>
                          {pct}%
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Recent Topics */}
          {summary.recent_topics && summary.recent_topics.length > 0 && (
            <section className="mt-6">
              <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4 flex items-center gap-2">
                <Clock className="h-5 w-5 text-brand-600 dark:text-brand-400" />
                Recently Practiced
              </h2>
              <div className="space-y-3">
                {summary.recent_topics.map((rt, i) => {
                  const pct = Math.round(rt.mastery_score * 100);
                  return (
                    <div key={`${rt.topic}-${i}`} className="card p-4 animate-fade-in">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-ink-800 dark:text-ink-200 truncate">
                          {rt.topic}
                        </span>
                        <span className={`text-sm font-semibold shrink-0 ${masteryTextColor(pct)}`}>
                          {pct}%
                        </span>
                      </div>
                      {rt.last_interaction && (
                        <p className="mt-1.5 text-xs text-ink-400 dark:text-ink-500 inline-flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatTimestamp(rt.last_interaction)}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Recommendations */}
          {recommendations?.recommendations && recommendations.recommendations.length > 0 ? (
            <section className="mt-6">
              <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4 flex items-center gap-2">
                <Zap className="h-5 w-5 text-brand-600 dark:text-brand-400" />
                Recommended Next
              </h2>
              <div className="space-y-3">
                {recommendations.recommendations.map((rec, i) => (
                  <RecommendationCard
                    key={`${rec.topic}-${i}`}
                    rec={rec}
                    courseId={courseId}
                    onStart={() => handleStartPractice(rec)}
                  />
                ))}
              </div>
            </section>
          ) : !isNewLearner ? (
            <section className="mt-6">
              <EmptyState
                icon={<Zap className="h-7 w-7" />}
                title="No recommendations yet"
                description="Complete more assessments to receive personalized study recommendations."
              />
            </section>
          ) : null}
        </>
      )}
    </AppLayout>
  );
}

function RecommendationCard({
  rec,
  courseId,
  onStart,
}: {
  rec: Recommendation;
  courseId?: string;
  onStart: () => void;
}) {
  return (
    <div className="card p-5 animate-fade-in hover:border-brand-200 dark:hover:border-brand-800 transition-colors">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="font-display text-base font-semibold text-ink-900 dark:text-white">
              {rec.topic}
            </h3>
            <span className={priorityBadge(rec.priority)}>
              {rec.priority} priority
            </span>
          </div>
          {rec.reason && (
            <p className="text-sm text-ink-500 dark:text-ink-400 leading-relaxed mb-3">
              <span className="font-medium text-ink-600 dark:text-ink-300">Reason: </span>
              {rec.reason}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="badge-brand capitalize">
              {rec.recommended_action}
            </span>
            <span className="badge-neutral capitalize">
              {rec.recommended_difficulty}
            </span>
            <span className="badge-neutral">
              {rec.recommended_question_count} questions
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {courseId && (
            <Link
              to={`/courses/${courseId}/tutor`}
              className="btn-secondary text-xs inline-flex items-center gap-1.5"
              title={`Ask AI Tutor about ${rec.topic}`}
            >
              <Sparkles className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
              Ask Tutor
            </Link>
          )}
          <button
            onClick={onStart}
            className="btn-primary text-xs inline-flex items-center gap-1.5"
          >
            <Target className="h-3.5 w-3.5" />
            Practice Quiz
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
