import { useCallback, useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  FileText,
  Send,
} from 'lucide-react';
import { api, getErrorMessage } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { SourceCard } from '@/components/SourceCard';
import { ErrorState } from '@/components/ErrorState';
import { ThemeToggle } from '@/components/ThemeToggle';
import type {
  Assessment,
  AssessmentQuestion,
} from '@/types';

interface AnswerMap {
  [questionId: string]: string;
}

export function AssessmentTakePage() {
  const { assessmentId, courseId } = useParams<{ assessmentId: string; courseId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState<AnswerMap>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [showConfirm, setShowConfirm] = useState(false);
  const [showSources, setShowSources] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    if (!assessmentId) return;
    setLoading(true);
    setError('');
    try {
      const data = await api.getAssessment(assessmentId);
      setAssessment(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [assessmentId]);

  useEffect(() => {
    load();
  }, [load]);

  function setAnswer(qId: string, value: string) {
    setAnswers((prev) => ({ ...prev, [qId]: value }));
  }

  function toggleSources(qId: string) {
    setShowSources((prev) => {
      const next = new Set(prev);
      if (next.has(qId)) next.delete(qId);
      else next.add(qId);
      return next;
    });
  }

  const totalQuestions = assessment?.questions.length ?? 0;
  const answeredCount = assessment
    ? assessment.questions.filter((q) => (answers[q.id] ?? '').trim().length > 0).length
    : 0;
  const allAnswered = answeredCount === totalQuestions && totalQuestions > 0;

  async function handleSubmit() {
    if (!assessmentId || !assessment) return;
    setShowConfirm(false);
    setSubmitting(true);
    setSubmitError('');
    try {
      const answerList = assessment.questions.map((q) => ({
        question_id: q.id,
        answer: (answers[q.id] ?? '').trim(),
      }));
      const result = await api.submitAssessment(assessmentId, {
        student_id: user?.id,
        answers: answerList,
      });
      sessionStorage.setItem(`assessment_result_${assessmentId}`, JSON.stringify(result));
      const redirectCourseId = courseId ?? assessment.course_id ?? '';
      navigate(`/courses/${redirectCourseId}/assessments/${assessmentId}/results`);
    } catch (err) {
      setSubmitError(getErrorMessage(err));
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-ink-50">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-brand-600" />
          <p className="text-sm text-ink-500">Loading assessment…</p>
        </div>
      </div>
    );
  }

  if (error && !assessment) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-ink-50 px-4">
        <ErrorState message={error} onRetry={load} />
        <Link to="/dashboard" className="btn-secondary mt-4">
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Link>
      </div>
    );
  }

  if (!assessment || !assessment.questions || assessment.questions.length === 0) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-ink-50 px-4">
        <ErrorState message="Assessment not found or has no questions." />
        <Link to="/dashboard" className="btn-secondary mt-4">
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const currentQuestion = assessment.questions[currentIdx];
  const progress = ((currentIdx + 1) / totalQuestions) * 100;
  const backLink = courseId
    ? `/courses/${courseId}/assessments`
    : '/dashboard';

  return (
    <div className="min-h-screen bg-ink-50 dark:bg-ink-950 transition-colors duration-150">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-ink-200 dark:border-ink-800 bg-white/90 dark:bg-ink-900/90 backdrop-blur-md">
        <div className="mx-auto max-w-3xl px-4 py-3 sm:px-6">
          <div className="flex items-center justify-between gap-4">
            <Link
              to={backLink}
              className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 hover:text-ink-700 dark:text-ink-400 dark:hover:bg-ink-800 dark:hover:text-ink-200 transition-colors shrink-0"
              aria-label="Back to assessments"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div className="flex-1 min-w-0 text-center">
              <h1 className="font-display text-sm font-semibold text-ink-900 dark:text-ink-100 truncate">
                {assessment.title || 'Assessment'}
              </h1>
              <p className="text-xs text-ink-500 dark:text-ink-400">
                Question {currentIdx + 1} of {totalQuestions}
              </p>
            </div>
            <div className="shrink-0 flex items-center">
              <ThemeToggle id="assessment-theme-toggle" />
            </div>
          </div>
          {/* Progress bar */}
          <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-ink-100 dark:bg-ink-800">
            <div
              className="h-full rounded-full bg-brand-600 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </header>

      {/* Main */}
      <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
        {/* Question navigator */}
        <div className="mb-6 flex flex-wrap items-center justify-center gap-2">
          {assessment.questions.map((q, i) => {
            const isAnswered = (answers[q.id] ?? '').trim().length > 0;
            const isCurrent = i === currentIdx;
            return (
              <button
                key={q.id}
                onClick={() => setCurrentIdx(i)}
                className={`flex h-9 w-9 items-center justify-center rounded-lg text-sm font-medium transition-all ${
                  isCurrent
                    ? 'bg-brand-600 text-white shadow-sm'
                    : isAnswered
                      ? 'bg-accent-100 text-accent-700 border border-accent-200 dark:bg-accent-950/60 dark:text-accent-300 dark:border-accent-800/60'
                      : 'bg-white dark:bg-ink-800 text-ink-500 dark:text-ink-300 border border-ink-200 dark:border-ink-700 hover:border-ink-300 dark:hover:border-ink-600'
                }`}
                aria-label={`Go to question ${i + 1}`}
              >
                {isAnswered && !isCurrent ? (
                  <CheckCircle className="h-4 w-4" />
                ) : (
                  i + 1
                )}
              </button>
            );
          })}
        </div>

        {/* Question card */}
        <div className="card p-6 animate-fade-in" key={currentQuestion.id}>
          {/* Meta badges */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {currentQuestion.topic && (
              <span className="badge-brand">{currentQuestion.topic}</span>
            )}
            <span className="badge-neutral capitalize">{currentQuestion.difficulty}</span>
            <span className="badge-neutral capitalize">
              {currentQuestion.question_type.replace('_', ' ')}
            </span>
          </div>

          {/* Question text — backend field is "question", not "question_text" */}
          <p className="text-base font-medium leading-relaxed text-ink-900 dark:text-ink-50">
            {currentQuestion.question}
          </p>

          {/* Answer area */}
          <div className="mt-5">
            <QuestionAnswerInput
              question={currentQuestion}
              value={answers[currentQuestion.id] ?? ''}
              onChange={(val) => setAnswer(currentQuestion.id, val)}
              disabled={submitting}
            />
          </div>

          {/* Sources */}
          {currentQuestion.sources && currentQuestion.sources.length > 0 && (
            <div className="mt-5 border-t border-ink-100 dark:border-ink-800 pt-4">
              <button
                onClick={() => toggleSources(currentQuestion.id)}
                className="flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 transition-colors"
              >
                <FileText className="h-4 w-4" />
                {showSources.has(currentQuestion.id) ? 'Hide source' : 'View source'}
              </button>
              {showSources.has(currentQuestion.id) && (
                <div className="mt-3 space-y-2">
                  {currentQuestion.sources.map((src, i) => (
                    <SourceCard key={`${src.source_id}-${i}`} source={src} index={i} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="mt-5 flex items-center justify-between gap-3">
          <button
            onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
            disabled={currentIdx === 0 || submitting}
            className="btn-secondary"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </button>

          {currentIdx < totalQuestions - 1 ? (
            <button
              onClick={() => setCurrentIdx((i) => Math.min(totalQuestions - 1, i + 1))}
              disabled={submitting}
              className="btn-primary"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={() => setShowConfirm(true)}
              disabled={submitting}
              className="btn-primary"
            >
              <Send className="h-4 w-4" />
              Submit Assessment
            </button>
          )}
        </div>

        {/* Submit error */}
        {submitError && (
          <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-err-200 bg-err-50 px-4 py-3 animate-fade-in">
            <AlertCircle className="h-5 w-5 text-err-500 shrink-0 mt-0.5" />
            <p className="text-sm text-err-700">{submitError}</p>
          </div>
        )}
      </div>

      {/* Confirmation modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in" onClick={() => !submitting && setShowConfirm(false)}>
          <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm" onClick={() => setShowConfirm(false)} />
          <div className="relative w-full max-w-md rounded-2xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 shadow-pop animate-fade-in-up" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-5">
              <div className="flex items-center gap-3 mb-4">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400">
                  <Send className="h-5 w-5" />
                </span>
                <h3 className="font-display text-base font-semibold text-ink-900 dark:text-ink-100">
                  Submit Assessment?
                </h3>
              </div>
              <p className="text-sm text-ink-500 dark:text-ink-400">
                You've answered <span className="font-semibold text-ink-700 dark:text-ink-200">{answeredCount}</span> of <span className="font-semibold text-ink-700 dark:text-ink-200">{totalQuestions}</span> questions.
                {!allAnswered && (
                  <span className="block mt-1.5 text-warn-600 dark:text-warn-400">
                    You have {totalQuestions - answeredCount} unanswered question{totalQuestions - answeredCount !== 1 ? 's' : ''}. You can still submit.
                  </span>
                )}
              </p>
              <div className="mt-5 flex items-center gap-3">
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="btn-primary flex-1"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Submitting…
                    </>
                  ) : (
                    <>
                      <CheckCircle className="h-4 w-4" />
                      Confirm Submit
                    </>
                  )}
                </button>
                <button
                  onClick={() => setShowConfirm(false)}
                  disabled={submitting}
                  className="btn-secondary"
                >
                  Keep Editing
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function QuestionAnswerInput({
  question,
  value,
  onChange,
  disabled,
}: {
  question: AssessmentQuestion;
  value: string;
  onChange: (val: string) => void;
  disabled: boolean;
}) {
  if (question.question_type === 'mcq' && question.options) {
    return (
      <div className="space-y-2.5">
        {question.options.map((opt, i) => {
          const letter = String.fromCharCode(65 + i);
          const isSelected = value === letter || value === opt;
          return (
            <button
              key={i}
              onClick={() => onChange(letter)}
              disabled={disabled}
              className={`flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left text-sm transition-all ${
                isSelected
                  ? 'border-brand-500 bg-brand-50 dark:bg-brand-950/60 text-ink-900 dark:text-ink-100 shadow-sm'
                  : 'border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-800/80 text-ink-700 dark:text-ink-200 hover:border-ink-300 dark:hover:border-ink-600 hover:bg-ink-50 dark:hover:bg-ink-700/50'
              } ${disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-sm font-semibold ${
                  isSelected
                    ? 'bg-brand-600 text-white'
                    : 'bg-ink-100 dark:bg-ink-700 text-ink-500 dark:text-ink-300'
                }`}
              >
                {letter}
              </span>
              <span className="flex-1">{opt}</span>
            </button>
          );
        })}
      </div>
    );
  }

  if (question.question_type === 'numerical') {
    return (
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="Enter a number"
        className="input"
        step="any"
      />
    );
  }

  // short_answer
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      placeholder="Type your answer…"
      className="input min-h-[100px] resize-y"
      maxLength={500}
    />
  );
}
