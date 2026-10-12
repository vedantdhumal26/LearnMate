import { useCallback, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Loader2,
  CheckCircle,
  XCircle,
  TrendingUp,
  Award,
  FileText,
  BookOpen,
  Sparkles,
} from 'lucide-react';
import { api } from '@/lib/api';
import { SourceCard } from '@/components/SourceCard';
import { ErrorState } from '@/components/ErrorState';
import { ThemeToggle } from '@/components/ThemeToggle';
import type { AssessmentResult, Assessment } from '@/types';

export function AssessmentResultsPage() {
  const { assessmentId, courseId } = useParams<{ assessmentId: string; courseId: string }>();
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!assessmentId) return;
    setLoading(true);
    setError('');

    // Try sessionStorage first (set immediately after submit)
    const cached = sessionStorage.getItem(`assessment_result_${assessmentId}`);
    if (cached) {
      try {
        const parsed = JSON.parse(cached) as AssessmentResult;
        setResult(parsed);
        // Also try to load the assessment for question text
        try {
          const a = await api.getAssessment(assessmentId);
          setAssessment(a);
        } catch {
          // assessment may not be re-fetchable; that's OK
        }
        setLoading(false);
        return;
      } catch {
        // fall through
      }
    }

    setError('Unable to load assessment results. Please submit the assessment first.');
    setLoading(false);
  }, [assessmentId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-ink-50 dark:bg-ink-950">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-brand-600 dark:text-brand-400" />
          <p className="text-sm text-ink-500 dark:text-ink-400">Loading results…</p>
        </div>
      </div>
    );
  }

  if ((error && !result) || !result) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-ink-50 dark:bg-ink-950 px-4">
        <ErrorState
          message={error || 'Unable to load assessment results.'}
          onRetry={load}
        />
        <Link to={courseId ? `/courses/${courseId}/assessments` : '/dashboard'} className="btn-secondary mt-4">
          <ArrowLeft className="h-4 w-4" />
          Back to Assessments
        </Link>
      </div>
    );
  }

  const scorePct = Math.round(result.score);
  const passColor = scorePct >= 80 ? 'text-accent-600 dark:text-accent-400' : scorePct >= 50 ? 'text-warn-600 dark:text-warn-400' : 'text-err-600 dark:text-err-400';
  const ringColor = scorePct >= 80 ? 'border-accent-300 bg-accent-50 dark:border-accent-800/80 dark:bg-accent-950/30' : scorePct >= 50 ? 'border-warn-300 bg-warn-50 dark:border-warn-800/80 dark:bg-warn-950/30' : 'border-err-300 bg-err-50 dark:border-err-800/80 dark:bg-err-950/30';

  // Build a map of question_id -> question text from the assessment
  const questionTextMap = new Map<string, string>();
  if (assessment && assessment.questions) {
    for (const q of assessment.questions) {
      questionTextMap.set(q.id, q.question);
    }
  }

  const backLink = courseId
    ? `/courses/${courseId}/assessments`
    : '/dashboard';

  return (
    <div className="min-h-screen bg-ink-50 dark:bg-ink-950 text-ink-900 dark:text-ink-100">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-ink-200 dark:border-ink-800 bg-white/90 dark:bg-ink-900/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Link
              to={backLink}
              className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 hover:text-ink-700 dark:text-ink-400 dark:hover:bg-ink-800 dark:hover:text-ink-200 transition-colors shrink-0"
              aria-label="Back"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div className="min-w-0">
              <h1 className="font-display text-sm font-semibold text-ink-900 dark:text-white">
                Assessment Results
              </h1>
              <p className="text-xs text-ink-500 dark:text-ink-400">Your performance breakdown</p>
            </div>
          </div>
          <ThemeToggle id="results-theme-toggle" />
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
        {/* Score summary */}
        <div className={`card border-2 p-6 text-center animate-fade-in ${ringColor}`}>
          <div className="flex items-center justify-center gap-2 mb-3">
            <Award className={`h-5 w-5 ${passColor}`} />
            <span className="text-sm font-medium text-ink-500 dark:text-ink-400">Your Score</span>
          </div>
          <p className={`font-display text-5xl font-bold ${passColor}`}>
            {scorePct}%
          </p>
          <p className="mt-2 text-sm text-ink-600 dark:text-ink-300">
            <span className="font-semibold text-ink-800 dark:text-white">{result.correct}</span> out of{' '}
            <span className="font-semibold text-ink-800 dark:text-white">{result.total}</span> correct
          </p>
        </div>

        {/* Topic performance */}
        {result.topic_performance && result.topic_performance.length > 0 && (
          <section className="mt-6">
            <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4 flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-brand-600 dark:text-brand-400" />
              Topic Performance
            </h2>
            <div className="space-y-3">
              {result.topic_performance.map((tp, i) => {
                const pct = tp.total > 0 ? Math.round((tp.correct / tp.total) * 100) : 0;
                return (
                  <div key={`${tp.topic}-${i}`} className="card p-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium text-ink-800 dark:text-ink-200 truncate">
                        {tp.topic}
                      </span>
                      <span className="text-sm font-semibold text-ink-600 dark:text-ink-400 shrink-0">
                        {tp.correct} / {tp.total}
                      </span>
                    </div>
                    <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-ink-100 dark:bg-ink-800">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          pct >= 80 ? 'bg-accent-500' : pct >= 50 ? 'bg-warn-500' : 'bg-err-500'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Question-by-question results */}
        {result.question_results && result.question_results.length > 0 && (
          <section className="mt-6">
            <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4 flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-brand-600 dark:text-brand-400" />
              Question Results
            </h2>
            <div className="space-y-4">
              {result.question_results.map((qr, i) => {
                const qText = questionTextMap.get(qr.question_id);
                return (
                  <div
                    key={qr.question_id}
                    className={`card p-5 animate-fade-in ${qr.correct ? 'border-l-4 border-l-accent-400' : 'border-l-4 border-l-err-400'}`}
                    style={{ animationDelay: `${i * 50}ms` }}
                  >
                    {/* Question header */}
                    <div className="flex items-start gap-3">
                      <span
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                          qr.correct
                            ? 'bg-accent-100 text-accent-600 dark:bg-accent-950/70 dark:text-accent-400'
                            : 'bg-err-100 text-err-500 dark:bg-err-950/70 dark:text-err-400'
                        }`}
                      >
                        {qr.correct ? (
                          <CheckCircle className="h-4.5 w-4.5" />
                        ) : (
                          <XCircle className="h-4.5 w-4.5" />
                        )}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-medium text-ink-400 dark:text-ink-500">
                            Question {i + 1}
                          </span>
                          <span
                            className={`badge ${qr.correct ? 'badge-success' : 'badge-error'}`}
                          >
                            {qr.correct ? 'Correct' : 'Incorrect'}
                          </span>
                        </div>
                        {qText && (
                          <p className="text-sm font-medium leading-relaxed text-ink-900 dark:text-ink-100">
                            {qText}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Feedback */}
                    {qr.feedback && (
                      <div className="mt-3 ml-11 rounded-lg bg-ink-50 border border-ink-100 dark:bg-ink-900/60 dark:border-ink-800 px-3.5 py-2.5">
                        <p className="text-sm leading-relaxed text-ink-600 dark:text-ink-300">
                          {qr.feedback}
                        </p>
                      </div>
                    )}

                    {/* Sources */}
                    {qr.sources && qr.sources.length > 0 && (
                      <div className="mt-3 ml-11">
                        <p className="text-xs font-medium text-ink-500 dark:text-ink-400 flex items-center gap-1.5 mb-2">
                          <FileText className="h-3.5 w-3.5" />
                          Sources
                        </p>
                        <div className="space-y-2">
                          {qr.sources.map((src, si) => (
                            <SourceCard key={`${src.source_id}-${si}`} source={src} index={si} />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Actions */}
        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            to={courseId ? `/courses/${courseId}/learning` : '/dashboard'}
            className="btn-primary"
          >
            <TrendingUp className="h-4 w-4" />
            View Updated Learning Profile
          </Link>
          {courseId && (
            <Link
              to={`/courses/${courseId}/tutor`}
              className="btn-secondary inline-flex items-center gap-2"
            >
              <Sparkles className="h-4 w-4 text-brand-600 dark:text-brand-400" />
              Review with AI Tutor
            </Link>
          )}
          <Link to={backLink} className="btn-secondary">
            <ArrowLeft className="h-4 w-4" />
            Back to Assessments
          </Link>
        </div>
      </div>
    </div>
  );
}
