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
  BookOpen,
} from 'lucide-react';
import { AppLayout } from '@/layouts/AppLayout';
import { ErrorState } from '@/components/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { api, getErrorMessage, getStudentId } from '@/lib/api';
import type {
  Course,
  LearnerMastery,
  LearnerSummary,
  LearnerRecommendations,
  Recommendation,
} from '@/types';

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
  if (pct >= 80) return 'text-accent-600';
  if (pct >= 50) return 'text-warn-600';
  return 'text-err-600';
}

function priorityBadge(priority: string): string {
  if (priority === 'high') return 'badge-error';
  if (priority === 'medium') return 'badge-warn';
  return 'badge-neutral';
}

export function LearningDashboardPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const [course, setCourse] = useState<Course | null>(null);
  const [summary, setSummary] = useState<LearnerSummary | null>(null);
  const [mastery, setMastery] = useState<LearnerMastery | null>(null);
  const [recommendations, setRecommendations] = useState<LearnerRecommendations | null>(null);
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
      const studentId = getStudentId();
      try {
        const [courseData, summaryData, masteryData, recData] = await Promise.all([
          api.getCourse(courseId),
          api.getLearnerSummary(studentId, courseId),
          api.getLearnerMastery(studentId, courseId),
          api.getLearnerRecommendations(studentId, courseId),
        ]);
        setCourse(courseData);
        setSummary(summaryData);
        setMastery(masteryData);
        setRecommendations(recData);
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [courseId],
  );

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  function handleStartPractice(rec: Recommendation) {
    const params = new URLSearchParams({
      topic: rec.topic,
      difficulty: rec.recommended_difficulty,
      count: String(rec.recommended_question_count),
    });
    navigate(`/courses/${courseId}/assessments?${params.toString()}`);
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
        className="inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-700 transition-colors mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Course
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900">
            My Learning
          </h1>
          <p className="mt-1.5 text-sm text-ink-500 max-w-lg">
            Track your mastery across topics and get personalized recommendations based on your assessment performance.
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

      {error && (
        <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-err-200 bg-err-50 px-4 py-3 animate-fade-in">
          <AlertCircle className="h-5 w-5 text-err-500 shrink-0 mt-0.5" />
          <p className="text-sm text-err-700">{error}</p>
        </div>
      )}

      {/* New learner empty state */}
      {isNewLearner ? (
        <div className="mt-8">
          <div className="card p-8 text-center animate-fade-in">
            <span className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 mb-4">
              <Sparkles className="h-8 w-8" />
            </span>
            <h2 className="font-display text-xl font-semibold text-ink-900 mb-2">
              Your learning profile is ready to begin
            </h2>
            <p className="text-sm text-ink-500 max-w-md mx-auto">
              Mastery insights, weak topic analysis, and personalized recommendations will appear here after you complete your first assessment.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
              <Link
                to={courseId ? `/courses/${courseId}/assessments` : '/dashboard'}
                className="btn-primary"
              >
                <Target className="h-4 w-4" />
                Start an Assessment
              </Link>
            </div>
          </div>

          {/* Show diagnostic recommendation if available */}
          {recommendations?.recommendations && recommendations.recommendations.length > 0 && (
            <section className="mt-8">
              <h2 className="font-display text-lg font-semibold text-ink-900 mb-4 flex items-center gap-2">
                <Zap className="h-5 w-5 text-brand-600" />
                Recommended Next
              </h2>
              <div className="space-y-3">
                {recommendations.recommendations.map((rec, i) => (
                  <RecommendationCard
                    key={`${rec.topic}-${i}`}
                    rec={rec}
                    onStart={() => handleStartPractice(rec)}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      ) : (
        <>
          {/* Overall Mastery */}
          <section className="mt-8">
            <div className="card p-6 animate-fade-in">
              <div className="flex items-center gap-2 mb-4">
                <Award className="h-5 w-5 text-brand-600" />
                <h2 className="font-display text-lg font-semibold text-ink-900">
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
                  <div className="h-3 overflow-hidden rounded-full bg-ink-100">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${masteryColor(overallPct)}`}
                      style={{ width: `${overallPct}%` }}
                    />
                  </div>
                  <p className="mt-2 text-xs text-ink-500">
                    Across all topics in this course
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Topic Mastery */}
          {mastery && mastery.topics && mastery.topics.length > 0 && (
            <section className="mt-6">
              <h2 className="font-display text-lg font-semibold text-ink-900 mb-4 flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-brand-600" />
                Topic Mastery
              </h2>
              <div className="space-y-3">
                {mastery.topics.map((tm, i) => {
                  const pct = Math.round(tm.mastery_score * 100);
                  return (
                    <div key={`${tm.topic}-${i}`} className="card p-4 animate-fade-in">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-ink-800 truncate">
                          {tm.topic}
                        </span>
                        <span className={`text-sm font-semibold shrink-0 ${masteryTextColor(pct)}`}>
                          {pct}%
                        </span>
                      </div>
                      <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-ink-100">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${masteryColor(pct)}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-400">
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
              <h2 className="font-display text-lg font-semibold text-ink-900 mb-4 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-warn-600" />
                Needs Attention
              </h2>
              <div className="space-y-3">
                {summary.weak_topics.map((wt, i) => {
                  const pct = Math.round(wt.mastery_score * 100);
                  return (
                    <div key={`${wt.topic}-${i}`} className="card p-4 border-l-4 border-l-warn-400 animate-fade-in">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-ink-800">
                          {wt.topic}
                        </span>
                        <span className={`text-sm font-semibold shrink-0 ${masteryTextColor(pct)}`}>
                          {pct}%
                        </span>
                      </div>
                      {wt.reason && (
                        <p className="mt-2 text-xs text-ink-500 leading-relaxed">
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
              <h2 className="font-display text-lg font-semibold text-ink-900 mb-4 flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-accent-600" />
                Strong Areas
              </h2>
              <div className="space-y-3">
                {summary.strong_topics.map((st, i) => {
                  const pct = Math.round(st.mastery_score * 100);
                  return (
                    <div key={`${st.topic}-${i}`} className="card p-4 border-l-4 border-l-accent-400 animate-fade-in">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-ink-800">
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
              <h2 className="font-display text-lg font-semibold text-ink-900 mb-4 flex items-center gap-2">
                <Clock className="h-5 w-5 text-brand-600" />
                Recently Practiced
              </h2>
              <div className="space-y-3">
                {summary.recent_topics.map((rt, i) => {
                  const pct = Math.round(rt.mastery_score * 100);
                  return (
                    <div key={`${rt.topic}-${i}`} className="card p-4 animate-fade-in">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-ink-800 truncate">
                          {rt.topic}
                        </span>
                        <span className={`text-sm font-semibold shrink-0 ${masteryTextColor(pct)}`}>
                          {pct}%
                        </span>
                      </div>
                      {rt.last_interaction && (
                        <p className="mt-1.5 text-xs text-ink-400 inline-flex items-center gap-1">
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
              <h2 className="font-display text-lg font-semibold text-ink-900 mb-4 flex items-center gap-2">
                <Zap className="h-5 w-5 text-brand-600" />
                Recommended Next
              </h2>
              <div className="space-y-3">
                {recommendations.recommendations.map((rec, i) => (
                  <RecommendationCard
                    key={`${rec.topic}-${i}`}
                    rec={rec}
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
  onStart,
}: {
  rec: Recommendation;
  onStart: () => void;
}) {
  return (
    <div className="card p-5 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="font-display text-base font-semibold text-ink-900">
              {rec.topic}
            </h3>
            <span className={priorityBadge(rec.priority)}>
              {rec.priority} priority
            </span>
          </div>
          {rec.reason && (
            <p className="text-sm text-ink-500 leading-relaxed mb-3">
              <span className="font-medium text-ink-600">Reason: </span>
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
        <button
          onClick={onStart}
          className="btn-primary shrink-0"
        >
          <Target className="h-4 w-4" />
          Start Practice
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
